"""
AI job match validator.
Validates scraped job listings against the user's requested role, locations,
seniority level, and work authorization profile (read from job_search_config.yml).
"""
from src.llm_client import chat
from src.agents import parse_json

# ── Seniority rules ──────────────────────────────────────────────────────────
_LEVEL_RULES = {
    "junior": (
        "junior / entry-level",
        "ACCEPT: Junior, Entry, Entry-Level, Associate, Jr, New Grad, Graduate, Engineer I, or no seniority marker.\n"
        "REJECT: Senior, Sr, Lead, Principal, Staff, Manager, Director, Head, Architect, Engineer II/III+.",
    ),
    "mid": (
        "mid-level",
        "ACCEPT: no seniority marker, Engineer II, Mid, Mid-Level.\n"
        "REJECT: Junior, Jr, Entry, Associate, Senior, Sr, Lead, Principal, Staff, Manager, Director, Engineer III+.",
    ),
    "senior": (
        "senior / lead",
        "ACCEPT: Senior, Sr, Lead, Principal, Staff, Engineer III+, Architect.\n"
        "REJECT: Junior, Jr, Entry, Associate, Engineer I — below the requested level.\n"
        "Also REJECT: Manager, Director, VP, Head Of — people-management, not IC senior.",
    ),
}
_LEVEL_RULE_NONE = ("all levels", "No seniority filter — accept any level.")

# ── Visa / eligibility rules ─────────────────────────────────────────────────
_VISA_REJECT_SIGNALS = """
REJECT the listing if it contains ANY of:
  - Requires US citizenship ("must be a US citizen", "US citizenship required")
  - Requires active or eligible security clearance ("Secret", "TS/SCI", "DoD clearance",
    "clearance required", "must be eligible for clearance", "ITAR")
  - No sponsorship available ("no sponsorship", "cannot sponsor",
    "must be authorized to work in the US without sponsorship", "no visa sponsorship")
  - Federal / DoD / defense contractor role ("DoD contractor", "federal agency",
    "government contractor") — these inherently require US citizenship
ACCEPT if no disqualifying signals found (assume open unless stated).
"""

_NO_VISA_RESTRICTION = "No work authorization filter — accept all listings regardless of sponsorship/clearance language."

_SYSTEM_TEMPLATE = """\
You are a strict job match validator for a job seeker with this profile:
{profile_block}

Evaluate each job listing against THREE criteria. ALL must pass:

━━━ CRITERION 1 — ROLE MATCH ━━━
The job must be about work in the requested role's domain. Use BOTH the title AND the JD snippet.

Step 1 — title check:
  If the title is a clear semantic match → ACCEPT (move to Criterion 2).
  If the title is a clear mismatch with no AI/ML overlap at all → REJECT.
  If the title contains "AI", "ML", "Machine Learning", "Data Science", "Applied Science",
  or "Artificial Intelligence" as a word but has an unusual suffix (e.g. "AI Identity
  Security Engineer", "AI Solutions Engineer", "AI Platform Engineer") → go to Step 2.

Step 2 — JD content check (only for ambiguous titles):
  Read the JD snippet. If the work described involves model training, inference, LLMs,
  neural networks, ML pipelines, feature engineering, or AI system development → ACCEPT.
  If the work is clearly something else (pure security, devops, frontend, ETL only) → REJECT.

MATCH examples for "ML Engineer": "Machine Learning Engineer", "Applied Scientist",
  "AI/ML Engineer", "Deep Learning Engineer", "NLP Engineer", "MLOps Engineer",
  "AI Engineer", "AI Research Engineer", "ML Platform Engineer", "AI Software Engineer",
  "AI Solutions Engineer" (when JD describes ML/AI work).
NO MATCH: "Software Engineer II" (no AI/ML in JD), "Data Engineer" (ETL pipelines only),
  "Backend Engineer", "DevOps Engineer", "Security Engineer" (when JD has no ML content).

━━━ CRITERION 2 — SENIORITY LEVEL ({level_label}) ━━━
{level_rule}

━━━ CRITERION 3 — ELIGIBILITY ━━━
{eligibility_rule}

━━━ OUTPUT FORMAT ━━━
Return a JSON array — one object per input job, same order:
[
  {{"index": 0, "matches": true,  "reason": "ML role, matches mid level, no citizenship/clearance requirement"}},
  {{"index": 1, "matches": false, "reason": "Requires TS/SCI clearance — not eligible"}},
  {{"index": 2, "matches": false, "reason": "Title 'DevOps Engineer' does not match 'ML Engineer'"}},
  ...
]
Return ONLY the JSON array. No markdown fences. No extra text."""


