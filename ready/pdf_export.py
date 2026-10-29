"""Render the already-authorized frozen test as a read-only review PDF.

No database, network, script execution or participant player. Authored text is
escaped before entering ReportLab's paragraph markup. Fonts ship with ReportLab.
"""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, HRFlowable

FONT_DIR = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("ReadySans", str(FONT_DIR / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("ReadySansBold", str(FONT_DIR / "VeraBd.ttf")))
pdfmetrics.registerFontFamily("ReadySans", normal="ReadySans", bold="ReadySansBold")
INK = colors.HexColor("#20352e")
GREEN = colors.HexColor("#236449")
MUTED = colors.HexColor("#58695f")


def text(value):
    value = str(value).replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    return escape(value).replace("\n", "<br/>")


def render_test_pdf(saved):
    """Return PDF bytes from the frozen test, never live library references."""
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter, leftMargin=48, rightMargin=48,
        topMargin=53, bottomMargin=48, title=saved["label"], author=saved["origin"]["author"])
    styles = {
        "title": ParagraphStyle("ReadyTitle", fontName="ReadySansBold", fontSize=19, leading=24,
            textColor=INK, spaceAfter=12, keepWithNext=True),
        "meta": ParagraphStyle("ReadyMeta", fontName="ReadySans", fontSize=8, leading=12,
            textColor=MUTED, spaceAfter=5),
        "question": ParagraphStyle("ReadyQuestion", fontName="ReadySansBold", fontSize=11,
            leading=16, textColor=INK, spaceAfter=10, keepWithNext=True),
        "answer": ParagraphStyle("ReadyAnswer", fontName="ReadySans", fontSize=9.5,
            leading=14, textColor=INK, spaceAfter=4, leftIndent=12),
        "feedback": ParagraphStyle("ReadyFeedback", fontName="ReadySans", fontSize=8.5,
            leading=12.5, textColor=MUTED, spaceAfter=11, leftIndent=27),
    }
    story = [Paragraph(text(saved["label"]), styles["title"]),
        Paragraph("<b>Review copy - includes answer classifications and feedback</b>", styles["meta"]),
        Paragraph("Test ID: " + text(saved["id"]), styles["meta"]),
        Paragraph("Author: " + text(saved["origin"]["author"]) + " | " + str(len(saved["items"])) +
            " question occurrences | " + ("Archived" if saved["is_archived"] else "Preserved"), styles["meta"]),
        Paragraph("Source: " + text(saved["origin"].get("source_reference", "")), styles["meta"]), Spacer(1, 15)]
    for number, item in enumerate(saved["items"], 1):
        block = [Paragraph(str(number) + ". " + text(item["question_text"]), styles["question"])]
        for index, answer in enumerate(item["answers"]):
            label = chr(ord("A") + index) if index < 26 else str(index + 1)
            role = answer["role"].capitalize()
            block.append(Paragraph("<b>" + label + ". [" + text(role) + "]</b> " + text(answer["answer_text"]), styles["answer"]))
            if answer.get("feedback"):
                block.append(Paragraph(text(answer["feedback"]), styles["feedback"]))
        block.extend([Spacer(1, 5), HRFlowable(width="100%", thickness=.5,
            color=colors.HexColor("#d9dfd3")), Spacer(1, 15)])
        # Keep a normal question together; oversized authored questions can split.
        story.append(KeepTogether(block))

    def page_frame(canvas, document):
        canvas.saveState()
        canvas.setFillColor(GREEN); canvas.setFont("ReadySansBold", 9)
        canvas.drawString(48, letter[1] - 30, "READY | SAVED TEST REVIEW")
        canvas.setStrokeColor(colors.HexColor("#d9dfd3"));canvas.setLineWidth(.5)
        canvas.line(48, 37, letter[0] - 48, 37)
        canvas.setFillColor(MUTED);canvas.setFont("ReadySans", 7)
        canvas.drawString(48, 24, "Review copy - answer key included | Test " + saved["id"][:8])
        canvas.drawRightString(letter[0] - 48, 24, "Page " + str(document.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    return output.getvalue()
