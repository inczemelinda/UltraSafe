from __future__ import annotations

from psycopg.rows import dict_row

from underwright.domain.auth_user import AuthUser
from underwright.domain.auth_user_admin import (
    CustomerAuthUserLinkAuditRecord,
    AuthUserSearchResult,
)


class PostgresAuthUserRepository:
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def create_user(self, user: AuthUser) -> AuthUser:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO auth_user (
                        email,
                        password_hash,
                        role,
                        full_name,
                        phone,
                        client_id,
                        is_active
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        user.email,
                        user.password_hash,
                        user.role,
                        user.full_name,
                        user.phone,
                        user.client_id,
                        user.is_active,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("AuthUser was not saved")

        return AuthUser.model_validate(row)

    def get_user_by_email(self, email: str) -> AuthUser:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM auth_user
                    WHERE email = %s
                    LIMIT 1
                    """,
                    (email,),
                )
                row = cur.fetchone()

        if row is None:
            raise ValueError("AuthUser not found")

        return AuthUser.model_validate(row)

    def get_user_by_id(self, user_id: int) -> AuthUser:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM auth_user
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (user_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise ValueError("AuthUser not found")

        return AuthUser.model_validate(row)

    def list_users_by_client_id(self, client_id: int) -> list[AuthUser]:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM auth_user
                    WHERE client_id = %s
                    ORDER BY created_at DESC, id DESC
                    """,
                    (client_id,),
                )
                rows = cur.fetchall()

        return [AuthUser.model_validate(row) for row in rows]

    def search_users(
        self,
        *,
        query: str = "",
        role: str | None = "client",
        unlinked_only: bool = True,
        limit: int = 20,
    ) -> list[AuthUserSearchResult]:
        clauses: list[str] = []
        params: list[object] = []
        if query:
            clauses.append("(au.email ILIKE %s OR au.full_name ILIKE %s)")
            params.extend([f"%{query}%", f"%{query}%"])
        if role:
            clauses.append("au.role = %s")
            params.append(role)
        if unlinked_only:
            clauses.append("au.client_id IS NULL")

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT
                        au.id,
                        au.email,
                        au.role,
                        au.full_name,
                        au.client_id,
                        au.is_active,
                        au.created_at,
                        c.full_name AS customer_full_name
                    FROM auth_user au
                    LEFT JOIN customer c ON c.id = au.client_id
                    {where_sql}
                    ORDER BY au.created_at DESC, au.id DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()

        return [
            AuthUserSearchResult(
                id=row["id"],
                email=row["email"],
                role=row["role"],
                full_name=row["full_name"],
                client_id=row["client_id"],
                customer_full_name=row["customer_full_name"],
                is_active=row["is_active"],
                status="active" if row["is_active"] else "disabled",
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def update_user_client_id(
        self,
        *,
        user_id: int,
        client_id: int | None,
    ) -> AuthUser:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE auth_user
                    SET client_id = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (client_id, user_id),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("AuthUser not found")

        return AuthUser.model_validate(row)

    def get_customer_display_name(self, customer_id: int) -> str | None:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT full_name
                    FROM customer
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (customer_id,),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return row["full_name"]

    def record_customer_auth_user_link_audit(
        self,
        *,
        action: str,
        auth_user_id: int,
        old_customer_id: int | None,
        new_customer_id: int | None,
        reason: str | None,
        changed_by_auth_user_id: int | None,
    ) -> CustomerAuthUserLinkAuditRecord:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO customer_auth_user_link_audit (
                        auth_user_id,
                        old_customer_id,
                        new_customer_id,
                        action,
                        reason,
                        changed_by_auth_user_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        auth_user_id,
                        old_customer_id,
                        new_customer_id,
                        action,
                        reason,
                        changed_by_auth_user_id,
                    ),
                )
                row = cur.fetchone()
                conn.commit()

        if row is None:
            raise ValueError("Customer auth-user link audit was not saved")

        return CustomerAuthUserLinkAuditRecord(
            id=row["id"],
            auth_user_id=row["auth_user_id"],
            old_customer_id=row["old_customer_id"],
            old_customer_name=self.get_customer_display_name(row["old_customer_id"])
            if row["old_customer_id"]
            else None,
            new_customer_id=row["new_customer_id"],
            new_customer_name=self.get_customer_display_name(row["new_customer_id"])
            if row["new_customer_id"]
            else None,
            action=row["action"],
            reason=row["reason"],
            changed_by_auth_user_id=row["changed_by_auth_user_id"],
            changed_at=row["changed_at"],
        )

    def customer_exists(self, customer_id: int) -> bool:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM customer
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (customer_id,),
                )
                return cur.fetchone() is not None

    def email_exists(self, email: str) -> bool:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM auth_user
                    WHERE email = %s
                    LIMIT 1
                    """,
                    (email,),
                )
                return cur.fetchone() is not None
