"""
Resume evaluator using the HackerRank hiring-agent scoring framework.

Ported from https://github.com/interviewstreet/hiring-agent and adapted for
resume-vs-job-description matching.

Original dimensions (hiring-agent):
  open_source (35) | self_projects (30) | production (25) | technical_skills (10)
  bonus up to +20 | deductions | final range 0-120

Adapted dimensions for JD matching:
  keyword_coverage (35) | skills_alignment (30) | experience_relevance (25) | summary_format (10)
  bonus up to +20 | deductions | final range 0-120
  normalized pass threshold: raw >= 85 (out of 120 cap)
"""
from src.llm_client import chat
from src.agents import parse_json

# Mirrors hiring-agent constants
MAX_BONUS_POINTS = 20
MAX_FINAL_SCORE  = 120

CATEGORY_MAXES = {
    "keyword_coverage":     35,
    "skills_alignment":     30,
    "experience_relevance": 25,
    "summary_format":       10,
}

_SYSTEM = """\
You are a senior technical recruiter evaluating how well a resume matches a specific job description.
Use the HackerRank hiring-agent scoring framework: evidence-based category scores, bonus points, and deductions.

FAIRNESS CONSTRAINTS — never score on:
  candidate name, gender, demographics, university/college name, GPA/CGPA,
  location, or any personal characteristic unrelated to technical fit.

━━━ SCORING DIMENSIONS (base 100 points) ━━━

1. KEYWORD COVERAGE (0-35 pts)
   Count every distinct required and preferred keyword/technology from the JD.
   Score = 35 * (matched_keywords / total_jd_keywords)
   HIGH (28-35): 90-100% JD keywords present
   MEDIUM (18-27): 65-89% present
   LOW (8-17): 40-64% present
   VERY LOW (0-7): <40% present

2. SKILLS ALIGNMENT (0-30 pts)
   Are all required technical skills listed in the resume skills section verbatim?
   HIGH (22-30): all required skills present, most preferred skills too
   MEDIUM (14-21): most required skills present, some gaps
   LOW (5-13): several required skills missing
   ZERO (0-4): critical skills absent

3. EXPERIENCE RELEVANCE (0-25 pts)
   Does the candidate work experience, projects, and seniority match the JD?
   Score on: years of relevant experience, domain overlap, seniority match, quantified achievements.
   HIGH (19-25): strong domain match, appropriate seniority, metrics-driven bullets
   MEDIUM (11-18): partial domain match or seniority mismatch
   LOW (4-10): weak alignment
   ZERO (0-3): no relevant experience

4. SUMMARY & FORMAT (0-10 pts)
   Summary mentions >= 2 JD-specific themes (5 pts).
   ATS-safe format: standard section names, consistent dates, no tables/graphics (5 pts).

━━━ BONUS POINTS (max +20 total) ━━━
  +5  All required JD skills present AND 100% keyword coverage
  +3  Every bullet has a quantified metric (%, $, time, count)
  +3  Seniority and domain are an exact match for the role
  +2  Relevant certifications or publications matching the JD
  +2  Open source or side projects directly related to the JD domain
  +3  Leadership / founding experience relevant to the role
  +2  Awards or recognition in the JD domain

━━━ DEDUCTIONS ━━━
  -3 to -5  Per missing critical JD keyword or required skill
  -2 to -4  Bullets use weak language ("responsible for", "helped with", "worked on")
  -2 to -3  Format issues (tables, graphics, non-standard section names)
  -1 to -3  Summary does not mention the JD domain or role type

Final score = sum(capped category scores) + bonus_points - deductions
Cap final score at 120. All scores must be >= 0.
Pass threshold: raw score >= 85.

━━━ OUTPUT FORMAT ━━━
Return a single JSON object exactly matching this schema:
{
  "scores": {
    "keyword_coverage":     {"score": <0-35>, "max": 35, "evidence": "<what matched and what is missing>"},
    "skills_alignment":     {"score": <0-30>, "max": 30, "evidence": "<which required skills present/absent>"},
    "experience_relevance": {"score": <0-25>, "max": 25, "evidence": "<domain/seniority match analysis>"},
    "summary_format":       {"score": <0-10>, "max": 10, "evidence": "<summary themes found, format issues>"}
  },
  "bonus_points": {
    "total": <0-20>,
    "breakdown": "<bullet list of bonuses awarded and why>"
  },
  "deductions": {
    "total": <0 or positive number — applied negatively>,
    "reasons": "<bullet list of deductions and why>"
  },
  "final_score": <integer, sum of category scores + bonus - deductions, capped at 120>,
  "normalized_score": <integer 0-100, final_score * 100 / 120 rounded>,
  "passed": <true if final_score >= 85>,
  "key_strengths": ["<1-5 strongest match signals>"],
  "improvement_areas": ["<1-5 specific things to fix to improve the score>"],
  "missing_critical": ["<required JD keyword or skill not found in resume>"],
  "missing_preferred": ["<preferred JD keyword not found>"],
  "feedback": "<if not passed: precise instructions — what to add, where, how. If passed: empty string.>"
}
Return ONLY the JSON. No markdown fences. No extra text."""


def evaluate(resume_text: str, jd_text: str) -> dict:
    prompt = f"Job Description:\n{jd_text}\n\nResume to evaluate:\n{resume_text}"
    # HackerRank hiring-agent uses temperature=0.5, top_p=0.9
    raw = chat(_SYSTEM, prompt, temperature=0.5, top_p=0.9)
    result = parse_json(raw, _default())

    # Mirror hiring-agent score.py: cap each category, recompute final
    scores = result.get("scores", {})
    base = 0
    for key, max_val in CATEGORY_MAXES.items():
        cat = scores.get(key, {})
        capped = min(float(cat.get("score", 0)), max_val)
        cat["score"] = capped
        base += capped

    bonus = min(float(result.get("bonus_points", {}).get("total", 0)), MAX_BONUS_POINTS)
    deduct = max(0.0, float(result.get("deductions", {}).get("total", 0)))
    final = min(base + bonus - deduct, MAX_FINAL_SCORE)
    final = max(0.0, final)

    result["final_score"]      = round(final)
    result["normalized_score"] = round(final * 100 / MAX_FINAL_SCORE)
    result["passed"]           = final >= 85
    result["score"]            = result["normalized_score"]  # alias for loop compatibility

    # Expose per-dimension pcts for the loop display
    kw = scores.get("keyword_coverage", {})
    sk = scores.get("skills_alignment", {})
    result["keyword_coverage_pct"]  = round(kw.get("score", 0) / 35 * 100)
    result["skills_alignment_pct"]  = round(sk.get("score", 0) / 30 * 100)

    return result


def _default() -> dict:
    return {
        "scores": {
            "keyword_coverage":     {"score": 0, "max": 35, "evidence": ""},
            "skills_alignment":     {"score": 0, "max": 30, "evidence": ""},
            "experience_relevance": {"score": 0, "max": 25, "evidence": ""},
            "summary_format":       {"score": 0, "max": 10, "evidence": ""},
        },
        "bonus_points": {"total": 0, "breakdown": ""},
        "deductions":   {"total": 0, "reasons": ""},
        "final_score": 0, "normalized_score": 0,
        "passed": False, "score": 0,
        "keyword_coverage_pct": 0, "skills_alignment_pct": 0,
        "key_strengths": [], "improvement_areas": [],
        "missing_critical": [], "missing_preferred": [],
        "feedback": "Evaluation failed — LLM did not return valid JSON.",
    }
