"""
Meta WhatsApp Cloud API provider.

Docs: https://developers.facebook.com/docs/whatsapp/cloud-api
"""

from __future__ import annotations

import logging

import httpx
from fastapi import Request, Response

from app.core.config import settings
from app.services.providers.base import InboundImage, WhatsAppProvider

log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com"


class MetaProvider(WhatsAppProvider):

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {settings.whatsapp_token}"}

    async def verify_webhook(self, request: Request) -> Response:
        params = request.query_params
        if (
            params.get("hub.mode") == "subscribe"
            and params.get("hub.verify_token") == settings.whatsapp_verify_token
        ):
            return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
        return Response(content="Forbidden", status_code=403)

    async def parse_images(self, request: Request) -> list[InboundImage]:
        body   = await request.json()
        images = []

        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                for message in change.get("value", {}).get("messages", []):
                    if message.get("type") == "image":
                        images.append(InboundImage(
                            sender    = message["from"],
                            media_ref = message["image"]["id"],
                        ))
                    else:
                        log.debug("Ignored message type '%s'", message.get("type"))

        return images

    async def get_media_bytes(self, media_ref: str) -> bytes:
        async with httpx.AsyncClient() as client:
            # Resolve media_id → download URL
            resp = await client.get(
                f"{GRAPH_BASE}/{settings.whatsapp_api_version}/{media_ref}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            url = resp.json()["url"]

            # Download binary content
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.content

    async def send_text(self, to: str, body: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GRAPH_BASE}/{settings.whatsapp_api_version}/{settings.whatsapp_phone_id}/messages",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": body},
                },
            )
            resp.raise_for_status()
            log.info("Sent message to %s via Meta", to)
