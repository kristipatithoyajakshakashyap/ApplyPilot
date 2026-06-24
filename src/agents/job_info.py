"""Extract structured job info and generate candidate-specific answers in first person."""
from src.llm_client import chat
from src.agents import STYLE_GUIDE, parse_json

_SYSTEM = f"""You are a career coach helping a candidate write job application answers.

{STYLE_GUIDE}

Given the job description and the candidate resume, produce two ready-to-submit answers
the candidate can copy directly into an application form.

Rules:
- responsibilities: 3-5 sentences describing the day-to-day work. Write in second person
  (You will...). Extract only from the JD. Do not invent tasks.
- why_this_role: Write in first person as the candidate (I, my, me). 2-3 sentences.
  Reference specific experience, tools, or projects from the resume that directly connect
  to what this role requires. Be concrete. Name actual companies, tools, or metrics from
  the resume. Never say "you may be interested" or write in second or third person.
- why_this_company: Write in first person as the candidate (I, my, me). 2-3 sentences.
  Reference the company name and a specific product, mission, or technology from the JD.
  Connect it to something concrete in the candidate resume. Never write generic statements
  like "this company aligns with my goals". Name the company and its product specifically.
- start_date: Extract from JD. Default to "Immediate".
- end_date: For contract or fixed-term roles only. Default to "N/A (Full-time)".

Example style for why_this_role (follow this tone exactly):
  "I have spent 3.5 years building ML pipelines and LLM evaluation frameworks in production,
  most recently at Flagstar Bank where I productionized multi-agent workflows using LangGraph
  and CrewAI. This role matches that work directly, and the focus on tabular data and platform
  engineering is the direction I want to deepen."

Example style for why_this_company (follow this tone exactly):
  "Ikigai Labs is building something I find genuinely compelling: a no-code AI platform for
  tabular data that brings ML to business users without requiring data science expertise. My
  work on XGBoost pipelines and ETL systems at Lognormal Analytics maps directly to the
  problems Ikigai is solving, and I want to work on a product that sits at that intersection."

Return a single JSON object:
{{
  "company_name": "<company name>",
  "job_role": "<exact job title from JD>",
  "location": "<city, state or Remote>",
  "responsibilities": "<day-to-day responsibilities paragraph in second person>",
  "start_date": "<start date>",
  "end_date": "<end date or N/A>",
  "why_this_role": "<first-person answer, copy-paste ready>",
  "why_this_company": "<first-person answer, copy-paste ready>"
}}
Return ONLY the JSON. No markdown fences. No extra text."""


def extract_job_info(jd_text: str, resume_text: str, company: str = "", role: str = "") -> dict:
    prompt = (
        f"Company: {company or 'Extract from JD'}\n"
        f"Role: {role or 'Extract from JD'}\n\n"
        f"Job Description:\n{jd_text}\n\n"
        f"Candidate Resume:\n{resume_text[:3500]}"
    )
    raw = chat(_SYSTEM, prompt)
    return parse_json(raw, {
        "company_name": company or "Unknown",
        "job_role": role or "Unknown",
        "location": "Unknown",
        "responsibilities": "See job description.",
        "start_date": "Immediate",
        "end_date": "N/A (Full-time)",
        "why_this_role": "",
        "why_this_company": "",
    })
