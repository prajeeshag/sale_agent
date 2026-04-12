"""
Build a FAISS index from the product catalogue.

Usage:
    python scripts/build_index.py
    python scripts/build_index.py --catalogue catalogue.json --index index.faiss --id-map id_map.json
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

# Fix duplicate OpenMP before any heavy imports
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import torch  # isort: skip
import faiss
import typer
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

BATCH_SIZE = 32
app = typer.Typer()


def _best_device():
    if torch.backends.mps.is_available():
        log.info("Device: MPS (Apple Silicon)")
        return torch.device("mps")
    if torch.cuda.is_available():
        log.info("Device: CUDA")
        return torch.device("cuda")
    log.info("Device: CPU")
    return torch.device("cpu")


def load_catalogue(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        products = json.load(f)
    valid = [
        p for p in products if p.get("image_path") and Path(p["image_path"]).exists()
    ]
    skipped = len(products) - len(valid)
    if skipped:
        log.warning("Skipped %d products with missing image_path", skipped)
    log.info("Indexing %d products", len(valid))
    return valid


def encode(products: list[dict]):
    device = _best_device()
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    model.eval()

    all_embeddings = []
    total = len(products)

    for start in range(0, total, BATCH_SIZE):
        batch = products[start : start + BATCH_SIZE]
        images = []

        for p in batch:
            try:
                images.append(Image.open(p["image_path"]).convert("RGB"))
            except Exception as exc:
                log.error("Cannot open %s: %s — using blank", p["image_path"], exc)
                images.append(Image.new("RGB", (224, 224)))

        inputs = processor(images=images, return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            features = model.get_image_features(**inputs)

        if not isinstance(features, torch.Tensor):
            features = features.pooler_output

        features = features / features.norm(dim=-1, keepdim=True)
        all_embeddings.append(features.cpu().float())
        log.info("Encoded %d / %d", min(start + BATCH_SIZE, total), total)

    return torch.cat(all_embeddings, dim=0)


def build_index(embeddings):
    vectors = embeddings.numpy().astype("float32")
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)  # type: ignore
    log.info("FAISS index built — %d vectors, dim=%d", index.ntotal, dim)
    return index


def save(index, products: list[dict], index_path: Path, id_map_path: Path) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_path))
    log.info("Saved index → %s", index_path)

    id_map = {str(i): p for i, p in enumerate(products)}
    with id_map_path.open("w", encoding="utf-8") as f:
        json.dump(id_map, f, indent=2, ensure_ascii=False)
    log.info("Saved id_map → %s", id_map_path)


@app.command()
def main(
    catalogue: Path = typer.Option(Path("catalogue.json"), help="Input catalogue JSON"),
    index: Path = typer.Option(Path("index.faiss"), help="Output FAISS index path"),
    id_map: Path = typer.Option(Path("id_map.json"), help="Output id_map JSON path"),
) -> None:
    """Encode product images with CLIP and build a FAISS index."""
    products = load_catalogue(catalogue)
    embeddings = encode(products)
    idx = build_index(embeddings)
    save(idx, products, index, id_map)
    log.info("Indexing complete.")


if __name__ == "__main__":
    app()
