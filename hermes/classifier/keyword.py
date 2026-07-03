from __future__ import annotations

from decimal import Decimal

from hermes.classifier.base import ClassificationResult, PublicationClassifier

ENGINEERING_KEYWORDS = {
    "obras_publicas": ["obra", "execucao", "reforma", "construcao", "infraestrutura"],
    "rodovias": ["rodovia", "pavimentacao", "sinalizacao", "terraplenagem"],
    "saneamento": ["saneamento", "drenagem", "esgoto", "agua"],
    "estruturas": ["ponte", "viaduto", "tunel", "barragem", "contencao"],
    "transportes": ["aeroporto", "ferrovia", "hidrovia"],
    "energia": ["energia", "subestacao", "linha de transmissao"],
    "maquinas": ["equipamento pesado", "locacao de maquina", "maquinas"],
}


class KeywordEngineeringClassifier(PublicationClassifier):
    provider = "keyword"

    def classify(self, text: str, metadata: dict[str, object] | None = None) -> ClassificationResult:
        normalized = text.casefold()
        tags: list[str] = []
        keywords: list[str] = []

        for tag, terms in ENGINEERING_KEYWORDS.items():
            matched = [term for term in terms if term in normalized]
            if matched:
                tags.append(tag)
                keywords.extend(matched)

        confidence = Decimal("0.50") if tags else Decimal("0.10")
        return ClassificationResult(
            provider=self.provider,
            labels={"domain": "engineering", "matched": bool(tags)},
            tags=sorted(set(tags)),
            keywords=sorted(set(keywords)),
            confidence=confidence,
            model="keyword-rules-v1",
        )

