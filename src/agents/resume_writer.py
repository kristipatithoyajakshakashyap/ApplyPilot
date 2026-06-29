"""Full resume rewrite agent with dual ATS + evaluator quality gate."""
from src.llm_client import chat
from src.agents import STYLE_GUIDE, parse_json

_SYSTEM_BASE = f"""You are an expert resume writer. Produce a complete, ATS-optimized, single-page resume.

{STYLE_GUIDE}

=== GOLDEN RULE: STAY IN SCOPE ===
You are REWRITING, not reinventing. Every fact, metric, tool, technology, company, title, and date
must come directly from the original resume. Never invent experience, numbers, or skills.
The candidate should be able to recognize every line as their own work, just better expressed.

=== TAILORING RULES ===
The output must be clearly optimized for the target job -- not a generic resume with keywords sprinkled in.
Achieve this by reorienting EXISTING content, not by adding new content:

SUMMARY:
- Reframe the candidate existing background using the JD language and priorities.
- Highlight the aspects of their real experience that map closest to the JD top requirements.
- Name 2-3 JD-specific technologies or domains that the candidate actually has experience with.

SKILLS:
- Keep every skill from the original resume.
- Add a JD-required skill ONLY when the candidate existing experience clearly implies it
  (e.g., they built PyTorch models but the JD says "deep learning frameworks" -- add that phrase).
- Never add a skill with zero basis in the original resume.

EXPERIENCE:
- Keep all existing roles (company, title, location, dates) exactly as-is. Do not add or remove roles.
- Only rewrite the bullet text within each existing role.
- EVERY ROLE must have bullets. No role should be left empty.
- Most recent role: 3-4 bullets. Older roles: 2-3 bullets each. No single role dominates all bullets.
- Each role's bullets must come from the evidence tagged for THAT ROLE in the RESPONSIBILITY-TO-EVIDENCE MAPPING below.
- For each bullet, choose the angle of that achievement that best demonstrates the skill or
  responsibility the JD cares about most.
- Mirror the JD exact terminology where it accurately describes what the candidate did.
- Quantify every bullet using numbers and metrics already present in the original resume.

=== KEYWORD SATURATION RULE ===
Every keyword listed under MISSING KEYWORDS must appear at least once in the final resume.
Place it in whichever section it fits most naturally based on the candidate actual experience.
Do not insert keywords into bullets where they do not accurately describe the work done.

=== FORMAT RULES (strict -- ATS score depends on these) ===
- Section headers EXACTLY: PROFESSIONAL SUMMARY, TECHNICAL SKILLS, EXPERIENCE, EDUCATION, PUBLICATIONS
- Date format: "Mon YYYY - Mon YYYY" on the same line as job title. No right-aligned dates. No tables.
- No bold inline labels inside bullets (e.g. remove "Agentic AI:" prefixes).
- No colored text, sidebars, graphics, icons, or multi-column layout.
- Contact info (name, email, phone, city) in the body -- not in a PDF header or footer.
- No semicolons. No em dashes. Commas and periods only.
- Bullets: active voice, past tense for past roles, present tense for current role.
- Start every bullet with a strong action verb (Built, Reduced, Scaled, Shipped, Drove, etc.).
- Bullets per role: 3-4 for the most recent role, 2-3 for each older role. Every role must have at least 2 bullets.

Return a single JSON object:
{{
  "name": "<FULL NAME IN CAPS>",
  "contact": "<City, ST | phone | email | linkedin_url | github_url>",
  "summary": "<2-3 sentences. JD-aligned using candidate real background. No semicolons. No em dashes.>",
  "skills": [
    {{"label": "<Category>", "items": "<comma-separated items>"}}
  ],
  "experience": [
    {{
      "title": "<Job Title -- keep exactly as original>",
      "company": "<Company Name -- keep exactly as original>",
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
  "corrections": ["<what was reoriented and why>"]
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

    # Build responsibility-to-evidence mapping grouped by role
    from collections import defaultdict
    role_buckets: dict = defaultdict(list)
    for r in rewrites:
        role_buckets[r.get("role", "General")].append(r)

    resp_parts = []
    for role, role_list in role_buckets.items():
        resp_parts.append(f"--- {role} ---")
        for r in role_list:
            jd_req  = r.get("jd_responsibility", r.get("original", ""))
            cand_ev = r.get("candidate_evidence", r.get("original", ""))
            bullet  = r.get("optimized", r.get("bullet", ""))
            resp_parts.append(f"  JD REQUIRES : {jd_req}\n  CANDIDATE   : {cand_ev}\n  BULLET      : {bullet}")
    resp_map = "\n\n".join(resp_parts)
    unused_list = optimized.get("unused_strong_bullets", [])
    unused = "\n".join(f"  - {b}" for b in unused_list)

    prompt = f"""{iteration_block}=== TARGET JOB (read this first — every bullet must prove competency for this specific role) ===
{jd_text if jd_text else "(no JD provided)"}

=== RESPONSIBILITY-TO-EVIDENCE MAPPING ===
The optimizer has already mapped each key JD responsibility to specific candidate evidence.
Use these as the PRIMARY bullets. Each bullet already starts from a JD requirement and
proves it with real candidate experience.

{resp_map}

{f"Additional strong bullets available (use if space allows):{chr(10)}{unused}" if unused else ""}

=== GAP ANALYSIS ===
High-priority missing keywords (must appear in final resume):
{critical_kw}

Red flags to fix:
{red_flags}

Top edits:
{top_edits}

=== ORIGINAL RESUME (source of truth for all facts) ===
{resume_text}

=== INSTRUCTIONS ===
1. The RESPONSIBILITY-TO-EVIDENCE MAPPING is grouped by role (each section starts with "--- Role @ Company ---").
   Assign the bullets in each section to that matching role in the EXPERIENCE section. Do not mix bullets across roles.
2. Every role must receive the bullets tagged for it. No role should be left without bullets.
3. The summary must name 2-3 technologies/domains from the JD that the candidate actually has.
4. Skills: keep all original skills, add JD-required skills only where the candidate has evidence.
5. Company names, job titles, locations, and dates must match the original resume exactly.
6. Every missing keyword above must appear at least once in the final resume.
7. Apply all FORMAT RULES strictly."""

    raw = chat(_SYSTEM_BASE, prompt, temperature=0.35)
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
