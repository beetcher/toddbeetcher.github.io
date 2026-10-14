"""CMS Feature 1: a basic request acknowledgment, using the SMTP transport hook."""
from html import escape

import smtp_transport

SUBJECT = "Launch — we received your request"


def acknowledge(name, email, confirmation_number, key):
    """Return a sanitized transport result. No database access, retries or logging."""
    text = (f"Hello {name},\n\nWe received your request. Your confirmation number is "
            f"{confirmation_number}.\n\nWe'll contact you about the next steps.\n\nLaunch\n")
    html = (f"<html><body><p>Hello {escape(name)},</p><p>We received your request. "
            f"Your confirmation number is <strong>{escape(confirmation_number)}</strong>.</p>"
            "<p>We'll contact you about the next steps.</p><p>Launch</p></body></html>")
    # Multipart HTML allows Brevo's existing open tracking; no tracking or
    # unsubscribe override is added. SMTP acceptance is not delivery or an open.
    return smtp_transport.send(key, email, SUBJECT, text, html)
