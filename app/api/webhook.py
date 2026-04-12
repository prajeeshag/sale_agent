"""
WhatsApp webhook — provider-agnostic.

GET  /webhook  — Provider verification handshake
POST /webhook  — Inbound messages

The active provider (Meta / Twilio / ...) is selected via WHATSAPP_PROVIDER in config.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from app.services import search as search_service
from app.services.whatsapp import get_provider

log = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.get("")
async def verify(request: Request):
    return await get_provider().verify_webhook(request)


@router.post("")
async def receive(request: Request):
    provider = get_provider()
    images   = await provider.parse_images(request)

    for image in images:
        try:
            image_bytes = await provider.get_media_bytes(image.media_ref)
        except Exception as exc:
            log.error("Failed to download media for %s: %s", image.sender, exc)
            await provider.send_text(image.sender, "Sorry, I couldn't process your image. Please try again.")
            continue

        searcher = search_service.get_searcher()
        results  = searcher.search(image_bytes, top_k=1)

        if not results:
            await provider.send_text(image.sender, "No matching products found.")
            continue

        r     = results[0]
        reply = (
            f"Best match ({r.similarity:.0%} similarity)\n\n"
            f"*{r.name}*\n"
            f"{r.currency} {r.price} | {'In stock' if r.available else 'Out of stock'}\n"
            f"{r.product_url}"
        )
        await provider.send_text(image.sender, reply)

    return {"status": "ok"}
