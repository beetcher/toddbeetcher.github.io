"""CMS Feature 1: a basic request acknowledgment, using the SMTP transport hook."""
from html import escape

import smtp_transport

SUBJECT = "Launch — we received your request"


def acknowledge(name, email, confirmation_number, key, link=None):
    """Return a sanitized transport result. No database access, retries or logging."""
    text = (f"Hello {name},\n\nWe received your request. Your confirmation number is "
            f"{confirmation_number}.\n\n")
    html = (f"<html><body><p>Hello {escape(name)},</p><p>We received your request. "
            f"Your confirmation number is <strong>{escape(confirmation_number)}</strong>.</p>")
    if link:   # the completion link: opens the same request with their answers filled in (slice 3)
        text += ("Want to tell us a little more so we can find the right fit? It takes about two minutes, and what you already told us "
                 f"is filled in:\n\n{link}\n\n")
        html += ("<p>Want to tell us a little more so we can find the right fit? It takes about two minutes, and what you already told us "
                 f"is filled in.</p><p><a href=\"{escape(link)}\" style=\"display:inline-block;padding:12px 20px;background:#1a1a1a;color:#ffffff;"
                 "text-decoration:none;border-radius:6px;font-weight:bold\">Finish your request</a></p>"
                 f"<p>If the button does not work, copy this address into your browser:<br>{escape(link)}</p>")
    text += "We'll contact you about the next steps either way.\n\nLaunch\n"
    html += "<p>We'll contact you about the next steps either way.</p><p>Launch</p></body></html>"
    # Multipart HTML allows Brevo's existing open tracking; no tracking or
    # unsubscribe override is added. SMTP acceptance is not delivery or an open.
    return smtp_transport.send(key, email, SUBJECT, text, html)
