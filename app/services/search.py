"""
Visual search service.
Loads CLIP + FAISS index once at app startup; call search() per request.
"""

from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import torch  # isort: skip
import faiss
import numpy as np

# torch must be imported before faiss to avoid OpenMP conflicts on macOS
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

log = logging.getLogger(__name__)


def _best_device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


@dataclass
class SearchResult:
    rank: int
    similarity: float
    product_id: str
    variant_id: str
    name: str
    brand: str
    price: str
    currency: str
    category: str
    product_url: str
    image_url: str
    available: bool

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "similarity": round(self.similarity, 4),
            "product_id": self.product_id,
            "variant_id": self.variant_id,
            "name": self.name,
            "brand": self.brand,
            "price": self.price,
            "currency": self.currency,
            "category": self.category,
            "product_url": self.product_url,
            "image_url": self.image_url,
            "available": self.available,
        }


class Searcher:
    def __init__(self, index_path: str | Path, id_map_path: str | Path) -> None:
        self._index_path = Path(index_path)
        self._id_map_path = Path(id_map_path)

        log.info("Loading FAISS index from %s", self._index_path)
        self._index = faiss.read_index(str(self._index_path))

        log.info("Loading id_map from %s", self._id_map_path)
        with self._id_map_path.open(encoding="utf-8") as f:
            self._id_map: dict[str, dict] = json.load(f)

        log.info(
            "Search ready — %d vectors, %d products",
            self._index.ntotal,
            len(self._id_map),
        )

    def _encode(self, image_bytes: bytes) -> "np.ndarray":
        device = _best_device()
        model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
        processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        model.eval()

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = processor(images=[image], return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            features = model.get_image_features(**inputs)

        if not isinstance(features, torch.Tensor):
            features = features.pooler_output

        features = features / features.norm(dim=-1, keepdim=True)
        return features.cpu().float().numpy().astype("float32")

    def search(self, image_bytes: bytes, top_k: int = 5) -> list[SearchResult]:
        import numpy as np

        query_vec = self._encode(image_bytes)
        query_vec = np.ascontiguousarray(query_vec.reshape(1, -1))

        scores, indices = self._index.search(query_vec, top_k)

        results = []
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0]), start=1):
            if idx == -1:
                continue
            product = self._id_map.get(str(idx))
            if not product:
                log.warning("No product at FAISS index position %d", idx)
                continue
            results.append(
                SearchResult(
                    rank=rank,
                    similarity=float(score),
                    product_id=product["product_id"],
                    variant_id=product["variant_id"],
                    name=product["name"],
                    brand=product["brand"],
                    price=product["price"],
                    currency=product["currency"],
                    category=product["category"],
                    product_url=product["product_url"],
                    image_url=product["image_url"],
                    available=product["available"],
                )
            )
        return results


# Module-level singleton — initialised by app lifespan
_searcher: Searcher | None = None


def init_searcher(index_path: str | Path, id_map_path: str | Path) -> None:
    global _searcher
    _searcher = Searcher(index_path, id_map_path)


def get_searcher() -> Searcher:
    if _searcher is None:
        raise RuntimeError("Searcher not initialised — call init_searcher() at startup")
    return _searcher
