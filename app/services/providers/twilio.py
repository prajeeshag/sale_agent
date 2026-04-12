"""
Twilio WhatsApp provider.

Inbound payloads are form-encoded. The Twilio SDK handles request validation,
auth, and sending. Media comes as direct URLs — no resolution step needed.

Docs: https://www.twilio.com/docs/whatsapp
"""

from __future__ import annotations

import logging

import httpx
from fastapi import Request, Response
from twilio.request_validator import RequestValidator
from twilio.rest import Client

from app.core.config import settings
from app.services.providers.base import InboundImage, WhatsAppProvider

log = logging.getLogger(__name__)


class TwilioProvider(WhatsAppProvider):

    def __init__(self) -> None:
        self._client    = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self._validator = RequestValidator(settings.twilio_auth_token)

    async def verify_webhook(self, request: Request) -> Response:
        # Twilio uses HMAC signature validation instead of a challenge handshake
        url       = str(request.url)
        signature = request.headers.get("X-Twilio-Signature", "")
        form      = await request.form()
        params    = {k: str(v) for k, v in form.items()}

        if not settings.debug and not self._validator.validate(url, params, signature):
            log.warning("Invalid Twilio signature from %s", request.client)
            return Response(content="Forbidden", status_code=403)

        return Response(content="OK", media_type="text/plain")

    async def parse_images(self, request: Request) -> list[InboundImage]:
        form      = await request.form()
        num_media = int(str(form.get("NumMedia", "0")))
        sender    = str(form.get("From", "")).removeprefix("whatsapp:")
        images    = []

        for i in range(num_media):
            content_type = str(form.get(f"MediaContentType{i}", ""))
            if content_type.startswith("image/"):
                media_url = str(form.get(f"MediaUrl{i}", ""))
                if media_url:
                    images.append(InboundImage(sender=sender, media_ref=media_url))
            else:
                log.debug("Ignored media type '%s'", content_type)

        return images

    async def get_media_bytes(self, media_ref: str) -> bytes:
        # Twilio redirects media URLs to their CDN — follow_redirects required.
        # Auth is only needed for the first hop; drop it after redirect.
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                media_ref,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
            resp.raise_for_status()
            return resp.content

    async def send_text(self, to: str, body: str) -> None:
        self._client.messages.create(
            from_=f"whatsapp:{settings.twilio_whatsapp_number}",
            to=f"whatsapp:{to}",
            body=body,
        )
        log.info("Sent message to %s via Twilio", to)
