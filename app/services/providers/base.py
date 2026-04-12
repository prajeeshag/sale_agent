"""
Base interface for WhatsApp providers.

To add a new provider:
  1. Subclass WhatsAppProvider
  2. Implement all abstract methods
  3. Add the provider name to config.py
  4. Register it in app/services/whatsapp.py
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from fastapi import Request, Response


@dataclass
class InboundImage:
    """Normalised representation of an inbound image message."""
    sender: str       # E.164 phone number, e.g. "+919876543210"
    media_ref: str    # Provider-specific reference: media_id (Meta) or URL (Twilio)


class WhatsAppProvider(ABC):

    @abstractmethod
    async def verify_webhook(self, request: Request) -> Response:
        """
        Handle the provider's webhook verification handshake.
        Return the appropriate HTTP response.
        """

    @abstractmethod
    async def parse_images(self, request: Request) -> list[InboundImage]:
        """
        Parse an inbound webhook payload.
        Return one InboundImage per image message; ignore all other message types.
        """

    @abstractmethod
    async def get_media_bytes(self, media_ref: str) -> bytes:
        """Download and return the raw image bytes for a given media reference."""

    @abstractmethod
    async def send_text(self, to: str, body: str) -> None:
        """Send a plain-text message to the given phone number."""
