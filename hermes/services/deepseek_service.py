from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_FAST_MODEL = "deepseek-v4-flash"
DEFAULT_REPORT_MODEL = "deepseek-v4-pro"


@dataclass(slots=True)
class DeepSeekResult:
    ok: bool
    used_deepseek: bool
    data: Any = None
    error: str | None = None
    model: str | None = None


class DeepSeekService:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_fast: str | None = None,
        model_report: str | None = None,
        timeout_seconds: float = 20.0,
        max_chars: int = 6000,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY")
        self.base_url = (base_url or os.getenv("DEEPSEEK_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model_fast = model_fast or os.getenv("DEEPSEEK_MODEL_FAST") or DEFAULT_FAST_MODEL
        self.model_report = model_report or os.getenv("DEEPSEEK_MODEL_REPORT") or self.model_fast or DEFAULT_REPORT_MODEL
        self.timeout_seconds = timeout_seconds
        self.max_chars = max_chars
        self.calls = 0
        self.failures = 0

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def expand_mission_terms(self, mission_text: str) -> DeepSeekResult:
        if not self.available:
            return DeepSeekResult(ok=False, used_deepseek=False, error="DEEPSEEK_API_KEY ausente.")
        schema = {
            "termos_principais": ["..."],
            "termos_expandidos": ["..."],
            "tipos_evento_interesse": ["..."],
            "natureza_objeto_interesse": ["..."],
            "periodo_identificado": None,
            "query_humana_resumida": "...",
        }
        prompt = (
            "Transforme a missao do usuario em JSON estrito para busca em Diario Oficial. "
            f"Use exatamente estas chaves: {json.dumps(schema, ensure_ascii=False)}\n"
            f"Missao: {mission_text[:1500]}"
        )
        return self._chat_json(prompt, model=self.model_fast)

    def classify_publication_snippet(self, snippet: str, mission_context: dict[str, Any]) -> DeepSeekResult:
        if not self.available:
            return DeepSeekResult(ok=False, used_deepseek=False, error="DEEPSEEK_API_KEY ausente.")
        schema = {
            "relevant": True,
            "relevance_score": 0,
            "event_type": "contrato",
            "natureza_objeto": "obras_engenharia",
            "agency": None,
            "company_name": None,
            "process_number": None,
            "contract_number": None,
            "value_text": None,
            "object_text": None,
            "summary": "...",
            "reason": "...",
            "matched_terms": ["..."],
        }
        prompt = (
            "Classifique o trecho de Diario Oficial em JSON estrito. Nao invente dados ausentes. "
            f"Use exatamente estas chaves: {json.dumps(schema, ensure_ascii=False)}\n"
            f"Contexto da missao: {json.dumps(mission_context, ensure_ascii=False, default=str)[:2500]}\n"
            f"Trecho:\n{snippet[: self.max_chars]}"
        )
        return self._chat_json(prompt, model=self.model_fast)

    def build_investigation_report(self, report_input: dict[str, Any]) -> DeepSeekResult:
        if not self.available:
            return DeepSeekResult(ok=False, used_deepseek=False, error="DEEPSEEK_API_KEY ausente.")
        prompt = (
            "Escreva um relatorio executivo em Markdown para uma investigacao de Diario Oficial. "
            "Nao invente dados. Use apenas achados, evidencias e limitacoes fornecidos. "
            "Preserve links e numeros. Estruture em secoes claras.\n"
            f"Dados: {json.dumps(report_input, ensure_ascii=False, default=str)[: self.max_chars]}"
        )
        return self._chat_text(prompt, model=self.model_report)

    def _chat_json(self, prompt: str, *, model: str) -> DeepSeekResult:
        text_result = self._chat_text(prompt, model=model, response_format={"type": "json_object"})
        if not text_result.ok:
            return text_result
        try:
            return DeepSeekResult(
                ok=True,
                used_deepseek=True,
                data=parse_json_object(str(text_result.data)),
                model=text_result.model,
            )
        except ValueError as exc:
            self.failures += 1
            return DeepSeekResult(ok=False, used_deepseek=True, error=f"JSON invalido: {exc}", model=model)

    def _chat_text(self, prompt: str, *, model: str, response_format: dict[str, Any] | None = None) -> DeepSeekResult:
        if not self.available:
            return DeepSeekResult(ok=False, used_deepseek=False, error="DEEPSEEK_API_KEY ausente.", model=model)
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Voce e o HERMES, analista de publicacoes oficiais. Seja preciso e cite apenas evidencias fornecidas."},
                {"role": "user", "content": prompt[: self.max_chars]},
            ],
            "temperature": 0.1,
        }
        if response_format:
            payload["response_format"] = response_format
        try:
            self.calls += 1
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            return DeepSeekResult(ok=True, used_deepseek=True, data=content, model=model)
        except Exception as exc:
            self.failures += 1
            return DeepSeekResult(ok=False, used_deepseek=True, error=f"{exc.__class__.__name__}: {exc}", model=model)


def parse_json_object(value: str) -> dict[str, Any]:
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        text = match.group(0)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("resposta nao e objeto JSON")
    return parsed


def expand_mission_terms(mission_text: str) -> dict[str, Any]:
    result = DeepSeekService().expand_mission_terms(mission_text)
    return result.data if result.ok and isinstance(result.data, dict) else {}


def classify_publication_snippet(snippet: str, mission_context: dict[str, Any]) -> dict[str, Any]:
    result = DeepSeekService().classify_publication_snippet(snippet, mission_context)
    return result.data if result.ok and isinstance(result.data, dict) else {}


def build_investigation_report(report_input: dict[str, Any]) -> str:
    result = DeepSeekService().build_investigation_report(report_input)
    return str(result.data) if result.ok else ""
