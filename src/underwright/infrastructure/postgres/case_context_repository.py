from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from underwright.domain.case_context_base import BaseCaseContext
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.contract_case_context import ContractCaseContext
from underwright.domain.quote_case_context import QuoteCaseContext


class CaseContextRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def save_case_context(self, context: BaseCaseContext) -> BaseCaseContext:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                if context.case_metadata.case_id is None:
                    # New contexts get a UUID before persistence.
                    context.case_metadata.case_id = uuid4()

                # Persist by case_id: insert when missing, update when present.
                cur.execute(
                    """
                    INSERT INTO case_context (case_id, status, context_json)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (case_id)
                    DO UPDATE SET
                        status = EXCLUDED.status,
                        context_json = EXCLUDED.context_json,
                        updated_at = NOW()
                    RETURNING case_id
                    """,
                    (
                        context.case_metadata.case_id,
                        context.case_metadata.status,
                        Jsonb(context.model_dump(mode="json")),
                    ),
                )
                # Keep the model aligned with the stored row.
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError("Failed to save case context: no row returned from database")

                context.case_metadata.case_id = row[0]
            conn.commit()
        return context

    def get_case_context_by_case_id(self, case_id: UUID | str) -> BaseCaseContext:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                # Stored JSON is the full case context snapshot.
                cur.execute(
                    """
                    SELECT context_json
                    FROM case_context
                    WHERE case_id = %s
                    """,
                    (case_id,)
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(f"CaseContext with case_id {case_id} not found")
                return self._context_from_payload(row[0])

    def get_latest_claim_case_context_by_request_id(
        self,
        request_id: UUID | str,
    ) -> ClaimCaseContext:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT context_json
                    FROM case_context
                    WHERE context_json -> 'case_metadata' ->> 'domain' = 'claims'
                      AND context_json -> 'source_inputs' ->> 'request_id' = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (str(request_id),),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(
                        "ClaimCaseContext with request_id "
                        f"{request_id} not found"
                    )

                context = self._context_from_payload(row[0])
                if not isinstance(context, ClaimCaseContext):
                    raise ValueError(
                        "Latest case context for request_id "
                        f"{request_id} is not a claim context"
                    )
                return context

    def get_latest_claim_case_context_by_evidence_reply_token(
        self,
        reply_token: str,
    ) -> ClaimCaseContext:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT context_json
                    FROM case_context
                    WHERE context_json -> 'case_metadata' ->> 'domain' = 'claims'
                      AND context_json -> 'generated_outputs'
                          -> 'evidence_request_draft'
                          ->> 'reply_token' = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (reply_token,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(
                        "ClaimCaseContext with evidence reply token not found"
                    )

                context = self._context_from_payload(row[0])
                if not isinstance(context, ClaimCaseContext):
                    raise ValueError(
                        "Latest case context for evidence reply token is not "
                        "a claim context"
                    )
                return context

    def _context_from_payload(self, payload: dict) -> BaseCaseContext:
        domain = payload.get("case_metadata", {}).get("domain")
        if domain == "claims":
            return ClaimCaseContext.model_validate(payload)
        if domain == "contracts":
            return ContractCaseContext.model_validate(payload)
        if domain == "quotes":
            return QuoteCaseContext.model_validate(payload)
        return BaseCaseContext.model_validate(payload)

   
