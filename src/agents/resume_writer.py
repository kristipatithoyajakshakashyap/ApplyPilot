"""Full resume rewrite agent with dual ATS + evaluator quality gate."""
from src.llm_client import chat
from src.agents import STYLE_GUIDE, parse_json

_SYSTEM_BASE = f"""You are an expert resume writer. Produce a complete, ATS-optimized, single-page resume.

{STYLE_GUIDE}

SKILLS SECTION RULE (MANDATORY):
Every required JD skill MUST appear verbatim in the Technical Skills section.
Do not fabricate skills the candidate does not have.

SUMMARY RULE (MANDATORY):
Name at least 2 JD-specific technologies or domains in the summary.
Connect the candidate years of experience to the top JD themes.

KEYWORD SATURATION RULE (MANDATORY):
Every keyword listed under MISSING KEYWORDS must appear at least once in the final resume.
Place in skills, summary, or a bullet — whichever is most natural.

FORMAT RULES (strict — these determine ATS format score):
- Section headers EXACTLY: PROFESSIONAL SUMMARY, TECHNICAL SKILLS, EXPERIENCE, EDUCATION, PUBLICATIONS
- Date format: "Mon YYYY - Mon YYYY" on the same line as job title. No right-aligned dates. No tables.
- No bold inline labels inside bullets (e.g. remove "Agentic AI:" prefixes).
- No colored text, sidebars, graphics, icons, or multi-column layout.
- Contact info (name, email, phone, city) in the body — not in a PDF header or footer.
- No semicolons. No em dashes. Commas and periods only.
- Bullets: active voice, past tense for past roles, present tense for current role.
- Start every bullet with a strong action verb (Built, Reduced, Scaled, Shipped, Drove, etc.).
- Max 10 bullets across all roles.
- Only use facts from the original resume. Do not invent experience or metrics.

Return a single JSON object:
{{
  "name": "<FULL NAME IN CAPS>",
  "contact": "<City, ST | phone | email | linkedin_url | github_url>",
  "summary": "<2-3 sentences. JD-aligned. No semicolons. No em dashes.>",
  "skills": [
    {{"label": "<Category>", "items": "<comma-separated items>"}}
  ],
  "experience": [
    {{
      "title": "<Job Title>",
      "company": "<Company Name>",
      "location": "<City, ST>",
      "dates": "<Mon YYYY - Present or Mon YYYY - Mon YYYY>",
      "bullets": ["<bullet>"]
    }}
  ],
  "education": [
    {{
      "degree": "<Degree>",
      "school": "<School, City, ST>",
      "dates": "<Mon YYYY - Mon YYYY>",
      "details": "<GPA and coursework, commas only>"
    }}
  ],
  "publications": ["<pub>"],
  "corrections": ["<what was fixed>"]
}}
Return ONLY the JSON. No markdown fences. No extra text."""


def rewrite_resume(
    resume_text: str,
    optimized: dict,
    jd_match: dict,
    jd_text: str = "",
    evaluator_feedback: str = "",
    missing_critical: list | None = None,
    missing_preferred: list | None = None,
    ats_issues: list | None = None,
    iteration: int = 1,
) -> dict:
    rewrites = optimized.get("rewrites", [])
    bullet_map = "\n".join(
        f"ORIGINAL: {r['original']}\nOPTIMIZED: {r['optimized']}"
        for r in rewrites
    )
    critical_kw = ", ".join(
        k["keyword"] for k in jd_match.get("missing_keywords", [])
        if k.get("importance") in ("Critical", "High")
    )
    red_flags = "\n".join(f"- {f}" for f in jd_match.get("red_flags", []))
    top_edits = "\n".join(f"- {e}" for e in jd_match.get("top_edits", []))

    iteration_block = ""
    if iteration > 1:
        parts = [f"ITERATION {iteration} — FIX ALL ITEMS BELOW BEFORE ANYTHING ELSE:\n"]

        if missing_critical:
            parts.append("MISSING KEYWORDS (each must appear in the final resume):")
            parts.extend(f"  - {kw}" for kw in missing_critical)

        if missing_preferred:
            parts.append("\nMISSING PREFERRED KEYWORDS (add where candidate has real experience):")
            parts.extend(f"  - {kw}" for kw in missing_preferred[:10])

        if ats_issues:
            parts.append("\nATS FORMAT ISSUES (fix every one to raise ATS score to 92+):")
            parts.extend(f"  - {issue}" for issue in ats_issues)

        if evaluator_feedback:
            parts.append(f"\nEVALUATOR FEEDBACK:\n{evaluator_feedback}")

        iteration_block = "\n".join(parts) + "\n\n"

    prompt = f"""{iteration_block}Original resume:
{resume_text}

Optimized bullets:
{bullet_map}

High-priority missing JD keywords:
{critical_kw}

Red flags to fix:
{red_flags}

Top edits:
{top_edits}

Full Job Description:
{jd_text}

Rewrite the full resume now. Apply SKILLS SECTION RULE, SUMMARY RULE, KEYWORD SATURATION RULE, and FORMAT RULES."""

    raw = chat(_SYSTEM_BASE, prompt, temperature=0.1)
    return parse_json(raw, _fallback(resume_text))


def _fallback(resume_text: str) -> dict:
    lines = [ln.strip() for ln in resume_text.splitlines() if ln.strip()]
    return {
        "name": lines[0] if lines else "RESUME",
        "contact": lines[1] if len(lines) > 1 else "",
        "summary": "", "skills": [], "experience": [],
        "education": [], "publications": [],
        "corrections": ["LLM rewrite failed. Showing minimal fallback."],
    }
