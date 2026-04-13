FROM python:3.12-slim

# faiss-cpu requires libgomp on Linux
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Use uv for fast dependency installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (cached layer — only rebuilds when pyproject/lock changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source
COPY app/     ./app/

# Pre-download CLIP model weights so the first request isn't slow
#RUN uv run python -c "\
#from transformers import CLIPModel, CLIPProcessor; \
#CLIPModel.from_pretrained('openai/clip-vit-base-patch32'); \
#CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')"

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
