from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Product:
    # ── Identity ──────────────────────────────────────────────────────────────
    variant_id: str   # "gid://shopify/ProductVariant/123"  ← index key
    product_id: str   # "gid://shopify/Product/456"         ← for grouping

    # ── Display ───────────────────────────────────────────────────────────────
    name: str
    brand: str
    price: str        # kept as string; Shopify returns "49.90"
    currency: str
    category: str
    product_url: str

    # ── Visual ────────────────────────────────────────────────────────────────
    image_url: str
    image_path: str = ""   # local path after download

    # ── Operational ───────────────────────────────────────────────────────────
    available: bool = True
    indexed_at: Optional[str] = None   # ISO-8601, set after CLIP encode

    def mark_indexed(self) -> None:
        self.indexed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def __repr__(self) -> str:
        return (
            f"<Product variant_id={self.variant_id!r} "
            f"name={self.name!r} available={self.available}>"
        )
