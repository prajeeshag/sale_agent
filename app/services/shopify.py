"""
Shopify product + image fetcher.
Fetches all active product variants via GraphQL and downloads variant images.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from app.models.product import Product

log = logging.getLogger(__name__)

API_VERSION    = "2024-10"
PAGE_SIZE      = 50
MAX_RETRIES    = 5
RETRY_BACKOFF  = 2.0
REQUEST_DELAY  = 0.5
IMG_WORKERS    = 8
IMG_TIMEOUT    = 15

CURRENCY_QUERY = """{ shop { currencyCode } }"""

PRODUCTS_QUERY = """
query FetchProducts($cursor: String) {
  products(first: %(page_size)d, after: $cursor, query: "status:active") {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id title vendor productType handle
        featuredImage { url }
        variants(first: 100) {
          edges {
            node {
              id title price availableForSale
              image { url }
            }
          }
        }
      }
    }
  }
}
""" % {"page_size": PAGE_SIZE}


class ShopifyFetcher:
    def __init__(self, shop: str, client_id: str, client_secret: str) -> None:
        self.shop          = shop.rstrip("/")
        self.client_id     = client_id
        self.client_secret = client_secret
        self.token: Optional[str] = None
        self.endpoint      = (
            f"https://{self.shop}.myshopify.com/admin/api/{API_VERSION}/graphql.json"
        )
        self._products: list[Product] = []

    # ── Token ─────────────────────────────────────────────────────────────────

    def acquire_token(self) -> None:
        body = urllib.parse.urlencode({
            "grant_type":    "client_credentials",
            "client_id":     self.client_id,
            "client_secret": self.client_secret,
        }).encode()

        req = urllib.request.Request(
            f"https://{self.shop}.myshopify.com/admin/oauth/access_token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Token request failed — HTTP {exc.code}: {exc.reason}") from exc

        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"No access_token in response: {data}")

        self.token = token
        log.info("Access token acquired.")

    # ── GraphQL ───────────────────────────────────────────────────────────────

    def _graphql(self, query: str, variables: Optional[dict] = None) -> dict:
        if not self.token:
            raise RuntimeError("Call acquire_token() before making GraphQL requests.")

        payload = json.dumps({"query": query, "variables": variables or {}}).encode()
        headers = {
            "Content-Type":           "application/json",
            "X-Shopify-Access-Token": self.token,
        }
        delay = RETRY_BACKOFF

        for attempt in range(1, MAX_RETRIES + 1):
            req = urllib.request.Request(
                self.endpoint, data=payload, headers=headers, method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())

                if "errors" in data:
                    msgs = [e.get("message", "") for e in data["errors"]]
                    raise RuntimeError(f"GraphQL errors: {msgs}")

                return data

            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    wait = float(exc.headers.get("Retry-After", delay))
                    log.warning("Rate limited — waiting %.1fs", wait)
                    time.sleep(wait)
                    continue
                if exc.code >= 500:
                    log.warning("Server error %d, attempt %d/%d", exc.code, attempt, MAX_RETRIES)
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise RuntimeError(f"HTTP {exc.code}: {exc.reason}") from exc

            except urllib.error.URLError as exc:
                log.warning("Network error: %s, attempt %d/%d", exc.reason, attempt, MAX_RETRIES)
                time.sleep(delay)
                delay *= 2

        raise RuntimeError(f"All {MAX_RETRIES} retries exhausted.")

    # ── Parsing ───────────────────────────────────────────────────────────────

    def _parse_page(self, edges: list[dict], currency: str) -> list[Product]:
        products = []
        for edge in edges:
            node          = edge["node"]
            product_id    = node["id"]
            product_title = node["title"]
            vendor        = node["vendor"]
            category      = node["productType"]
            handle        = node["handle"]
            product_image = node.get("featuredImage")

            for ve in node["variants"]["edges"]:
                v     = ve["node"]
                image = v.get("image") or product_image
                if not image:
                    log.debug("Skipping variant %s — no image", v["id"])
                    continue

                variant_id    = v["id"]
                numeric_id    = variant_id.split("/")[-1]
                variant_title = v["title"]

                name = (
                    f"{product_title} / {variant_title}"
                    if variant_title.lower() != "default title"
                    else product_title
                )

                products.append(Product(
                    variant_id  = variant_id,
                    product_id  = product_id,
                    name        = name,
                    brand       = vendor,
                    price       = v["price"],
                    currency    = currency,
                    category    = category,
                    product_url = f"https://{self.shop}.com/products/{handle}?variant={numeric_id}",
                    image_url   = image["url"],
                    available   = v["availableForSale"],
                ))
        return products

    # ── Fetch loop ────────────────────────────────────────────────────────────

    def _fetch_products(self) -> None:
        currency = self._graphql(CURRENCY_QUERY)["data"]["shop"]["currencyCode"]
        log.info("Store currency: %s", currency)

        self._products = []
        cursor: Optional[str] = None
        page = 0

        while True:
            page += 1
            data  = self._graphql(PRODUCTS_QUERY, {"cursor": cursor})
            pdata = data["data"]["products"]
            parsed = self._parse_page(pdata["edges"], currency)
            self._products.extend(parsed)

            log.info(
                "Page %d — %d products, %d variants with images | total: %d",
                page, len(pdata["edges"]), len(parsed), len(self._products),
            )

            if not pdata["pageInfo"]["hasNextPage"]:
                break

            cursor = pdata["pageInfo"]["endCursor"]
            time.sleep(REQUEST_DELAY)

        log.info("Fetch complete — %d variants", len(self._products))

    # ── Image download ────────────────────────────────────────────────────────

    def _download_one(self, product: Product, image_dir: Path) -> bool:
        numeric_id = product.variant_id.split("/")[-1]
        url_path   = product.image_url.split("?")[0]
        ext        = Path(url_path).suffix.lower() or ".jpg"
        dest       = image_dir / f"{numeric_id}{ext}"

        if dest.exists() and dest.stat().st_size > 0:
            product.image_path = str(dest)
            return True

        try:
            req = urllib.request.Request(
                product.image_url,
                headers={"User-Agent": "ProductVisualSearchBot/1.0"},
            )
            with urllib.request.urlopen(req, timeout=IMG_TIMEOUT) as resp:
                dest.write_bytes(resp.read())
            product.image_path = str(dest)
            log.debug("Downloaded → %s", dest)
            return True
        except Exception as exc:
            log.error("Failed to download image for %s: %s", product.variant_id, exc)
            return False

    def _download_all(self, image_dir: Path) -> None:
        image_dir.mkdir(parents=True, exist_ok=True)
        success = failed = 0

        with ThreadPoolExecutor(max_workers=IMG_WORKERS) as pool:
            futures = {pool.submit(self._download_one, p, image_dir): p for p in self._products}
            for future in as_completed(futures):
                if future.result():
                    success += 1
                else:
                    failed += 1

        log.info("Images: %d downloaded, %d failed", success, failed)

        before = len(self._products)
        self._products = [p for p in self._products if p.image_path]
        removed = before - len(self._products)
        if removed:
            log.warning("Removed %d variants with missing images", removed)

    # ── Save ──────────────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump([p.to_dict() for p in self._products], f, indent=2, ensure_ascii=False)
        log.info("Saved %d variants → %s", len(self._products), path)

    # ── Public entry point ────────────────────────────────────────────────────

    def run(
        self,
        image_dir: str | Path = "images",
        output:    str | Path = "catalogue.json",
    ) -> list[Product]:
        self.acquire_token()
        self._fetch_products()
        self._download_all(Path(image_dir))
        self.save(output)
        return self._products
