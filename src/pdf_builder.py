import html
import pymupdf
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, HRFlowable
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER

_FONT_SIZES = [8.2, 7.9, 7.6, 7.3, 7.0, 6.7, 6.4]


def build_pdf(resume: dict, output_path: str) -> None:
    for fs in _FONT_SIZES:
        _render(resume, output_path, fs)
        if _page_count(output_path) == 1:
            print(f"  Single page at font size {fs:.1f}pt.")
            return
    print("  WARNING: Could not fit in one page at minimum font. Trimming bullets.")
    _trim_bullets(resume)
    _render(resume, output_path, _FONT_SIZES[-1])


def _page_count(path: str) -> int:
    doc = pymupdf.open(path)
    n = len(doc)
    doc.close()
    return n


def _trim_bullets(resume: dict) -> None:
    for exp in resume.get("experience", []):
        exp["bullets"] = exp.get("bullets", [])[:2]


def _e(text: str) -> str:
    normalized = (
        str(text)
        .replace("–", "-")
        .replace("—", "-")
        .replace("‘", "'")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
    )
    return html.escape(normalized, quote=False)


def _render(resume: dict, output_path: str, fs: float) -> None:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.48 * inch,
        leftMargin=0.48 * inch,
        topMargin=0.38 * inch,
        bottomMargin=0.32 * inch,
    )

    name_st = ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=fs + 5,
                              alignment=TA_CENTER, spaceAfter=2)
    contact_st = ParagraphStyle("contact", fontName="Helvetica", fontSize=fs - 0.4,
                                alignment=TA_CENTER, spaceAfter=3)
    sec_st = ParagraphStyle("sec", fontName="Helvetica-Bold", fontSize=fs + 0.5,
                            spaceBefore=4, spaceAfter=1)
    job_st = ParagraphStyle("job", fontName="Helvetica-Bold", fontSize=fs,
                            spaceBefore=3, spaceAfter=1)
    body_st = ParagraphStyle("body", fontName="Helvetica", fontSize=fs,
                             leading=fs * 1.3, spaceAfter=1)
    bullet_st = ParagraphStyle("bullet", fontName="Helvetica", fontSize=fs,
                               leading=fs * 1.3, leftIndent=10,
                               firstLineIndent=-6, spaceAfter=1.5)
    pub_st = ParagraphStyle("pub", fontName="Helvetica", fontSize=fs - 0.4,
                            leading=fs * 1.25, spaceAfter=1.5)

    def section(title):
        return [
            Paragraph(title, sec_st),
            HRFlowable(width="100%", thickness=0.5, color=colors.black, spaceAfter=2),
        ]

    story = []

    story.append(Paragraph(_e(resume.get("name", "")), name_st))
    story.append(Paragraph(_e(resume.get("contact", "")), contact_st))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.black, spaceAfter=3))

    if resume.get("summary"):
        story += section("PROFESSIONAL SUMMARY")
        story.append(Paragraph(_e(resume["summary"]), body_st))

    if resume.get("skills"):
        story += section("TECHNICAL SKILLS")
        for s in resume["skills"]:
            story.append(Paragraph(f"<b>{_e(s['label'])}:</b> {_e(s['items'])}", body_st))

    if resume.get("experience"):
        story += section("EXPERIENCE")
        for exp in resume["experience"]:
            header = (
                f"<b>{_e(exp.get('title', ''))}</b> | "
                f"{_e(exp.get('company', ''))} - {_e(exp.get('location', ''))} | "
                f"{_e(exp.get('dates', ''))}"
            )
            story.append(Paragraph(header, job_st))
            for b in exp.get("bullets", []):
                story.append(Paragraph(f"• {_e(b)}", bullet_st))

    if resume.get("education"):
        story += section("EDUCATION")
        for edu in resume["education"]:
            story.append(Paragraph(
                f"<b>{_e(edu.get('degree', ''))}</b> | "
                f"{_e(edu.get('school', ''))} | {_e(edu.get('dates', ''))}",
                job_st,
            ))
            if edu.get("details"):
                story.append(Paragraph(_e(edu["details"]), body_st))

    if resume.get("publications"):
        story += section("PUBLICATIONS")
        for pub in resume["publications"]:
            story.append(Paragraph(_e(pub), pub_st))

    doc.build(story)
