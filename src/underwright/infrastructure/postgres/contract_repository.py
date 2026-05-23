from __future__ import annotations

from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from underwright.application.ports import ContractSourceQuoteConflictError
from underwright.domain.contract_lifecycle import (
    AddressSnapshot,
    ContractAssetSummary,
    ContractCreationData,
    ContractCustomerSummary,
    ContractPricingSummary,
    ContractReadModel,
)
from underwright.domain.models import (
    Address,
    Contract,
    ContractContextSource,
    Customer,
    InsuredAsset,
    Insurer,
    InsurerContextSource,
    Pricing,
    RiskFactor,
    RiskProfile,
)
from underwright.infrastructure.postgres.repository_base import PostgresRepositoryMixin


class PostgresContractRepository(PostgresRepositoryMixin):
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def list_contracts(self) -> list[ContractReadModel]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    {self._contract_read_model_select()}
                    ORDER BY c.created_at DESC, c.id DESC
                    """
                )
                return [self._contract_read_model(row) for row in cur.fetchall()]

    def list_claimable_contracts_by_client_id(
        self,
        client_id: int | str | UUID,
        claimable_statuses: set[str],
    ) -> list[ContractReadModel]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    {self._contract_read_model_select()}
                    WHERE {self._client_ownership_clause()}
                      AND c.status = ANY(%s::text[])
                      AND c.expiration_date >= CURRENT_DATE
                    ORDER BY c.effective_date DESC, c.created_at DESC, c.id DESC
                    """,
                    (client_id, client_id, list(claimable_statuses)),
                )
                return [self._contract_read_model(row) for row in cur.fetchall()]

    def list_contracts_by_client_id(
        self,
        client_id: int | str | UUID,
    ) -> list[ContractReadModel]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    {self._contract_read_model_select()}
                    WHERE {self._client_ownership_clause()}
                    ORDER BY c.created_at DESC, c.id DESC
                    """,
                    (client_id, client_id),
                )
                return [self._contract_read_model(row) for row in cur.fetchall()]

    def get_contract_by_id_for_client(
        self,
        contract_id: UUID,
        client_id: int | str | UUID,
    ) -> ContractReadModel:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    {self._contract_read_model_select()}
                    WHERE c.id = %s
                      AND {self._client_ownership_clause()}
                    """,
                    (contract_id, client_id, client_id),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError("Contract not found")
                return self._contract_read_model(row)

    def get_claimable_contract_by_id_for_client(
        self,
        contract_id: UUID,
        client_id: int | str | UUID,
        claimable_statuses: set[str],
    ) -> ContractReadModel:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    {self._contract_read_model_select()}
                    WHERE c.id = %s
                      AND {self._client_ownership_clause()}
                      AND c.status = ANY(%s::text[])
                      AND c.expiration_date >= CURRENT_DATE
                    """,
                    (contract_id, client_id, client_id, list(claimable_statuses)),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError("Claimable contract not found")
                return self._contract_read_model(row)

    def get_contract_by_id(self, contract_id: UUID) -> ContractReadModel:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    {self._contract_read_model_select()}
                    WHERE c.id = %s
                    """,
                    (contract_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError("Contract not found")
                return self._contract_read_model(row)

    def get_contract_by_source_quote_request_id(
        self,
        quote_request_id: UUID,
    ) -> ContractReadModel | None:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    {self._contract_read_model_select()}
                    WHERE c.source_quote_request_id = %s
                    """,
                    (quote_request_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return self._contract_read_model(row)

    def mark_contract_issued_for_quote_acceptance(
        self,
        quote_request_id: UUID,
        quote_acceptance_id: int,
    ) -> ContractReadModel | None:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE contract
                    SET
                        source_quote_acceptance_id = %s,
                        status = 'issued',
                        updated_at = NOW()
                    WHERE source_quote_request_id = %s
                      AND status <> 'declined'
                    """,
                    (quote_acceptance_id, quote_request_id),
                )
                cur.execute(
                    f"""
                    {self._contract_read_model_select()}
                    WHERE c.source_quote_request_id = %s
                    """,
                    (quote_request_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return self._contract_read_model(row)

    def mark_contract_declined(
        self,
        contract_id: UUID,
    ) -> ContractReadModel | None:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE contract
                    SET
                        status = 'declined',
                        updated_at = NOW()
                    WHERE id = %s
                      AND status = 'generated'
                    """,
                    (contract_id,),
                )
                cur.execute(
                    f"""
                    {self._contract_read_model_select()}
                    WHERE c.id = %s
                    """,
                    (contract_id,),
                )
                row = cur.fetchone()
                conn.commit()
                if row is None:
                    return None
                return self._contract_read_model(row)

    def create_contract_from_quote_data(
        self,
        creation_data: ContractCreationData,
    ) -> ContractReadModel:
        if creation_data.source_quote_request_id is None:
            raise ValueError("source_quote_request_id is required")
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                self._ensure_source_quote_document_matches(
                    cur,
                    creation_data.source_quote_request_id,
                    creation_data.source_quote_document_id,
                )
                insurer_id = self._default_insurer_id(cur)
                customer_address_id = self._insert_address(
                    cur,
                    creation_data.customer_address,
                )
                cur.execute(
                    """
                    INSERT INTO customer (
                        type,
                        full_name,
                        national_id,
                        company_id,
                        email,
                        phone,
                        address_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        creation_data.customer_type,
                        creation_data.customer_full_name,
                        creation_data.customer_national_id,
                        creation_data.customer_company_id,
                        creation_data.customer_email,
                        creation_data.customer_phone,
                        customer_address_id,
                    ),
                )
                customer_row = cur.fetchone()
                if customer_row is None:
                    raise ValueError("Customer was not saved")
                customer_id = customer_row["id"]

                asset_address_id = self._insert_address(
                    cur,
                    creation_data.asset_address,
                )
                cur.execute(
                    """
                    INSERT INTO insured_asset (
                        customer_id,
                        asset_type,
                        usage_type,
                        construction_type,
                        year_built,
                        floor,
                        area_sqm,
                        declared_value,
                        occupancy,
                        previous_claims_count,
                        address_id,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                    RETURNING id
                    """,
                    (
                        customer_id,
                        creation_data.asset_type,
                        creation_data.usage_type,
                        creation_data.construction_type,
                        creation_data.year_built,
                        creation_data.floor,
                        creation_data.area_sqm,
                        creation_data.declared_value,
                        creation_data.occupancy,
                        creation_data.previous_claims_count,
                        asset_address_id,
                        creation_data.created_at,
                        creation_data.updated_at,
                    ),
                )
                asset_row = cur.fetchone()
                if asset_row is None:
                    raise ValueError("InsuredAsset was not saved")
                insured_asset_id = asset_row["id"]

                cur.execute(
                    """
                    INSERT INTO contract (
                        id,
                        contract_number,
                        document_type,
                        document_version,
                        insurer_id,
                        customer_id,
                        insured_asset_id,
                        issue_date,
                        effective_date,
                        expiration_date,
                        jurisdiction,
                        governing_law,
                        currency,
                        status,
                        source_quote_request_id,
                        source_quote_document_id,
                        source_quote_acceptance_id,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (source_quote_request_id) DO NOTHING
                    RETURNING id
                    """,
                    (
                        creation_data.id,
                        creation_data.contract_number,
                        creation_data.document_type,
                        creation_data.document_version,
                        insurer_id,
                        customer_id,
                        insured_asset_id,
                        creation_data.issue_date,
                        creation_data.effective_date,
                        creation_data.expiration_date,
                        creation_data.jurisdiction,
                        creation_data.governing_law,
                        creation_data.currency,
                        creation_data.status,
                        creation_data.source_quote_request_id,
                        creation_data.source_quote_document_id,
                        creation_data.source_quote_acceptance_id,
                        creation_data.created_at,
                        creation_data.updated_at,
                    ),
                )
                if cur.fetchone() is None:
                    cur.execute(
                        f"""
                        {self._contract_read_model_select()}
                        WHERE c.source_quote_request_id = %s
                        """,
                        (creation_data.source_quote_request_id,),
                    )
                    existing_row = cur.fetchone()
                    conn.rollback()
                    if existing_row is not None:
                        raise ContractSourceQuoteConflictError(
                            creation_data.source_quote_request_id
                        )
                    raise ValueError("Contract was not saved")

                cur.execute(
                    """
                    INSERT INTO risk_profile (
                        contract_id,
                        overall_risk_level,
                        risk_score,
                        assessment_date,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        creation_data.id,
                        creation_data.overall_risk_level,
                        creation_data.risk_score,
                        creation_data.issue_date,
                        creation_data.created_at,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO pricing (
                        contract_id,
                        base_premium_ron,
                        adjustments_json,
                        final_premium_ron,
                        payment_plan_type,
                        installments
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        creation_data.id,
                        creation_data.base_premium_ron,
                        Jsonb(creation_data.pricing_adjustments),
                        creation_data.final_premium_ron,
                        creation_data.payment_plan_type,
                        creation_data.installments,
                    ),
                )
                cur.execute(
                    f"""
                    {self._contract_read_model_select()}
                    WHERE c.id = %s
                    """,
                    (creation_data.id,),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("Contract not found after creation")
        return self._contract_read_model(row)

    def has_default_insurer(self) -> bool:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT id FROM insurer ORDER BY id ASC LIMIT 1")
                return cur.fetchone() is not None

    def get_default_insurer_context_source(self) -> InsurerContextSource:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                insurer = self._fetch_one(
                    cur,
                    "SELECT * FROM insurer ORDER BY id ASC LIMIT 1",
                    (),
                    Insurer,
                    "Default insurer not found",
                )
                insurer_address = self._fetch_one(
                    cur,
                    "SELECT * FROM address WHERE id = %s",
                    (insurer.address_id,),
                    Address,
                    "Default insurer address not found",
                )
                return InsurerContextSource(
                    insurer=insurer,
                    insurer_address=insurer_address,
                )

    def _ensure_source_quote_document_matches(
        self,
        cur,
        source_quote_request_id: UUID,
        source_quote_document_id: int,
    ) -> None:
        cur.execute(
            """
            SELECT quote_request_id
            FROM quote_document
            WHERE id = %s
            """,
            (source_quote_document_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("source_quote_document_id was not found")
        if str(row["quote_request_id"]) != str(source_quote_request_id):
            raise ValueError(
                "source_quote_document_id must belong to source_quote_request_id"
            )

    def get_contract_context_source(self, contract_id: UUID) -> ContractContextSource:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                contract = self._fetch_one(
                    cur,
                    "SELECT * FROM contract WHERE id = %s",
                    (contract_id,),
                    Contract,
                )
                customer = self._fetch_one(
                    cur,
                    "SELECT * FROM customer WHERE id = %s",
                    (contract.customer_id,),
                    Customer,
                )
                customer_address = self._fetch_one(
                    cur,
                    "SELECT * FROM address WHERE id = %s",
                    (customer.address_id,),
                    Address,
                )

                insurer = self._fetch_one(
                    cur,
                    "SELECT * FROM insurer WHERE id = %s",
                    (contract.insurer_id,),
                    Insurer,
                )
                insurer_address = self._fetch_one(
                    cur,
                    "SELECT * FROM address WHERE id = %s",
                    (insurer.address_id,),
                    Address,
                )

                insured_asset = self._fetch_one(
                    cur,
                    "SELECT * FROM insured_asset WHERE id = %s",
                    (contract.insured_asset_id,),
                    InsuredAsset,
                )
                insured_asset_address = self._fetch_one(
                    cur,
                    "SELECT * FROM address WHERE id = %s",
                    (insured_asset.address_id,),
                    Address,
                )

                risk_profile = self._fetch_one(
                    cur,
                    """
                      SELECT * FROM risk_profile
                      WHERE contract_id = %s
                      ORDER BY assessment_date DESC, id DESC
                      LIMIT 1
                      """,
                    (contract.id,),
                    RiskProfile,
                )

                risk_factors = self._fetch_many(
                    cur,
                    """
                      SELECT * FROM risk_factor
                      WHERE risk_profile_id = %s
                      ORDER BY id ASC
                      """,
                    (risk_profile.id,),
                    RiskFactor,
                )

                pricing = self._fetch_one(
                    cur,
                    """
                      SELECT * FROM pricing
                      WHERE contract_id = %s
                      ORDER BY id DESC
                      LIMIT 1
                      """,
                    (contract.id,),
                    Pricing,
                )

                return ContractContextSource(
                    contract=contract,
                    customer=customer,
                    customer_address=customer_address,
                    insurer=insurer,
                    insurer_address=insurer_address,
                    insured_asset=insured_asset,
                    insured_asset_address=insured_asset_address,
                    risk_profile=risk_profile,
                    risk_factors=risk_factors,
                    pricing=pricing,
                )

    def _default_insurer_id(self, cur) -> int:
        cur.execute("SELECT id FROM insurer ORDER BY id ASC LIMIT 1")
        row = cur.fetchone()
        if row is None:
            raise ValueError("Default insurer not found")
        return row["id"]

    def _insert_address(self, cur, address: AddressSnapshot) -> int:
        cur.execute(
            """
            INSERT INTO address (
                country,
                county,
                city,
                street,
                number,
                postal_code,
                full_text
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                address.country,
                address.county,
                address.city,
                address.street,
                address.number,
                address.postal_code,
                address.full_text,
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("Address was not saved")
        return row["id"]

    def _contract_read_model_select(self) -> str:
        return """
            SELECT
                c.id,
                c.contract_number,
                c.document_type,
                c.document_version,
                c.status,
                c.source_quote_request_id,
                c.source_quote_document_id,
                c.source_quote_acceptance_id,
                c.issue_date,
                c.effective_date,
                c.expiration_date,
                c.jurisdiction,
                c.governing_law,
                c.currency,
                c.created_at,
                c.updated_at,
                customer.id AS customer_id,
                customer.type AS customer_type,
                customer.full_name AS customer_full_name,
                customer.national_id AS customer_national_id,
                customer.company_id AS customer_company_id,
                customer.email AS customer_email,
                customer.phone AS customer_phone,
                customer_address.country AS customer_address_country,
                customer_address.county AS customer_address_county,
                customer_address.city AS customer_address_city,
                customer_address.street AS customer_address_street,
                customer_address.number AS customer_address_number,
                customer_address.postal_code AS customer_address_postal_code,
                customer_address.full_text AS customer_address_full_text,
                asset.id AS asset_id,
                asset.asset_type,
                asset.usage_type,
                asset.construction_type,
                asset.year_built,
                asset.floor,
                asset.area_sqm,
                asset.declared_value,
                asset.occupancy,
                asset.previous_claims_count,
                asset_address.country AS asset_address_country,
                asset_address.county AS asset_address_county,
                asset_address.city AS asset_address_city,
                asset_address.street AS asset_address_street,
                asset_address.number AS asset_address_number,
                asset_address.postal_code AS asset_address_postal_code,
                asset_address.full_text AS asset_address_full_text,
                pricing.base_premium_ron,
                pricing.final_premium_ron,
                pricing.payment_plan_type,
                pricing.installments
            FROM contract c
            JOIN customer ON customer.id = c.customer_id
            JOIN address customer_address ON customer_address.id = customer.address_id
            JOIN insured_asset asset ON asset.id = c.insured_asset_id
            JOIN address asset_address ON asset_address.id = asset.address_id
            LEFT JOIN LATERAL (
                SELECT *
                FROM pricing p
                WHERE p.contract_id = c.id
                ORDER BY p.id DESC
                LIMIT 1
            ) pricing ON TRUE
        """

    def _client_ownership_clause(self) -> str:
        return """
            (
                c.customer_id = %s
                OR EXISTS (
                    SELECT 1
                    FROM quote_request qr
                    WHERE qr.request_id = c.source_quote_request_id
                      AND qr.client_id = %s
                )
            )
        """

    def _contract_read_model(self, row: dict) -> ContractReadModel:
        source_quote_request_id = row.get("source_quote_request_id")
        pricing = None
        if row.get("final_premium_ron") is not None:
            pricing = ContractPricingSummary(
                base_premium_ron=row["base_premium_ron"],
                final_premium_ron=row["final_premium_ron"],
                currency=row["currency"],
                payment_plan_type=row["payment_plan_type"],
                installments=row["installments"],
            )

        return ContractReadModel(
            id=row["id"],
            contract_number=row["contract_number"],
            document_type=row["document_type"],
            document_version=row["document_version"],
            status=row["status"],
            source_quote_request_id=source_quote_request_id,
            source_quote_id=source_quote_request_id,
            source_quote_document_id=row.get("source_quote_document_id"),
            source_quote_acceptance_id=row.get("source_quote_acceptance_id"),
            issue_date=row["issue_date"],
            effective_date=row["effective_date"],
            expiration_date=row["expiration_date"],
            jurisdiction=row["jurisdiction"],
            governing_law=row["governing_law"],
            currency=row["currency"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            customer=ContractCustomerSummary(
                id=row["customer_id"],
                type=row["customer_type"],
                full_name=row["customer_full_name"],
                national_id=row["customer_national_id"],
                company_id=row["customer_company_id"],
                email=row["customer_email"],
                phone=row["customer_phone"],
                address=AddressSnapshot(
                    country=row["customer_address_country"],
                    county=row["customer_address_county"],
                    city=row["customer_address_city"],
                    street=row["customer_address_street"],
                    number=row["customer_address_number"],
                    postal_code=row["customer_address_postal_code"],
                    full_text=row["customer_address_full_text"],
                ),
            ),
            asset=ContractAssetSummary(
                id=row["asset_id"],
                asset_type=row["asset_type"],
                usage_type=row["usage_type"],
                construction_type=row["construction_type"],
                year_built=row["year_built"],
                floor=row["floor"],
                area_sqm=row["area_sqm"],
                declared_value=row["declared_value"],
                occupancy=row["occupancy"],
                previous_claims_count=row["previous_claims_count"],
                address=AddressSnapshot(
                    country=row["asset_address_country"],
                    county=row["asset_address_county"],
                    city=row["asset_address_city"],
                    street=row["asset_address_street"],
                    number=row["asset_address_number"],
                    postal_code=row["asset_address_postal_code"],
                    full_text=row["asset_address_full_text"],
                ),
            ),
            pricing=pricing,
        )


__all__ = ["PostgresContractRepository"]
