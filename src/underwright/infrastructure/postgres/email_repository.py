from uuid import UUID

from underwright.domain.email_message import CustomerEmailMessage, EmailMessage


class PostgresEmailMessageRepository:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def save(self, email: EmailMessage) -> EmailMessage:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO email_messages (
                        id,
                        case_id,
                        request_id,
                        direction,
                        from_email,
                        to_email,
                        subject,
                        body,
                        status,
                        provider_message_id,
                        error_message,
                        created_at,
                        sent_at
                    )
                    VALUES (
                        %(id)s,
                        %(case_id)s,
                        %(request_id)s,
                        %(direction)s,
                        %(from_email)s,
                        %(to_email)s,
                        %(subject)s,
                        %(body)s,
                        %(status)s,
                        %(provider_message_id)s,
                        %(error_message)s,
                        COALESCE(%(created_at)s, NOW()),
                        %(sent_at)s
                    )
                    RETURNING
                        id,
                        case_id,
                        request_id,
                        direction,
                        from_email,
                        to_email,
                        subject,
                        body,
                        status,
                        provider_message_id,
                        error_message,
                        created_at,
                        sent_at
                    """,
                    {
                        "id": email.id,
                        "case_id": email.case_id,
                        "request_id": email.request_id,
                        "direction": email.direction,
                        "from_email": email.from_email,
                        "to_email": email.to_email,
                        "subject": email.subject,
                        "body": email.body,
                        "status": email.status,
                        "provider_message_id": email.provider_message_id,
                        "error_message": email.error_message,
                        "created_at": email.created_at,
                        "sent_at": email.sent_at,
                    },
                )

                row = cur.fetchone()
                conn.commit()

        return self._to_domain(row)

    def list_by_case_id(self, case_id: UUID) -> list[EmailMessage]:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        case_id,
                        request_id,
                        direction,
                        from_email,
                        to_email,
                        subject,
                        body,
                        status,
                        provider_message_id,
                        error_message,
                        created_at,
                        sent_at
                    FROM email_messages
                    WHERE case_id = %s OR request_id = %s
                    ORDER BY created_at DESC
                    """,
                    (case_id, case_id),
                )

                rows = cur.fetchall()

        return [self._to_domain(row) for row in rows]

    def get_by_provider_message_id(
        self,
        provider_message_id: str,
    ) -> EmailMessage | None:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        case_id,
                        request_id,
                        direction,
                        from_email,
                        to_email,
                        subject,
                        body,
                        status,
                        provider_message_id,
                        error_message,
                        created_at,
                        sent_at
                    FROM email_messages
                    WHERE provider_message_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (provider_message_id,),
                )
                row = cur.fetchone()

        return self._to_domain(row) if row is not None else None

    def list_by_customer_id(self, customer_id: int) -> list[CustomerEmailMessage]:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH customer_cases AS (
                        SELECT
                            request_id,
                            CONCAT('Claim ', LEFT(request_id::text, 8))
                                AS case_reference
                        FROM claim_request
                        WHERE client_id = %(customer_id)s

                        UNION ALL

                        SELECT
                            request_id,
                            CONCAT('Quote ', LEFT(request_id::text, 8))
                                AS case_reference
                        FROM quote_request
                        WHERE client_id = %(customer_id)s
                    ),
                    context_cases AS (
                        SELECT
                            cc.case_id,
                            customer_cases.request_id,
                            customer_cases.case_reference
                        FROM case_context cc
                        JOIN customer_cases
                          ON cc.context_json -> 'source_inputs' ->> 'request_id'
                             = customer_cases.request_id::text
                    )
                    SELECT
                        e.id,
                        %(customer_id)s AS customer_id,
                        COALESCE(e.case_id, e.request_id) AS case_id,
                        COALESCE(
                            direct_request.case_reference,
                            direct_case.case_reference,
                            context_cases.case_reference
                        ) AS case_reference,
                        e.direction,
                        e.status,
                        e.to_email,
                        e.from_email,
                        e.subject,
                        LEFT(COALESCE(e.body, ''), 240) AS body_preview,
                        COALESCE(e.body, '') AS body_text,
                        NULL AS body_html,
                        'smtp' AS provider,
                        e.provider_message_id,
                        e.error_message,
                        e.created_at,
                        e.sent_at,
                        CASE
                            WHEN e.direction = 'INBOUND' THEN e.created_at
                            ELSE NULL
                        END AS received_at
                    FROM email_messages e
                    LEFT JOIN customer_cases direct_request
                      ON direct_request.request_id = e.request_id
                    LEFT JOIN customer_cases direct_case
                      ON direct_case.request_id = e.case_id
                    LEFT JOIN context_cases
                      ON context_cases.case_id = e.case_id
                    WHERE direct_request.request_id IS NOT NULL
                       OR direct_case.request_id IS NOT NULL
                       OR context_cases.case_id IS NOT NULL
                    ORDER BY e.created_at DESC, e.id DESC
                    """,
                    {"customer_id": customer_id},
                )

                rows = cur.fetchall()

        return [self._to_customer_domain(row) for row in rows]

    def _to_domain(self, row) -> EmailMessage:
        return EmailMessage(
            id=row[0],
            case_id=row[1],
            request_id=row[2],
            direction=row[3],
            from_email=row[4],
            to_email=row[5],
            subject=row[6],
            body=row[7],
            status=row[8],
            provider_message_id=row[9],
            error_message=row[10],
            created_at=row[11],
            sent_at=row[12],
        )

    def _to_customer_domain(self, row) -> CustomerEmailMessage:
        return CustomerEmailMessage(
            id=row[0],
            customer_id=int(row[1]),
            case_id=row[2],
            case_reference=row[3],
            direction=row[4],
            status=row[5],
            to_email=row[6],
            from_email=row[7],
            subject=row[8],
            body_preview=row[9],
            body_text=row[10],
            body_html=row[11],
            provider=row[12],
            provider_message_id=row[13],
            error_message=row[14],
            created_at=row[15],
            sent_at=row[16],
            received_at=row[17],
        )
