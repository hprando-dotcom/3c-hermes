from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_TOKEN_URLS = (
    "https://gateway.apilib.prefeitura.sp.gov.br/token",
    "http://gateway.apilib.prefeitura.sp.gov.br/token",
    "https://apilib.prefeitura.sp.gov.br/token",
)

SENSITIVE_KEYS = {"access_token", "refresh_token", "id_token", "client_secret", "consumer_secret"}


class ApilibAuthError(RuntimeError):
    def __init__(self, message: str, attempts: list[AuthAttempt] | None = None) -> None:
        super().__init__(message)
        self.attempts = attempts or []


@dataclass(slots=True)
class ApilibCredentials:
    consumer_key: str
    consumer_secret: str

    @classmethod
    def from_env(cls) -> ApilibCredentials:
        consumer_key = os.getenv("SP_DOE_CONSUMER_KEY")
        consumer_secret = os.getenv("SP_DOE_CONSUMER_SECRET")

        missing = [
            name
            for name, value in (
                ("SP_DOE_CONSUMER_KEY", consumer_key),
                ("SP_DOE_CONSUMER_SECRET", consumer_secret),
            )
            if not value
        ]
        if missing:
            raise ApilibAuthError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(consumer_key=consumer_key or "", consumer_secret=consumer_secret or "")


@dataclass(slots=True)
class ApilibToken:
    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    scope: str | None = None
    token_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def authorization_header(self) -> str:
        return f"{self.token_type} {self.access_token}"

    @property
    def masked_access_token(self) -> str:
        return mask_secret(self.access_token, visible=8)


@dataclass(slots=True)
class AuthAttempt:
    token_url: str
    status_code: int | None
    content_type: str | None
    preview: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 300


@dataclass(slots=True)
class AuthResult:
    token: ApilibToken
    attempts: list[AuthAttempt]


class ApilibAuthenticator:
    def __init__(
        self,
        credentials: ApilibCredentials,
        token_urls: list[str] | tuple[str, ...] | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.credentials = credentials
        self.token_urls = list(token_urls or build_token_url_candidates())
        self.timeout_seconds = timeout_seconds

    def request_token(self) -> AuthResult:
        attempts: list[AuthAttempt] = []

        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            for token_url in self.token_urls:
                try:
                    response = client.post(
                        token_url,
                        data={"grant_type": "client_credentials"},
                        auth=(self.credentials.consumer_key, self.credentials.consumer_secret),
                        headers={"Accept": "application/json"},
                    )
                    preview = safe_preview(response.text)
                    attempt = AuthAttempt(
                        token_url=token_url,
                        status_code=response.status_code,
                        content_type=response.headers.get("content-type"),
                        preview=preview,
                    )
                    attempts.append(attempt)

                    if response.is_success:
                        try:
                            token = parse_token_response(response, token_url)
                            return AuthResult(token=token, attempts=attempts)
                        except ApilibAuthError as exc:
                            attempt.error = str(exc)
                            attempt.preview = safe_preview(response.text)
                except httpx.HTTPError as exc:
                    attempts.append(
                        AuthAttempt(
                            token_url=token_url,
                            status_code=None,
                            content_type=None,
                            preview="",
                            error=f"{exc.__class__.__name__}: {exc}",
                        )
                    )

        raise ApilibAuthError("Unable to obtain APILIB access token with client_credentials.", attempts=attempts)


def build_token_url_candidates() -> list[str]:
    configured = os.getenv("SP_DOE_TOKEN_URL")
    candidates: list[str] = []
    if configured:
        candidates.append(configured)

    for token_url in DEFAULT_TOKEN_URLS:
        if token_url not in candidates:
            candidates.append(token_url)

    return candidates


def parse_token_response(response: httpx.Response, token_url: str) -> ApilibToken:
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise ApilibAuthError(f"Token endpoint returned non-JSON response at {token_url}.") from exc

    access_token = payload.get("access_token")
    if not access_token:
        raise ApilibAuthError(f"Token endpoint did not return access_token at {token_url}.")

    token_type = payload.get("token_type") or "Bearer"
    return ApilibToken(
        access_token=str(access_token),
        token_type=str(token_type),
        expires_in=_as_optional_int(payload.get("expires_in")),
        scope=payload.get("scope"),
        token_url=token_url,
        raw=payload,
    )


def safe_preview(value: str, limit: int = 500) -> str:
    if not value:
        return ""

    redacted = _redact_json_payload(value)
    redacted = re.sub(r'("?(?:access_token|refresh_token|id_token)"?\s*[:=]\s*)("[^"]+"|[^\s,&}]+)', r"\1<redacted>", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1<redacted>", redacted, flags=re.IGNORECASE)
    return redacted[:limit]


def mask_secret(value: str | None, visible: int = 4) -> str:
    if not value:
        return "<empty>"
    if len(value) <= visible * 2:
        return "<redacted>"
    return f"{value[:visible]}...{value[-visible:]}"


def _redact_json_payload(value: str) -> str:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return value

    def redact(item: Any) -> Any:
        if isinstance(item, dict):
            return {
                key: "<redacted>" if key.lower() in SENSITIVE_KEYS else redact(child)
                for key, child in item.items()
            }
        if isinstance(item, list):
            return [redact(child) for child in item]
        return item

    return json.dumps(redact(payload), ensure_ascii=False)


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
