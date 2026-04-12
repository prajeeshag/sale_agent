"""
WhatsApp provider factory.
Returns the configured provider singleton; initialised once at app startup.
"""

from __future__ import annotations

from app.services.providers.base import WhatsAppProvider

_provider: WhatsAppProvider | None = None


def init_provider() -> None:
    global _provider
    from app.core.config import settings

    match settings.whatsapp_provider:
        case "meta":
            from app.services.providers.meta import MetaProvider
            _provider = MetaProvider()
        case "twilio":
            from app.services.providers.twilio import TwilioProvider
            _provider = TwilioProvider()
        case other:
            raise ValueError(f"Unknown whatsapp_provider: {other!r}. Choose 'meta' or 'twilio'.")


def get_provider() -> WhatsAppProvider:
    if _provider is None:
        raise RuntimeError("WhatsApp provider not initialised — call init_provider() at startup")
    return _provider
