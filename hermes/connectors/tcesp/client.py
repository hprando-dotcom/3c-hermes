from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Any

import httpx


TCE_SP_BASE_URL = "https://transparencia.tce.sp.gov.br/api/json"


class TceSpClientError(RuntimeError):
    pass


@dataclass(slots=True)
class TceSpClient:
    base_url: str = TCE_SP_BASE_URL
    timeout_seconds: float = 30.0
    retries: int = 2

    def fetch_municipios(self) -> list[dict[str, Any]]:
        payload = self._get_json("/municipios")
        return ensure_list(payload, "municipios")

    def fetch_despesas(self, municipio_slug: str, exercicio: int, mes: int) -> list[dict[str, Any]]:
        payload = self._get_json(f"/despesas/{municipio_slug}/{exercicio}/{mes}")
        return ensure_list(payload, "despesas")

    def fetch_receitas(self, municipio_slug: str, exercicio: int, mes: int) -> list[dict[str, Any]]:
        payload = self._get_json(f"/receitas/{municipio_slug}/{exercicio}/{mes}")
        return ensure_list(payload, "receitas")

    def _get_json(self, path: str) -> Any:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                    response = client.get(url, headers={"Accept": "application/json", "User-Agent": "HERMES/0.1"})
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < self.retries:
                    sleep(0.5 * (attempt + 1))
                    continue
        raise TceSpClientError(f"Failed to fetch TCE-SP URL {url}: {last_error}")


def ensure_list(payload: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise TceSpClientError(f"TCE-SP {label} response is not a list.")
    return [item for item in payload if isinstance(item, dict)]
