from src.llm_client import chat
from src.agents import parse_json

_SYSTEM = """\
You are a resume strategist. Your job is to map a candidate's real experience — across ALL their
roles — to a specific job's responsibilities, then write evidence-based bullets that prove the
candidate can do what the job requires. Every role in the candidate's history must get bullets.

Process (follow in order):
1. Read the Job Description and extract the 6-10 most important responsibilities.
2. Read the candidate's resume and identify every role (company + title) in chronological order.
3. For EACH ROLE, pick 2-3 of those JD responsibilities that best match the work done in that role.
4. For each (role, responsibility) pair, write a bullet that STARTS from the JD responsibility
   language, then proves it with the candidate's real achievement from that specific role.

Rules:
- Every bullet must use the JD's exact terminology for the skill or responsibility it proves.
- Every bullet must include a number, percentage, scale, or time from the original resume.
- Never invent facts, metrics, tools, or experience not present in the original resume.
- Evidence must come from the specific role listed in "role" — do not mix roles.
- If a role has no direct JD match, use transferable skills from that role's actual work.
- Lead with a strong action verb. No weak openers (responsible for, helped with, worked on).
- No semicolons. No em dashes. Commas and periods only.
- EVERY ROLE must have at least 2 bullets. Most recent role: 3-4 bullets. Older roles: 2-3 each.

Return a single JSON object:
{
  "responsibility_bullets": [
    {
      "role": "<Job Title @ Company — exactly as it appears in the resume>",
      "jd_responsibility": "<the JD requirement this bullet proves>",
      "candidate_evidence": "<the specific experience/achievement from that role used as proof>",
      "bullet": "<final bullet: starts with JD language, proves with candidate achievement + metric>"
    }
  ],
  "unused_strong_bullets": [
    "<any original bullet with strong metrics not covered by a responsibility mapping>"
  ]
}
Return ONLY the JSON. No markdown fences. No extra text.
"""


def optimize_bullets(resume_text: str, jd_match: dict, jd_text: str = "") -> dict:
    missing_kw = ", ".join(
        k["keyword"] for k in jd_match.get("missing_keywords", [])[:8]
        if k.get("importance") in ("Critical", "High")
    )
    prompt = (
        f"=== JOB DESCRIPTION ===\n{jd_text}\n\n"
        f"=== CANDIDATE RESUME (all facts must come from here) ===\n{resume_text}\n\n"
        f"Critical keywords missing from resume (work these in where they fit naturally): {missing_kw}\n\n"
        "Now map the JD responsibilities to candidate evidence and write targeted bullets."
    )
    raw = chat(_SYSTEM, prompt)
    result = parse_json(raw, {"responsibility_bullets": [], "unused_strong_bullets": []})

    # Normalize to the {rewrites: [...]} shape the resume writer expects
    rewrites = []
    for rb in result.get("responsibility_bullets", []):
        rewrites.append({
            "role": rb.get("role", ""),
            "jd_responsibility": rb.get("jd_responsibility", ""),
            "candidate_evidence": rb.get("candidate_evidence", ""),
            "original": rb.get("candidate_evidence", ""),
            "optimized": rb.get("bullet", ""),
        })
    result["rewrites"] = rewrites
    return result