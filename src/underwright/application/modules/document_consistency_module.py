from __future__ import annotations

from typing import Any

from underwright.domain.claim_analysis import (
    ClaimReviewFindings,
    DocumentConsistencyResult,
    DocumentDiscrepancy,
    DocumentSupportingFact,
    ExtractedClaimDocument,
    ExtractedDocumentBundle,
    ReviewFindingSeverity,
)
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.module_result import ModuleResult


class DocumentConsistencyModule:
    """Compares claim intake fields with already-extracted document facts."""

    module_name = "DocumentConsistencyModule"

    def evaluate(self, case_context: ClaimCaseContext) -> ModuleResult:
        claim_request = self._object(case_context.reference_data.claim_request)
        claim_data = self._object(claim_request.get("claim_data"))
        client_profile = self._object(case_context.reference_data.client_profile)
        client_data = self._object(claim_request.get("client_data")) or client_profile
        documents = self._documents_by_type(
            case_context.reference_data.extracted_documents
        )

        supporting_facts: list[DocumentSupportingFact] = []
        discrepancies: list[DocumentDiscrepancy] = []
        if not documents:
            result = DocumentConsistencyResult(status="insufficient_document_data")
            self._attach_result(case_context, result)
            return ModuleResult(
                module_name=self.module_name,
                status="success",
                summary=(
                    "No extracted document data was available for consistency checks."
                ),
                source_fields_used=[
                    "reference_data.claim_request",
                    "reference_data.extracted_documents",
                ],
            )

        self._check_policy_number(
            claim_data,
            documents,
            supporting_facts,
            discrepancies,
        )
        self._check_property_address(
            claim_data,
            documents,
            supporting_facts,
            discrepancies,
        )
        self._check_full_name(
            claim_data,
            client_data,
            documents,
            supporting_facts,
            discrepancies,
        )
        self._check_incident_type(
            claim_data,
            documents,
            supporting_facts,
            discrepancies,
        )
        self._check_estimated_damage(
            claim_data,
            documents,
            supporting_facts,
            discrepancies,
        )

        if discrepancies:
            status = "discrepancies_found"
        elif supporting_facts:
            status = "no_discrepancies"
        else:
            status = "insufficient_document_data"

        result = DocumentConsistencyResult(
            status=status,
            supporting_facts=supporting_facts,
            discrepancies=discrepancies,
        )
        self._attach_result(case_context, result)
        return ModuleResult(
            module_name=self.module_name,
            status="success",
            summary=f"Document consistency check completed with status {status}.",
            source_fields_used=[
                "reference_data.claim_request",
                "reference_data.client_profile",
                "reference_data.extracted_documents",
            ],
        )

    def _check_policy_number(
        self,
        claim_data: dict[str, Any],
        documents: dict[str, list[ExtractedClaimDocument]],
        supporting_facts: list[DocumentSupportingFact],
        discrepancies: list[DocumentDiscrepancy],
    ) -> None:
        policy_document = self._first(documents, "policy_document")
        if policy_document is None:
            return
        self._compare_text(
            field="policy_number",
            claim_value=claim_data.get("policy_number"),
            document_value=policy_document.extracted_fields.get("policy_number"),
            source_document=policy_document.filename,
            supporting_facts=supporting_facts,
            discrepancies=discrepancies,
            mismatch_severity="high",
            match_message="Claim policy number matches the policy document.",
            mismatch_message="Claim policy number differs from the policy document.",
        )

    def _check_property_address(
        self,
        claim_data: dict[str, Any],
        documents: dict[str, list[ExtractedClaimDocument]],
        supporting_facts: list[DocumentSupportingFact],
        discrepancies: list[DocumentDiscrepancy],
    ) -> None:
        comparisons = [
            (
                self._first(documents, "policy_document"),
                "insured_address",
                "Claim property address matches the policy document.",
                "Claim property address differs from the policy document.",
            ),
            (
                self._first(documents, "land_registry_extract"),
                "property_address",
                "Claim property address matches the land registry extract.",
                "Claim property address differs from the land registry extract.",
            ),
            (
                self._first(documents, "property_ownership"),
                "property_address",
                "Claim property address matches the ownership document.",
                "Claim property address differs from the ownership document.",
            ),
        ]
        for document, field_name, match_message, mismatch_message in comparisons:
            if document is None:
                continue
            self._compare_text(
                field="property_address",
                claim_value=claim_data.get("property_address"),
                document_value=self._first_field(
                    document,
                    [field_name, "insured_property_address"],
                ),
                source_document=document.filename,
                supporting_facts=supporting_facts,
                discrepancies=discrepancies,
                mismatch_severity="high",
                match_message=match_message,
                mismatch_message=mismatch_message,
            )

    def _check_full_name(
        self,
        claim_data: dict[str, Any],
        client_data: dict[str, Any],
        documents: dict[str, list[ExtractedClaimDocument]],
        supporting_facts: list[DocumentSupportingFact],
        discrepancies: list[DocumentDiscrepancy],
    ) -> None:
        claim_name = (
            claim_data.get("full_name")
            or client_data.get("full_name")
            or client_data.get("name")
        )
        comparisons = [
            (
                self._first(documents, "id_document"),
                ["full_name", "document_holder_name"],
                "Claimant name matches the identity document.",
                "Claimant name differs from the identity document.",
            ),
            (
                self._first(documents, "property_ownership"),
                ["owner_name"],
                "Claimant name matches the ownership document.",
                "Claimant name differs from the ownership document.",
            ),
        ]
        for document, field_names, match_message, mismatch_message in comparisons:
            if document is None:
                continue
            self._compare_text(
                field="full_name",
                claim_value=claim_name,
                document_value=self._first_field(document, field_names),
                source_document=document.filename,
                supporting_facts=supporting_facts,
                discrepancies=discrepancies,
                mismatch_severity="medium",
                match_message=match_message,
                mismatch_message=mismatch_message,
            )

    def _check_incident_type(
        self,
        claim_data: dict[str, Any],
        documents: dict[str, list[ExtractedClaimDocument]],
        supporting_facts: list[DocumentSupportingFact],
        discrepancies: list[DocumentDiscrepancy],
    ) -> None:
        incident_photos = self._first(documents, "incident_photos")
        if incident_photos is None:
            return
        self._compare_text(
            field="incident_type",
            claim_value=(
                claim_data.get("incident_type") or claim_data.get("claim_type")
            ),
            document_value=incident_photos.extracted_fields.get("damage_type"),
            source_document=incident_photos.filename,
            supporting_facts=supporting_facts,
            discrepancies=discrepancies,
            mismatch_severity="warning",
            match_message="Incident photos support the reported incident type.",
            mismatch_message=(
                "Incident photo damage type differs from the claim incident type."
            ),
            allow_contains=True,
        )

    def _check_estimated_damage(
        self,
        claim_data: dict[str, Any],
        documents: dict[str, list[ExtractedClaimDocument]],
        supporting_facts: list[DocumentSupportingFact],
        discrepancies: list[DocumentDiscrepancy],
    ) -> None:
        policy_document = self._first(documents, "policy_document")
        if policy_document is None:
            return
        estimated_damage = self._number(claim_data.get("estimated_damage"))
        coverage_limit = self._number(
            self._first_field(
                policy_document,
                ["coverage_limit", "coverage_amount", "limit_of_indemnity"],
            )
        )
        if estimated_damage is None or coverage_limit is None or coverage_limit <= 0:
            return

        ratio = estimated_damage / coverage_limit
        if estimated_damage > coverage_limit:
            discrepancies.append(
                DocumentDiscrepancy(
                    field="estimated_damage",
                    claim_value=estimated_damage,
                    document_value=coverage_limit,
                    source_document=policy_document.filename,
                    severity="high",
                    message="Estimated damage exceeds the policy coverage limit.",
                )
            )
        elif ratio >= 0.8:
            discrepancies.append(
                DocumentDiscrepancy(
                    field="estimated_damage",
                    claim_value=estimated_damage,
                    document_value=coverage_limit,
                    source_document=policy_document.filename,
                    severity="warning",
                    message="Estimated damage is high relative to the coverage limit.",
                )
            )
        else:
            supporting_facts.append(
                DocumentSupportingFact(
                    field="estimated_damage",
                    claim_value=estimated_damage,
                    document_value=coverage_limit,
                    source_document=policy_document.filename,
                    severity="info",
                    message="Estimated damage is within the policy coverage limit.",
                )
            )

    def _compare_text(
        self,
        *,
        field: str,
        claim_value: Any,
        document_value: Any,
        source_document: str,
        supporting_facts: list[DocumentSupportingFact],
        discrepancies: list[DocumentDiscrepancy],
        mismatch_severity: ReviewFindingSeverity,
        match_message: str,
        mismatch_message: str,
        allow_contains: bool = False,
    ) -> None:
        if not self._has_value(claim_value) or not self._has_value(document_value):
            return
        if self._values_match(claim_value, document_value, allow_contains):
            supporting_facts.append(
                DocumentSupportingFact(
                    field=field,
                    claim_value=claim_value,
                    document_value=document_value,
                    source_document=source_document,
                    severity="info",
                    message=match_message,
                )
            )
            return
        discrepancies.append(
            DocumentDiscrepancy(
                field=field,
                claim_value=claim_value,
                document_value=document_value,
                source_document=source_document,
                severity=mismatch_severity,
                message=mismatch_message,
            )
        )

    def _attach_result(
        self,
        case_context: ClaimCaseContext,
        result: DocumentConsistencyResult,
    ) -> None:
        case_context.generated_outputs.document_consistency = result
        findings = (
            case_context.generated_outputs.claim_review.findings
            or ClaimReviewFindings()
        )
        findings.document_consistency = result
        case_context.generated_outputs.claim_review.findings = findings

    def _documents_by_type(
        self,
        bundle: ExtractedDocumentBundle,
    ) -> dict[str, list[ExtractedClaimDocument]]:
        documents: dict[str, list[ExtractedClaimDocument]] = {}
        for document in bundle.documents:
            documents.setdefault(document.document_type, []).append(document)
        return documents

    def _first(
        self,
        documents: dict[str, list[ExtractedClaimDocument]],
        document_type: str,
    ) -> ExtractedClaimDocument | None:
        matching_documents = documents.get(document_type) or []
        return matching_documents[0] if matching_documents else None

    def _first_field(
        self,
        document: ExtractedClaimDocument,
        field_names: list[str],
    ) -> Any:
        for field_name in field_names:
            value = document.extracted_fields.get(field_name)
            if self._has_value(value):
                return value
        return None

    def _values_match(
        self,
        claim_value: Any,
        document_value: Any,
        allow_contains: bool,
    ) -> bool:
        normalized_claim_value = self._normalize_text(claim_value)
        normalized_document_value = self._normalize_text(document_value)
        if normalized_claim_value == normalized_document_value:
            return True
        if not allow_contains:
            return False
        return (
            normalized_claim_value in normalized_document_value
            or normalized_document_value in normalized_claim_value
        )

    def _normalize_text(self, value: Any) -> str:
        normalized = str(value or "").strip().lower().replace(",", " ")
        return " ".join(normalized.split())

    def _object(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _number(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _has_value(self, value: Any) -> bool:
        return value is not None and value != "" and value != [] and value != {}


__all__ = ["DocumentConsistencyModule"]
