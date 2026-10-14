"""Small Brevo SMTP transport. Off by default; no Firebase, logging or stored secrets.

Callers set `transport` explicitly (a fake in tests). Importing this module never
connects to SMTP. An accepted result means relay acceptance, not inbox delivery.
"""
from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Callable, Optional

HOST = "smtp-relay.brevo.com"
PORT = 587
LOGIN = "bdeb44001@smtp-brevo.com"
FROM_ADDRESS = "toddbeetcher17@gmail.com"
FROM_HEADER = "Launch <toddbeetcher17@gmail.com>"
TIMEOUT_SECONDS = 8


@dataclass(frozen=True)
class SendResult:
    ok: bool
    code: str


transport: Optional[Callable[[str, str, str, str], SendResult]] = None


def send(key: str, recipient: str, subject: str, body: str) -> SendResult:
    """Use the explicitly enabled transport; never expose exception details."""
    if transport is None:
        return SendResult(False, "disabled")
    try:
        return transport(key, recipient, subject, body)
    except Exception:
        return SendResult(False, "unknown")


def send_brevo(key: str, recipient: str, subject: str, body: str) -> SendResult:
    """One attempt: certificate-verified STARTTLS before login, with no retry.

    A connection loss during submission is ambiguous and returns `unknown`.
    Closing the connection cannot overturn an already accepted submission.
    """
    if not key or not key.strip():
        return SendResult(False, "missing_key")
    client = None
    submitting = False
    try:
        message = EmailMessage()
        message["From"] = FROM_HEADER
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        client = smtplib.SMTP(HOST, PORT, timeout=TIMEOUT_SECONDS)
        client.set_debuglevel(0)
        client.ehlo_or_helo_if_needed()
        client.starttls(context=ssl.create_default_context())
        client.ehlo()
        client.login(LOGIN, key)
        submitting = True
        refused = client.send_message(message, from_addr=FROM_ADDRESS, to_addrs=[recipient])
        return SendResult(not refused, "recipient_rejected" if refused else "accepted")
    except smtplib.SMTPAuthenticationError:
        return SendResult(False, "authentication_failed")
    except smtplib.SMTPRecipientsRefused:
        return SendResult(False, "recipient_rejected")
    except smtplib.SMTPSenderRefused:
        return SendResult(False, "sender_rejected")
    except smtplib.SMTPDataError:
        return SendResult(False, "message_rejected")
    except ssl.SSLError:
        return SendResult(False, "unknown" if submitting else "tls_failed")
    except smtplib.SMTPNotSupportedError:
        return SendResult(False, "smtp_feature_unavailable")
    except (OSError, smtplib.SMTPServerDisconnected):
        return SendResult(False, "unknown" if submitting else "connection_failed")
    except Exception:
        return SendResult(False, "unknown" if submitting else "smtp_failed")
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
