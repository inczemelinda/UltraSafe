import os
import sys

from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "src"))

from underwright.infrastructure.email.smtp_email_provider import SmtpEmailProvider  # noqa: E402

load_dotenv(ROOT_DIR / ".env")

postmark_token = os.environ.get("POSTMARK_SERVER_TOKEN")
host = os.environ.get("EMAIL_SMTP_HOST") or (
    "smtp.postmarkapp.com" if postmark_token else None
)
port = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
username = os.environ.get("EMAIL_USERNAME") or postmark_token
password = os.environ.get("EMAIL_PASSWORD") or postmark_token
from_email = os.environ["EMAIL_FROM"]
to_email = os.environ.get("EMAIL_TEST_TO", "client@test.com")

if not host or not username or not password:
    raise RuntimeError(
        "Set EMAIL_SMTP_HOST plus EMAIL_USERNAME/EMAIL_PASSWORD, or set "
        "POSTMARK_SERVER_TOKEN to use smtp.postmarkapp.com."
    )

print("HOST =", host)
print("PORT =", port)
print("FROM =", from_email)
print("TO =", to_email)

provider = SmtpEmailProvider(
    host=host,
    port=port,
    username=username,
    password=password,
    from_email=from_email,
)
message_id = provider.send_email(
    to_email=to_email,
    subject="Underwright Email Test",
    body="Hello from Underwright.",
)

print(f"EMAIL SENT SUCCESSFULLY: {message_id}")