def _build_profile_block(candidate: dict) -> str:
    lines = []
    nationality = candidate.get("nationality", "")
    visa        = candidate.get("visa_status", "")
    sponsorship = candidate.get("needs_sponsorship", False)
    disabled    = candidate.get("is_disabled", False)
    veteran     = candidate.get("is_veteran", False)

    if nationality:
        lines.append(f"- Nationality: {nationality}")
    if visa:
        lines.append(f"- Visa status: {visa}")
    if sponsorship:
        lines.append("- Requires H-1B visa sponsorship to work in the United States")
        lines.append("- NOT a US citizen — cannot obtain security clearance")
    if not disabled:
        lines.append("- No disability")
    if not veteran:
        lines.append("- Not a veteran")
    return "\n".join(lines) if lines else "No specific profile set."


def _needs_visa_filter(candidate: dict) -> bool:
    return bool(candidate.get("needs_sponsorship") or candidate.get("visa_status") == "h1b_required")


def validate_jobs(
    candidates: list,
    requested_role: str,
    requested_locations: list,
    level: str | None = None,
    candidate: dict | None = None,
) -> list:
    if not candidates:
        return []
    if candidate is None:
        candidate = {}

    validated = []
    batch_size = 15
    for batch_start in range(0, len(candidates), batch_size):
        batch = candidates[batch_start: batch_start + batch_size]
        matched = _validate_batch(batch, batch_start, requested_role, requested_locations, level, candidate)
        validated.extend(matched)
    return validated


def _validate_batch(batch, offset, requested_role, requested_locations, level, candidate):
    level_label, level_rule = _LEVEL_RULES.get(level, _LEVEL_RULE_NONE)
    eligibility_rule = _VISA_REJECT_SIGNALS if _needs_visa_filter(candidate) else _NO_VISA_RESTRICTION
    profile_block    = _build_profile_block(candidate)

    system = _SYSTEM_TEMPLATE.format(
        profile_block=profile_block,
        level_label=level_label,
        level_rule=level_rule,
        eligibility_rule=eligibility_rule,
    )

    jobs_lines = "\n".join(
        f"{offset + i}. Title: {j.get('job_role', '')} | "
        f"Company: {j.get('company_name', '')} | "
        f"Location: {j.get('job_location', '')} | "
        f"Snippet: {j.get('job_description', '')[:200]}"
        for i, j in enumerate(batch)
    )
    prompt = (
        f"Requested role: {requested_role}\n"
        f"Requested seniority: {level or 'any'}\n"
        f"Acceptable locations: {', '.join(requested_locations)} (or Remote/Hybrid)\n\n"
        f"Jobs to validate:\n{jobs_lines}"
    )

    try:
        raw     = chat(system, prompt, temperature=0.1)
        results = parse_json(raw, [])
        if not isinstance(results, list):
            return batch
        matched_indices = {r["index"] for r in results if r.get("matches") is True}
        for r in results:
            if not r.get("matches"):
                print(f"      Rejected [{r.get('index')}]: {r.get('reason', '')}")
        return [j for i, j in enumerate(batch) if (offset + i) in matched_indices]
    except Exception as e:
        print(f"    Warning: job validator failed ({e}). Keeping all candidates.")
        return batch
