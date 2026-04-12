# Product Visual Search

A lightweight image-similarity search system for clothing shops.
Customers send screenshots of products via chat — this system finds the matching product in your catalogue.

Built on: **CLIP** (image embeddings) + **FAISS** (vector search) + **FastAPI** (REST API).

---

## Project structure

```
product_search/
├── catalogue/
│   ├── embedder.py        # CLIP encoder + FAISS index wrapper
│   └── noise_handler.py   # Screenshot cleaning (crop, denoise, resize)
├── api/
│   └── server.py          # FastAPI REST server
├── scripts/
│   ├── ingest.py          # CLI: build/patch the catalogue index
│   └── test_pipeline.py   # End-to-end smoke test
├── data/                  # Created automatically (index files live here)
├── catalogue.example.json # Example catalogue format
└── requirements.txt
```

---

## Setup

```bash
# 1. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Verify everything works (downloads CLIP weights on first run, ~600 MB)
python scripts/test_pipeline.py
```

---

## Quickstart

### Step 1 — Prepare your catalogue JSON

Create a `catalogue.json` file (see `catalogue.example.json`):

```json
[
  {
    "product_id": "shirt_001",
    "image_path": "product_images/shirt_001.jpg",
    "name": "Blue Linen Shirt",
    "price": "49.99",
    "url": "https://shop.example.com/shirt-001"
  }
]
```

### Step 2 — Build the index

```bash
python scripts/ingest.py --catalogue catalogue.json
```

Output:
```
  [OK]   shirt_001 — Blue Linen Shirt
  [OK]   dress_002 — Floral Midi Dress
Done. 2 indexed, 0 failed. Total in index: 2
```

### Step 3 — Start the API server

```bash
uvicorn api.server:app --host 0.0.0.0 --port 8000
```

### Step 4 — Search

```bash
# Using curl with a file upload
curl -X POST http://localhost:8000/search \
  -F "file=@customer_screenshot.png" \
  -F "top_k=3"

# Response
{
  "matches": [
    {"product_id": "shirt_001", "score": 0.87, "name": "Blue Linen Shirt", "price": "49.99"},
    {"product_id": "dress_002", "score": 0.41, "name": "Floral Midi Dress", "price": "79.99"}
  ],
  "query_cleaned": true,
  "total_in_index": 2
}
```

---

## Adding new products (catalogue patching)

No rebuild needed. Just upsert the new product:

```bash
python scripts/ingest.py \
  --add jacket_004 product_images/jacket_004.jpg \
  --name "Leather Biker Jacket" \
  --price "149.99" \
  --url "https://shop.example.com/jacket-004"
```

Or via the API (DELETE to remove):

```bash
curl -X DELETE http://localhost:8000/products/jacket_004
```

---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/search` | Search by image file upload |
| `POST` | `/search/base64` | Search by base64-encoded image (for chat bots) |
| `GET`  | `/health` | Index stats + health check |
| `GET`  | `/products` | List all catalogue products |
| `DELETE` | `/products/{id}` | Remove a product |

Interactive docs: http://localhost:8000/docs

---

## Tuning the confidence threshold

The `threshold` parameter controls how strict matching is (0.0–1.0):

| Value | Behaviour |
|-------|-----------|
| `0.20` | Default. Returns plausible matches, may include weak ones. |
| `0.40` | Stricter. Reduces false positives for visually similar products. |
| `0.60` | High confidence only. May return zero results for noisy images. |

Start at `0.20` and raise it if you're getting too many wrong matches.

---

## Hardware requirements

| Component | Requirement |
|-----------|-------------|
| CLIP model (ViT-B/32) | ~600 MB RAM, CPU only |
| FAISS index | ~1 MB per 1,000 products |
| API server | ~50 MB |
| **Minimum** | **2 GB RAM, any x86-64 CPU** |

Query time: ~200–500ms per image on a modern CPU.

---

## Upgrading to fashion-specific embeddings

For better clothing similarity, swap CLIP for `patrickjohncyh/fashion-clip`:

In `catalogue/embedder.py`, change:
```python
MODEL_NAME = "openai/clip-vit-base-patch32"
```
to:
```python
MODEL_NAME = "patrickjohncyh/fashion-clip"
```

Then rebuild the index (`python scripts/ingest.py --catalogue catalogue.json`).
The rest of the system is unchanged.
