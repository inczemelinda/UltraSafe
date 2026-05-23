from uuid import uuid4


class LocalEmailProvider:
    def __init__(self, prefix: str = "local-email") -> None:
        self.prefix = prefix

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
        reply_to: str | None = None,
        attachments=None,
    ) -> str:
        return f"{self.prefix}-{uuid4()}"
