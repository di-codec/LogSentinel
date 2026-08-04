import os

from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()


def get_azure_openai_endpoint() -> str:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    if not endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT is not set in .env")

    if "/api/projects/" in endpoint or ".services.ai.azure.com" in endpoint:
        resource = endpoint.split("https://", 1)[1].split(".services.ai.azure.com", 1)[0]
        return f"https://{resource}.openai.azure.com"

    return endpoint


def get_azure_openai_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=get_azure_openai_endpoint(),
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        api_version="2024-10-21",
    )


def require_env(name: str, optional: bool = False) -> str:
    value = os.getenv(name, "").strip()
    if not value and not optional:
        raise ValueError(f"{name} is not set in .env")
    return value
