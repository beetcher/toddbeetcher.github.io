"""Small Brevo SMTP transport. Off by default; no Firebase, logging or stored secrets.

Callers set `transport` explicitly (a fake in tests). Importing this module never
connects to SMTP. An accepted result means relay acceptance, not inbox delivery.
"""
from __future__ import annotations

import smtplib
import ssl
import multiprocessing
import time
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Callable, Optional

HOST = "smtp-relay.brevo.com"
PORT = 587
LOGIN = "bdeb44001@smtp-brevo.com"
FROM_ADDRESS = "toddbeetcher17@gmail.com"
TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class SendResult:
    ok: bool
    code: str


transport: Optional[Callable[..., SendResult]] = None


def send(key: str, recipient: str, subject: str, body: str, html_body=None, attachments=None) -> SendResult:
    """Use the explicitly enabled transport; never expose exception details.

    `attachments` is an optional list of (filename, mime_type, bytes), for example a calendar file; it is passed on only when given,
    so a transport that does not know about attachments keeps working for plain messages."""
    if transport is None:
        return SendResult(False, "disabled")
    try:
        if attachments:
            return transport(key, recipient, subject, body, html_body, attachments)
        if html_body is None:
            return transport(key, recipient, subject, body)
        return transport(key, recipient, subject, body, html_body)
    except TimeoutError:
        return SendResult(False, "unknown")
    except Exception:
        return SendResult(False, "unknown")


def _send_once(key: str, recipient: str, subject: str, body: str, html_body=None, attachments=None) -> SendResult:
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
        message["From"] = f"Launch <{FROM_ADDRESS}>"
        message["Reply-To"] = FROM_ADDRESS
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        if html_body is not None:
            message.add_alternative(html_body, subtype="html")
        for filename, mime_type, data in (attachments or ()):
            maintype, _, subtype = mime_type.partition("/")
            params = {"method": "PUBLISH", "charset": "utf-8"} if mime_type == "text/calendar" else {}
            message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename, params=params)
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
    except TimeoutError:
        return SendResult(False, "unknown")
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


def _smtp_worker(connection, key, recipient, subject, body, html_body, attachments=None):
    """Worker credentials travel in memory, never in command arguments or files."""
    try:
        connection.send(_send_once(key, recipient, subject, body, html_body, attachments))
    except BaseException:
        # No traceback: exception text can contain SMTP replies or submitted data.
        pass
    finally:
        connection.close()


def send_brevo(key: str, recipient: str, subject: str, body: str, html_body=None, attachments=None) -> SendResult:
    """Cap the entire attempt, including DNS/connect/TLS/auth/DATA, at about 10s.

    A separate worker lets us stop blocked I/O instead of leaving a thread that
    might send later. No retries. The parent never logs credentials or replies.
    """
    if not key or not key.strip():
        return SendResult(False, "missing_key")
    deadline = time.monotonic() + TIMEOUT_SECONDS
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    worker = context.Process(target=_smtp_worker, args=(sender, key, recipient, subject, body, html_body, attachments))
    started = False
    try:
        worker.start()
        started = True
        sender.close()
        remaining = max(0, deadline - time.monotonic())
        if receiver.poll(remaining):
            return receiver.recv()
        return SendResult(False, "unknown")
    except Exception:
        return SendResult(False, "unknown")
    finally:
        sender.close()
        receiver.close()
        if started:
            worker.join(timeout=0)
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=0.2)
            if worker.is_alive():
                worker.kill()
                worker.join(timeout=0.2)
            if not worker.is_alive():
                worker.close()
