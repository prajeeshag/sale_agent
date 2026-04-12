"""
Search the FAISS index with a query image.

Usage:
    python scripts/search.py image.jpg
    python scripts/search.py image.jpg --top-k 10
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import typer

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

app = typer.Typer()


@app.command()
def main(
    image: Path = typer.Argument(..., help="Path to query image"),
    top_k: int  = typer.Option(5, "--top-k", "-k", help="Number of results to return"),
) -> None:
    """Search the product catalogue by image similarity."""
    from app.core.config import settings
    from app.services.search import Searcher

    if not image.exists():
        typer.echo(f"Error: image file '{image}' not found", err=True)
        raise typer.Exit(1)

    searcher = Searcher(settings.index_path, settings.id_map_path)
    results  = searcher.search(image.read_bytes(), top_k=top_k)

    if not results:
        typer.echo("No results found.")
        raise typer.Exit(0)

    typer.echo(f"\nTop {len(results)} results for: {image}\n")
    typer.echo(f"{'Rank':<5} {'Similarity':<12} {'Name':<45} {'Price':<12} {'Available'}")
    typer.echo("-" * 95)

    for r in results:
        price = f"{r.currency} {r.price}"
        avail = "yes" if r.available else "no"
        typer.echo(f"{r.rank:<5} {r.similarity:<12.4f} {r.name[:44]:<45} {price:<12} {avail}")
        typer.echo(f"      product_id:  {r.product_id}")
        typer.echo(f"      variant_id:  {r.variant_id}")
        typer.echo(f"      {r.product_url}")
        typer.echo()


if __name__ == "__main__":
    app()
