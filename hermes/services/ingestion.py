from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.orm import Session

from hermes.classifier.base import PublicationClassifier
from hermes.collector.base import CollectionItem
from hermes.database.models import ClassificationResultModel, Publication, PublicationVersion, Source
from hermes.parser.base import PublicationParser, ParsedPublication
from hermes.services.hashing import stable_content_hash

IngestionResult = Literal["inserted", "updated", "unchanged"]


class IngestionService:
    def __init__(self, session: Session, parser: PublicationParser, classifier: PublicationClassifier) -> None:
        self.session = session
        self.parser = parser
        self.classifier = classifier

    def ingest(self, item: CollectionItem) -> IngestionResult:
        parsed = self.parser.parse(item)
        source = self._get_or_create_source(parsed)
        content_hash = stable_content_hash(parsed.raw_payload, parsed.raw_text)
        publication = self._find_existing(source.id, parsed, content_hash)
        classification = self.classifier.classify(parsed.clean_text or parsed.raw_text or "", parsed.normalized_payload)

        if publication is None:
            publication = self._build_publication(source.id, parsed, content_hash, classification)
            self.session.add(publication)
            self.session.flush()
            self._add_version(publication, parsed, classification, changed_fields=["created"])
            self._add_classification_result(publication, classification)
            self.session.commit()
            return "inserted"

        if publication.content_hash == content_hash:
            publication.collected_at = datetime.now(UTC)
            self.session.commit()
            return "unchanged"

        changed_fields = self._changed_fields(publication, parsed)
        publication.version += 1
        self._copy_parsed_to_publication(publication, parsed, content_hash, classification)
        self._add_version(publication, parsed, classification, changed_fields=changed_fields)
        self._add_classification_result(publication, classification)
        self.session.commit()
        return "updated"

    def _get_or_create_source(self, parsed: ParsedPublication) -> Source:
        source = self.session.query(Source).filter(Source.code == parsed.source_code).one_or_none()
        if source is not None:
            return source

        source = Source(
            code=parsed.source_code,
            name=parsed.source_name,
            api_name=parsed.api_name,
            enabled=True,
            metadata_json={"created_by": "ingestion_service"},
        )
        self.session.add(source)
        self.session.flush()
        return source

    def _find_existing(self, source_id: int, parsed: ParsedPublication, content_hash: str) -> Publication | None:
        if parsed.external_id:
            existing = (
                self.session.query(Publication)
                .filter(Publication.source_id == source_id, Publication.external_id == parsed.external_id)
                .one_or_none()
            )
            if existing is not None:
                return existing

        return (
            self.session.query(Publication)
            .filter(Publication.source_id == source_id, Publication.content_hash == content_hash)
            .one_or_none()
        )

    def _build_publication(self, source_id: int, parsed: ParsedPublication, content_hash: str, classification) -> Publication:
        publication = Publication(source_id=source_id, content_hash=content_hash, version=1)
        self._copy_parsed_to_publication(publication, parsed, content_hash, classification)
        return publication

    def _copy_parsed_to_publication(self, publication: Publication, parsed: ParsedPublication, content_hash: str, classification) -> None:
        publication.external_id = parsed.external_id
        publication.organization = parsed.organization
        publication.entity = parsed.entity
        publication.state = parsed.state
        publication.municipality = parsed.municipality
        publication.source_name = parsed.source_name
        publication.api_name = parsed.api_name
        publication.publication_type = parsed.publication_type
        publication.object_description = parsed.object_description
        publication.modality = parsed.modality
        publication.situation = parsed.situation
        publication.number = parsed.number
        publication.year = parsed.year
        publication.winner_company_name = parsed.winner_company_name
        publication.winner_cnpj = parsed.winner_cnpj
        publication.estimated_value = parsed.estimated_value
        publication.awarded_value = parsed.awarded_value
        publication.contracted_value = parsed.contracted_value
        publication.addendum_value = parsed.addendum_value
        publication.deadline = parsed.deadline
        publication.validity_start = parsed.validity_start
        publication.validity_end = parsed.validity_end
        publication.published_at = parsed.published_at
        publication.event_date = parsed.event_date
        publication.links = parsed.links
        publication.raw_payload = parsed.raw_payload
        publication.normalized_payload = parsed.normalized_payload
        publication.raw_text = parsed.raw_text
        publication.clean_text = parsed.clean_text
        publication.classification = classification.labels
        publication.tags = classification.tags
        publication.keywords = classification.keywords
        publication.content_hash = content_hash
        publication.collected_at = datetime.now(UTC)

    def _add_version(self, publication: Publication, parsed: ParsedPublication, classification, changed_fields: list[str]) -> None:
        self.session.add(
            PublicationVersion(
                publication_id=publication.id,
                version_number=publication.version,
                content_hash=publication.content_hash,
                raw_payload=parsed.raw_payload,
                normalized_payload=parsed.normalized_payload,
                raw_text=parsed.raw_text,
                clean_text=parsed.clean_text,
                classification=classification.labels,
                changed_fields=changed_fields,
            )
        )

    def _add_classification_result(self, publication: Publication, classification) -> None:
        self.session.add(
            ClassificationResultModel(
                publication_id=publication.id,
                provider=classification.provider,
                model=classification.model,
                labels=classification.labels,
                tags=classification.tags,
                keywords=classification.keywords,
                confidence=classification.confidence,
            )
        )

    def _changed_fields(self, publication: Publication, parsed: ParsedPublication) -> list[str]:
        fields = {
            "raw_payload": parsed.raw_payload,
            "raw_text": parsed.raw_text,
            "clean_text": parsed.clean_text,
            "object": parsed.object_description,
            "situation": parsed.situation,
            "estimated_value": parsed.estimated_value,
            "awarded_value": parsed.awarded_value,
            "contracted_value": parsed.contracted_value,
        }
        changed = [name for name, value in fields.items() if getattr(publication, "object_description" if name == "object" else name) != value]
        return changed or ["content_hash"]
