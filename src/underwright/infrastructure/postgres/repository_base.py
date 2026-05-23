from __future__ import annotations


class PostgresRepositoryMixin:
    def _fetch_one(
        self,
        cur,
        sql,
        params,
        model_type,
        not_found_message: str | None = None,
    ):
        cur.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            raise ValueError(not_found_message or f"{model_type.__name__} not found")
        return model_type.model_validate(row)

    def _fetch_many(self, cur, sql, params, model_type):
        cur.execute(sql, params)
        return [model_type.model_validate(row) for row in cur.fetchall()]


__all__ = ["PostgresRepositoryMixin"]
