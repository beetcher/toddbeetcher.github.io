"""Blocks to text and HTML (MESSAGE_TEMPLATE_GUIDE.md sections 3 and 4; rules R-11, R-12). Product-blind.

This must produce exactly the bytes of schemas/message_kinds/reference_render.py (plus the optional footer, which the reference
does not have); the golden masters prove it. If the two ever disagree, the reference and the guide win.
"""
from __future__ import annotations

import re
from html import escape

TOKEN = re.compile(r"(\*\*|\{[a-z][a-z0-9_]*\})")
BUTTON_STYLE = ("display:inline-block;padding:12px 20px;background:#1a1a1a;color:#ffffff;"
                "text-decoration:none;border-radius:6px;font-weight:bold")
ROW_STYLE = "color:#555;vertical-align:top"


class Incomplete(Exception):
    """A placeholder had no value. The argument is the fact name."""


def has(facts, name):
    v = facts.get(name)
    return v is not None and v != "" and v != []


def _fill(text, facts, html):
    out, bold = [], False
    for part in TOKEN.split(text):
        if part == "**":
            bold = not bold
            if html:
                out.append("<strong>" if bold else "</strong>")
        elif part.startswith("{") and part.endswith("}"):
            name = part[1:-1]
            if not has(facts, name):
                raise Incomplete(name)
            out.append(escape(str(facts[name])) if html else str(facts[name]))
        else:
            out.append(escape(part, quote=False) if html else part)
    if bold:
        raise ValueError("unbalanced ** in a template")
    return "".join(out)


def placeholders_in(template) -> set:
    """Every fact name a template mentions (subject, text, plain, link, row values and show_if guards). Used by the template
    handler to refuse a template that names a fact its kind does not supply (R-12)."""
    names = set(re.findall(r"\{([a-z][a-z0-9_]*)\}", template.get("subject", "")))
    for b in template.get("blocks", []):
        if b.get("show_if"):
            names.add(b["show_if"])
        for key in ("text", "plain", "link"):
            names |= set(re.findall(r"\{([a-z][a-z0-9_]*)\}", b.get(key, "")))
        for r in b.get("rows", []):
            if r.get("show_if"):
                names.add(r["show_if"])
            names |= set(re.findall(r"\{([a-z][a-z0-9_]*)\}", r.get("value", "")))
    return names


def render(template, facts, footer=None):
    """-> (subject, text, html). Raises Incomplete(fact_name)."""
    subject = _fill(template["subject"], facts, False)
    texts, htmls = [], []
    for b in template["blocks"]:
        if b.get("show_if") and not has(facts, b["show_if"]):
            continue
        if b["type"] == "paragraph":
            texts.append(_fill(b.get("plain", b["text"]), facts, False))
            htmls.append("<p>" + _fill(b["text"], facts, True) + "</p>")
        elif b["type"] == "facts_table":
            lines, rows = [], []
            for r in b["rows"]:
                if r.get("show_if") and not has(facts, r["show_if"]):
                    continue
                lines.append(f"{r['label']}: {_fill(r['value'], facts, False)}")
                rows.append(f'<tr><td style="{ROW_STYLE}">{escape(r["label"], quote=False)}</td>'
                            f"<td><strong>{_fill(r['value'], facts, True)}</strong></td></tr>")
            if rows:
                texts.append("\n".join(lines))
                htmls.append('<table cellpadding="4" style="border-collapse:collapse">' + "".join(rows) + "</table>")
        elif b["type"] == "button":
            link = _fill(b["link"], facts, False)
            prefix = b.get("plain_prefix")
            texts.append(f"{prefix} {link}" if prefix else link)
            h = f'<p><a href="{escape(link)}" style="{BUTTON_STYLE}">{escape(b["label"], quote=False)}</a></p>'
            if b.get("has_fallback_line"):
                h += f"<p>If the button does not work, copy this address into your browser:<br>{escape(link)}</p>"
            htmls.append(h)
    if footer:
        texts.append(footer)
        htmls.append("<p>" + escape(footer, quote=False) + "</p>")
    return subject, "\n\n".join(texts) + "\n", "<html><body>" + "".join(htmls) + "</body></html>"
