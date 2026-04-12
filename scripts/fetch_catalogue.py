"""
Fetch all active Shopify product variants and download images.

Usage:
    python scripts/fetch_catalogue.py --shop mystore --id CLIENT_ID --secret CLIENT_SECRET
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import typer

# Allow running from the project root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.shopify import ShopifyFetcher

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

app = typer.Typer()


@app.command()
def main(
    output: Path = typer.Option(Path("catalogue.json"), help="Output catalogue JSON path"),
    images: Path = typer.Option(Path("images/"),        help="Directory for downloaded images"),
) -> None:
    """Fetch Shopify product variants and download their images."""
    from app.core.config import settings

    if not settings.shopify_shop or not settings.shopify_client_id or not settings.shopify_client_secret:
        typer.echo("Error: SHOPIFY_SHOP, SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET must be set in .env", err=True)
        raise typer.Exit(1)

    ShopifyFetcher(settings.shopify_shop, settings.shopify_client_id, settings.shopify_client_secret).run(
        image_dir=images,
        output=output,
    )


if __name__ == "__main__":
    app()
