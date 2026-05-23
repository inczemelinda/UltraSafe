import smtplib

from email.message import EmailMessage
from email.utils import make_msgid

from underwright.domain.email_message import EmailAttachment


class SmtpEmailProvider:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
        reply_to: str | None = None,
        attachments: list[EmailAttachment] | None = None,
    ) -> str:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = to_email
        if reply_to:
            msg["Reply-To"] = reply_to
        msg["Message-ID"] = make_msgid(domain=self.from_email.split("@")[-1])
        msg.set_content(body)
        if html_body:
            msg.add_alternative(html_body, subtype="html")
        for attachment in attachments or []:
            maintype, _, subtype = attachment.content_type.partition("/")
            msg.add_attachment(
                attachment.content,
                maintype=maintype or "application",
                subtype=subtype or "octet-stream",
                filename=attachment.file_name,
            )

        if self.port == 465:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=20) as smtp:
                smtp.ehlo()
                smtp.login(self.username.strip(), self.password.strip())
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
                smtp.ehlo()

                if self.port in (2525, 587):
                    smtp.starttls()
                    smtp.ehlo()

                smtp.login(self.username.strip(), self.password.strip())
                smtp.send_message(msg)

        return msg["Message-ID"]
