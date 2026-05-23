from __future__ import annotations

from psycopg.rows import dict_row

from underwright.domain.customer_profile import (
    CustomerAddressProfile,
    CustomerProfileCompletionSource,
    CustomerProfileStatus,
    StoredCustomerProfile,
)


class PostgresCustomerProfileRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def list_customer_profiles(self) -> list[StoredCustomerProfile]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    {self._select_profile_sql()}
                    ORDER BY c.id DESC
                    """
                )
                rows = cur.fetchall()
        return [self._stored_profile(row) for row in rows]

    def get_customer_profile(self, customer_id: int) -> StoredCustomerProfile:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    {self._select_profile_sql()}
                    WHERE c.id = %s
                    LIMIT 1
                    """,
                    (customer_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise ValueError("Customer profile not found")
        return self._stored_profile(row)

    def create_customer_profile(
        self,
        profile: StoredCustomerProfile,
        *,
        updated_by_auth_user_id: int | None,
        source: CustomerProfileCompletionSource,
    ) -> StoredCustomerProfile:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                address_id = self._insert_address(cur, profile.address)
                cur.execute(
                    """
                    INSERT INTO customer (
                        type,
                        full_name,
                        national_id,
                        company_id,
                        email,
                        phone,
                        address_id,
                        customer_profile_completed_at,
                        customer_profile_updated_at,
                        customer_profile_updated_by_auth_user_id,
                        customer_profile_completion_source,
                        profile_update_count
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s, 1)
                    RETURNING id
                    """,
                    (
                        profile.type,
                        profile.full_name,
                        profile.national_id,
                        profile.company_id,
                        profile.email,
                        profile.phone,
                        address_id,
                        updated_by_auth_user_id,
                        source,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("Customer profile was not saved")
        return self.get_customer_profile(row["id"])

    def update_customer_profile(
        self,
        *,
        customer_id: int,
        profile: StoredCustomerProfile,
        status: CustomerProfileStatus,
        updated_by_auth_user_id: int | None,
        source: CustomerProfileCompletionSource,
    ) -> StoredCustomerProfile:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT address_id FROM customer WHERE id = %s LIMIT 1",
                    (customer_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError("Customer profile not found")
                self._update_address(cur, row["address_id"], profile.address)
                completed_at_sql = (
                    "COALESCE(customer_profile_completed_at, NOW())"
                    if status == "complete"
                    else "NULL"
                )
                cur.execute(
                    f"""
                    UPDATE customer
                    SET type = %s,
                        full_name = %s,
                        national_id = %s,
                        company_id = %s,
                        email = %s,
                        phone = %s,
                        customer_profile_completed_at = {completed_at_sql},
                        customer_profile_updated_at = NOW(),
                        customer_profile_updated_by_auth_user_id = %s,
                        customer_profile_completion_source = %s,
                        profile_update_count = COALESCE(profile_update_count, 0) + 1
                    WHERE id = %s
                    RETURNING id
                    """,
                    (
                        profile.type,
                        profile.full_name,
                        profile.national_id,
                        profile.company_id,
                        profile.email,
                        profile.phone,
                        updated_by_auth_user_id,
                        source,
                        customer_id,
                    ),
                )
                updated = cur.fetchone()
                conn.commit()

        if updated is None:
            raise ValueError("Customer profile not found")
        return self.get_customer_profile(customer_id)

    def touch_customer_profile(
        self,
        *,
        customer_id: int,
        status: CustomerProfileStatus,
        updated_by_auth_user_id: int | None,
        source: CustomerProfileCompletionSource,
    ) -> StoredCustomerProfile:
        completed_at_sql = (
            "COALESCE(customer_profile_completed_at, NOW())"
            if status == "complete"
            else "customer_profile_completed_at"
        )
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    UPDATE customer
                    SET customer_profile_completed_at = {completed_at_sql},
                        customer_profile_updated_at = NOW(),
                        customer_profile_updated_by_auth_user_id = %s,
                        customer_profile_completion_source = %s,
                        profile_update_count = COALESCE(profile_update_count, 0) + 1
                    WHERE id = %s
                    RETURNING id
                    """,
                    (updated_by_auth_user_id, source, customer_id),
                )
                row = cur.fetchone()
                conn.commit()
        if row is None:
            raise ValueError("Customer profile not found")
        return self.get_customer_profile(customer_id)

    def _select_profile_sql(self) -> str:
        return """
            SELECT
                c.id AS customer_id,
                c.type,
                c.full_name,
                c.national_id,
                c.company_id,
                c.email,
                c.phone,
                c.customer_profile_completed_at,
                c.customer_profile_updated_at,
                c.customer_profile_updated_by_auth_user_id,
                c.customer_profile_completion_source,
                COALESCE(c.profile_update_count, 0) AS profile_update_count,
                a.country AS address_country,
                a.county AS address_county,
                a.city AS address_city,
                a.street AS address_street,
                a.number AS address_number,
                a.postal_code AS address_postal_code,
                a.full_text AS address_full_text
            FROM customer c
            JOIN address a ON a.id = c.address_id
        """

    def _insert_address(self, cur, address: CustomerAddressProfile) -> int:
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
            self._address_values(address),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("Customer address was not saved")
        return row["id"]

    def _update_address(self, cur, address_id: int, address: CustomerAddressProfile) -> None:
        cur.execute(
            """
            UPDATE address
            SET country = %s,
                county = %s,
                city = %s,
                street = %s,
                number = %s,
                postal_code = %s,
                full_text = %s
            WHERE id = %s
            """,
            (*self._address_values(address), address_id),
        )

    def _address_values(self, address: CustomerAddressProfile) -> tuple:
        return (
            address.country,
            address.county,
            address.city,
            address.street,
            address.number,
            address.postal_code,
            address.full_text,
        )

    def _stored_profile(self, row: dict) -> StoredCustomerProfile:
        return StoredCustomerProfile(
            customer_id=row["customer_id"],
            type=row["type"],
            full_name=row["full_name"],
            national_id=row["national_id"],
            company_id=row["company_id"],
            email=row["email"],
            phone=row["phone"],
            address=CustomerAddressProfile(
                country=row["address_country"],
                county=row["address_county"],
                city=row["address_city"],
                street=row["address_street"],
                number=row["address_number"],
                postal_code=row["address_postal_code"],
                full_text=row["address_full_text"],
            ),
            customer_profile_completed_at=row["customer_profile_completed_at"],
            customer_profile_updated_at=row["customer_profile_updated_at"],
            customer_profile_updated_by_auth_user_id=(
                row["customer_profile_updated_by_auth_user_id"]
            ),
            customer_profile_completion_source=row[
                "customer_profile_completion_source"
            ],
            profile_update_count=row["profile_update_count"],
        )


__all__ = ["PostgresCustomerProfileRepository"]
