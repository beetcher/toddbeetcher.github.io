"""REFERENCE renderer for the template block format (message_template.schema.json). Executable definition, kept small on purpose.

The real renderer (enjoy_router/comms/render.py, step 2) must produce exactly the same bytes as this one for every golden master.
check.py uses this file to prove that the seed templates reproduce the pre-refactor emails. It knows nothing else about the CMS.

Rules (the guide, MESSAGE_TEMPLATE_GUIDE.md, section 3, states them in words):
  * Placeholders are {fact_name}. A placeholder whose fact is missing or empty makes the render fail (reason `incomplete`).
  * A block or row with show_if is omitted when that fact is missing or empty.
  * In the HTML version literal text is escaped with quote=False; substituted values with quote=True. `**x**` is bold in HTML, plain in text.
  * Plain text: blocks are joined by a blank line, the whole ends with one newline. A table is one `Label: value` line per row.
  * A button is `prefix link` (or just the link) in the text version, a styled link in HTML, plus an optional "copy this address" line.
"""
import re
from html import escape

TOKEN = re.compile(r"(\*\*|\{[a-z][a-z0-9_]*\})")
BUTTON_STYLE = ("display:inline-block;padding:12px 20px;background:#1a1a1a;color:#ffffff;"
                "text-decoration:none;border-radius:6px;font-weight:bold")
ROW_STYLE = "color:#555;vertical-align:top"


class Incomplete(Exception):
    pass


def has(facts, name):
    v = facts.get(name)
    return v is not None and v != "" and v != []


def _fill(text, facts, html):
    out, bold = [], False
    for part in TOKEN.split(text):
        if part == "**":
            bold = not bold
            if html:
                out.append("</strong>" if not bold else "<strong>")
        elif part.startswith("{") and part.endswith("}"):
            name = part[1:-1]
            if not has(facts, name):
                raise Incomplete(name)
            out.append(escape(str(facts[name])) if html else str(facts[name]))
        else:
            out.append(escape(part, quote=False) if html else part)
    if bold:
        raise ValueError("unbalanced ** in " + text)
    return "".join(out)


def render(template, facts):
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
            h = (f'<p><a href="{escape(link)}" style="{BUTTON_STYLE}">{escape(b["label"], quote=False)}</a></p>')
            if b.get("has_fallback_line"):
                h += f"<p>If the button does not work, copy this address into your browser:<br>{escape(link)}</p>"
            htmls.append(h)
    return subject, "\n\n".join(texts) + "\n", "<html><body>" + "".join(htmls) + "</body></html>"
