from __future__ import annotations

from psycopg.rows import dict_row

from underwright.domain.models import Template
from underwright.infrastructure.postgres.repository_base import PostgresRepositoryMixin


class PostgresTemplateRepository(PostgresRepositoryMixin):
    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def get_active_template(self, template_code: str) -> Template:
        with self.connection_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._fetch_one(
                    cur,
                    """
                    SELECT * FROM template
                    WHERE template_code = %s
                        AND is_active = TRUE
                    LIMIT 1
                    """,
                    (template_code,),
                    Template,
                )


__all__ = ["PostgresTemplateRepository"]
