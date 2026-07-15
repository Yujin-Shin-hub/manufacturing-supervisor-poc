"""
작성자  : 신유진
작성일  : 2026-07-06
작성 목적: LLM 클라이언트 래퍼 — Qwen/OpenAI 호출·재시도·structured output 일원화
변경 이력:
  - 2026-07-06: 단계 0.5 스캐폴딩 — 스텁 생성
  - 2026-07-06: 단계 2 Qwen/OpenAI provider 선택, JSON 검증, 1회 복구 요청 구현
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError


ProviderName = Literal["auto", "qwen", "openai"]
ActiveProviderName = Literal["qwen", "openai"]
ModelT = TypeVar("ModelT", bound=BaseModel)

DEFAULT_SYSTEM_PROMPT = (
    "You are a manufacturing supervisor assistant. "
    "Return only valid JSON. Do not invent numeric values."
)


@dataclass(frozen=True)
class ProviderConfig:
    """환경변수에서 읽은 LLM provider 설정."""

    provider: ActiveProviderName
    model_name: str
    base_url: str
    api_key: str


@dataclass(frozen=True)
class LLMCompletion:
    """LLM 호출 결과와 provider 선택 메타데이터."""

    result: BaseModel
    requested_provider: ProviderName
    active_provider: ActiveProviderName
    fallback_used: bool
    model_name: str


class LLMError(RuntimeError):
    """LLM 호출 또는 JSON 검증 실패."""


def _load_env() -> None:
    load_dotenv()


def _normalize_provider(provider: str | None) -> ProviderName:
    value = (provider or os.getenv("LLM_PROVIDER") or "auto").strip().lower()
    if value not in {"auto", "qwen", "openai"}:
        raise ValueError("LLM provider must be one of: auto, qwen, openai")
    return value  # type: ignore[return-value]


def _provider_config(provider: ActiveProviderName) -> ProviderConfig:
    prefix = "QWEN" if provider == "qwen" else "OPENAI"
    api_key = os.getenv(f"{prefix}_API_KEY")
    base_url = os.getenv(f"{prefix}_BASE_URL")
    model_name = os.getenv(f"{prefix}_MODEL_NAME")

    missing = [
        name
        for name, value in {
            f"{prefix}_API_KEY": api_key,
            f"{prefix}_BASE_URL": base_url,
            f"{prefix}_MODEL_NAME": model_name,
        }.items()
        if not value
    ]
    if missing:
        raise LLMError(f"Missing LLM environment variables: {', '.join(missing)}")

    return ProviderConfig(
        provider=provider,
        model_name=str(model_name),
        base_url=str(base_url),
        api_key=str(api_key),
    )


def _client(config: ProviderConfig) -> OpenAI:
    return OpenAI(api_key=config.api_key, base_url=config.base_url)


def _content_from_response(response) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError) as exc:
        raise LLMError("LLM response did not contain message content") from exc

    if not content:
        raise LLMError("LLM response content was empty")
    return content


def _validate_json(content: str, schema: type[ModelT]) -> ModelT:
    try:
        return schema.model_validate_json(content)
    except ValidationError:
        raise
    except ValueError as exc:
        raise LLMError("LLM response was not valid JSON") from exc


def _call_once(
    *,
    prompt: str,
    schema: type[ModelT],
    config: ProviderConfig,
    system_prompt: str,
) -> ModelT:
    response = _client(config).chat.completions.create(
        model=config.model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return _validate_json(_content_from_response(response), schema)


def _repair_prompt(prompt: str, validation_error: Exception) -> str:
    return (
        "Return corrected JSON only. The previous response failed validation.\n"
        f"Validation error: {validation_error}\n"
        "Original request:\n"
        f"{prompt}"
    )


def _complete_with_provider(
    *,
    prompt: str,
    schema: type[ModelT],
    active_provider: ActiveProviderName,
    requested_provider: ProviderName,
    fallback_used: bool,
    system_prompt: str,
) -> LLMCompletion:
    config = _provider_config(active_provider)
    try:
        result = _call_once(
            prompt=prompt,
            schema=schema,
            config=config,
            system_prompt=system_prompt,
        )
    except (LLMError, ValidationError) as first_error:
        result = _call_once(
            prompt=_repair_prompt(prompt, first_error),
            schema=schema,
            config=config,
            system_prompt=system_prompt,
        )

    return LLMCompletion(
        result=result,
        requested_provider=requested_provider,
        active_provider=active_provider,
        fallback_used=fallback_used,
        model_name=config.model_name,
    )


def complete_json_result(
    prompt: str,
    schema: type[ModelT],
    *,
    provider: str | None = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> LLMCompletion:
    """JSON object 응답을 받아 pydantic schema로 검증한다."""
    _load_env()
    requested_provider = _normalize_provider(provider)

    if requested_provider in {"qwen", "openai"}:
        return _complete_with_provider(
            prompt=prompt,
            schema=schema,
            active_provider=requested_provider,
            requested_provider=requested_provider,
            fallback_used=False,
            system_prompt=system_prompt,
        )

    try:
        return _complete_with_provider(
            prompt=prompt,
            schema=schema,
            active_provider="qwen",
            requested_provider=requested_provider,
            fallback_used=False,
            system_prompt=system_prompt,
        )
    except Exception as qwen_error:
        try:
            return _complete_with_provider(
                prompt=prompt,
                schema=schema,
                active_provider="openai",
                requested_provider=requested_provider,
                fallback_used=True,
                system_prompt=system_prompt,
            )
        except Exception as openai_error:
            raise LLMError(
                "LLM auto provider failed for qwen and openai"
            ) from openai_error


def complete_json(
    prompt: str,
    schema: type[ModelT],
    *,
    provider: str | None = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> ModelT:
    """JSON 구조화 출력을 강제해 LLM 호출하고 검증된 pydantic 모델을 반환한다."""
    completion = complete_json_result(
        prompt=prompt,
        schema=schema,
        provider=provider,
        system_prompt=system_prompt,
    )
    return completion.result  # type: ignore[return-value]
