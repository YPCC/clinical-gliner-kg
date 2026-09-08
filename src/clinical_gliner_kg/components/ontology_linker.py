"""Terminology linking and ontology domain-range validation."""

from __future__ import annotations

import json
from pathlib import Path

from clinical_gliner_kg.components.oak_grounder import OaklibGrounder
from clinical_gliner_kg.models import ClinicalEntity, ClinicalRelation, TerminologyLink, ValidationStatus

DEFAULT_RULES = {
    "allowed_relations": {
        "TREATS": [{"subject": "Medication", "object": "Condition"}],
        "HAS_CONDITION": [{"subject": "Patient", "object": "Condition"}],
        "TAKES": [{"subject": "Patient", "object": "Medication"}],
        "HAS_VALUE": [{"subject": "Laboratory_Test", "object": "Laboratory_Result"}],
        "INDICATES": [
            {"subject": "Laboratory_Result", "object": "Condition"},
            {"subject": "Laboratory_Test", "object": "Condition"},
        ],
        "CID": [
            {"subject": "Chemical", "object": "Disease"},
            {"subject": "Chemical", "object": "Condition"},
            {"subject": "Medication", "object": "Disease"},
            {"subject": "Medication", "object": "Condition"},
        ],
        "PERFORMED": [{"subject": "Provider", "object": "Procedure"}],
        "HAS_ANATOMICAL_SITE": [
            {"subject": "Condition", "object": "Anatomy"},
            {"subject": "Procedure", "object": "Anatomy"},
        ],
    },
    "forbidden_domain_range": [
        {"subject": "Medication", "relation": "HAS_ANATOMICAL_SITE", "object": "Anatomy"}
    ],
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


class OntologyValidationEngine:
    def __init__(
        self,
        rules_path: Path | None = None,
        catalog_path: Path | None = None,
        oak_selectors: list[str] | None = None,
        oak_mode: str = "local",
        oak_eager: bool = False,
        bioportal_token_env: str = "BIOPORTAL_API_KEY",
    ) -> None:
        root = _repo_root()
        self.rules = self._load_json(rules_path or root / "config" / "ontology_rules.json", DEFAULT_RULES)
        raw_catalog = self._load_json(catalog_path or root / "config" / "terminology_catalog.json", {})
        self.catalog: dict[str, TerminologyLink] = {
            key.lower(): TerminologyLink(**value) if isinstance(value, dict) else value
            for key, value in raw_catalog.items()
        }
        oak_kwargs: dict = {"mode": oak_mode, "eager": oak_eager, "bioportal_token_env": bioportal_token_env}
        if oak_selectors:
            oak_kwargs["selectors"] = oak_selectors
        self.oak = OaklibGrounder(**oak_kwargs)

    @staticmethod
    def _load_json(path: Path, fallback: dict) -> dict:
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                return json.load(handle)
        return fallback

    def link_entity(self, entity: ClinicalEntity) -> ClinicalEntity:
        if entity.is_phi:
            return entity
        key = entity.text.strip().lower()
        if key in self.catalog:
            entity.terminology = self.catalog[key]
            if entity.terminology and not entity.terminology.method:
                entity.terminology.method = "catalog"
            entity.linking_confidence = float(entity.terminology.match_score or 1.0)
            entity.validation_status = ValidationStatus.LINKED
            return entity
        for name, link in self.catalog.items():
            if name in key or key in name:
                entity.terminology = link.model_copy() if hasattr(link, "model_copy") else link
                if entity.terminology and not entity.terminology.method:
                    entity.terminology.method = "catalog-partial"
                entity.linking_confidence = min(0.85, float(getattr(entity.terminology, "match_score", 0.7) or 0.7))
                entity.validation_status = ValidationStatus.LINKED
                return entity
        if self.oak.enabled():
            grounded = self.oak.ground(entity)
            if grounded.terminology:
                grounded.linking_confidence = float(grounded.terminology.match_score or 0.7)
                grounded.validation_status = ValidationStatus.LINKED
                return grounded
            grounded.validation_status = ValidationStatus.UNLINKED
            return grounded
        entity.validation_status = ValidationStatus.UNLINKED
        return entity

    def validate_relation(
        self,
        rel: ClinicalRelation,
        entity_map: dict[str, ClinicalEntity],
    ) -> tuple[bool, str]:
        subj = entity_map.get(rel.subject_id)
        obj = entity_map.get(rel.object_id)
        if not subj or not obj:
            return False, "Orphan relation: missing subject or object"

        for forbidden in self.rules.get("forbidden_domain_range", []):
            if (
                forbidden["subject"] == subj.label
                and forbidden["relation"] == rel.relation
                and forbidden["object"] == obj.label
            ):
                return False, (
                    f"Ontology violation: {subj.label} cannot have relation "
                    f"{rel.relation} to {obj.label}"
                )

        allowed = self.rules.get("allowed_relations", {}).get(rel.relation, [])
        for pattern in allowed:
            if pattern["subject"] == subj.label and pattern["object"] == obj.label:
                return True, "Valid domain-range alignment"
        return False, f"Unregistered relation pair ({subj.label} -[{rel.relation}]-> {obj.label})"
