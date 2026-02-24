from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models import BaseChatModel

from config.settings import settings


@lru_cache(maxsize=1)
def get_llm() -> BaseChatModel:
    """
    Singleton LLM instance.

    Provider is selected via the LLM_PROVIDER env variable:
      - "bedrock"  (default) — AWS Bedrock / Claude via boto3
      - "openai"              — OpenAI API (use when Bedrock is throttled)

    Streaming is disabled for compatibility with with_structured_output().
    """
    provider = settings.llm_provider.lower().strip()

    if provider == "openai":
        return _build_openai()
    else:
        return _build_bedrock()


def _build_bedrock() -> BaseChatModel:
    from langchain_aws import ChatBedrock
    import boto3

    kwargs: dict = {
        "model_id": settings.bedrock_model_id,
        "region_name": settings.aws_default_region,
        "model_kwargs": {
            "temperature": settings.bedrock_temperature,
            "max_tokens": settings.bedrock_max_tokens,
            "anthropic_version": "bedrock-2023-05-31",
        },
        "streaming": False,
    }

    # Build an explicit boto3 session so .env credentials take priority over
    # any cached SSO sessions in ~/.aws/
    if settings.aws_profile:
        session = boto3.Session(profile_name=settings.aws_profile)
    elif settings.aws_access_key_id and settings.aws_secret_access_key:
        session = boto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_default_region,
        )
    else:
        session = boto3.Session()

    kwargs["client"] = session.client("bedrock-runtime", region_name=settings.aws_default_region)
    return ChatBedrock(**kwargs)


def _build_openai() -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    if not settings.openai_api_key:
        raise ValueError(
            "LLM_PROVIDER=openai but OPENAI_API_KEY is not set. "
            "Add it to your .env file."
        )

    return ChatOpenAI(
        model=settings.openai_model_id,
        api_key=settings.openai_api_key,
        temperature=settings.openai_temperature,
        max_tokens=settings.openai_max_tokens,
        streaming=False,
    )
