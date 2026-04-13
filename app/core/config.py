import typing as t
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    debug: bool = False  # set True locally to skip webhook signature validation

    # Provider selector: "meta" | "twilio"
    whatsapp_provider: t.Literal["meta", "twilio"] = "twilio"

    # Meta WhatsApp Cloud API
    whatsapp_token: str = ""
    whatsapp_verify_token: str = "my_verify_token"
    whatsapp_phone_id: str = ""
    whatsapp_api_version: str = "v19.0"

    # Twilio WhatsApp
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = ""  # E.164, e.g. "+14155238886"

    # Shopify
    shopify_shop: str = ""
    shopify_client_id: str = ""
    shopify_client_secret: str = ""

    # Search data paths (relative to project root)
    index_path: Path = Path("index.faiss")
    id_map_path: Path = Path("id_map.json")

    model_config = {"env_file": ".env"}


settings = Settings()
