from src.llm_client import chat
from src.skills import load_skill
from src.agents import STYLE_GUIDE, parse_json

_SKILL = load_skill("job-matcher")

_SYSTEM = f"""{_SKILL}

{STYLE_GUIDE}

Return your full analysis as a single JSON object. Schema:
{{
  "match_score": <integer 0-100>,
  "dimension_scores": {{
    "hard_skills": <int>,
    "soft_skills": <int>,
    "experience": <int>,
    "domain": <int>,
    "resonance": <int>
  }},
  "missing_keywords": [
    {{"keyword": "<kw>", "importance": "<Critical|High|Medium|Low>", "where": "<where to add it>"}}
  ],
  "strengths": ["<strength>"],
  "red_flags": ["<flag>"],
  "top_edits": ["<edit description>"]
}}
Return ONLY the JSON. No markdown fences. No extra text.
"""


def match_jd(resume_text: str, jd_text: str) -> dict:
    prompt = f"Resume:\n{resume_text}\n\nJob Description:\n{jd_text}"
    raw = chat(_SYSTEM, prompt)
    return parse_json(raw, {
        "match_score": 0, "dimension_scores": {},
        "missing_keywords": [], "strengths": [],
        "red_flags": [], "top_edits": [],
    })
