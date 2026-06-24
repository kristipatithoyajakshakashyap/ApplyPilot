"""Scrape a job posting URL using requests first, Playwright fallback for JS-heavy sites."""
import re
import requests
from bs4 import BeautifulSoup
from src.llm_client import chat
from src.agents import parse_json

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_LLM_SYSTEM = """You are a job posting parser. Extract structured data from raw job page text.

Return a single JSON object with these keys:
{
  "company_name": "<company name>",
  "job_role": "<exact job title>",
  "location": "<city, state or Remote>",
  "job_description": "<full job description — include ALL responsibilities, requirements, qualifications, and skills>",
  "start_date": "<start date if mentioned, else Immediate>",
  "end_date": "<end date if contract role, else N/A>"
}
Return ONLY the JSON. No markdown fences. No extra text."""

_JS_SIGNALS = [
    "linkedin.com", "greenhouse.io", "lever.co", "workday.com",
    "myworkdayjobs.com", "taleo.net", "icims.com",
    "careers.blackline.com", "careers.google.com", "jobs.apple.com",
    "smartrecruiters.com", "jobvite.com", "bamboohr.com",
    "ashbyhq.com", "rippling.com", "breezy.hr",
]


def _is_js_heavy(url: str) -> bool:
    return any(s in url for s in _JS_SIGNALS)


def _parse_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


def _scrape_with_requests(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        text = _parse_html(resp.text)
        if len(text) < 300:
            return None  # too little — probably JS-gated
        return text[:8000]
    except Exception:
        return None


def _scrape_with_playwright(url: str) -> str | None:
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=_HEADERS["User-Agent"],
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
            except PWTimeout:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
            # scroll to trigger lazy-loaded content
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
            html = page.content()
            browser.close()
        text = _parse_html(html)
        return text[:8000] if len(text) >= 300 else None
    except Exception as exc:
        return None


def _llm_extract(raw_text: str, url: str, fallback: dict) -> dict:
    raw = chat(_LLM_SYSTEM, f"Job page text from {url}:\n\n{raw_text}")
    result = parse_json(raw, fallback)
    result["url"] = url
    result["scrape_failed"] = False
    return result


def scrape_job(url: str) -> dict:
    fallback = {
        "company_name": "", "job_role": "", "location": "",
        "job_description": "", "start_date": "Immediate", "end_date": "N/A",
        "url": url, "scrape_failed": False,
    }

    # 1. Try plain HTTP first (fast)
    text = None
    if not _is_js_heavy(url):
        text = _scrape_with_requests(url)

    # 2. Fall back to Playwright (headless Chrome) for JS-heavy or failed requests
    if not text:
        print("      (JS site detected — launching headless browser...)")
        text = _scrape_with_playwright(url)

    if not text:
        fallback["scrape_failed"] = True
        fallback["scrape_error"] = (
            f"Could not extract content from {url}.\n"
            f"The page may require login or block automated access.\n"
            f"Copy the job description manually and use:\n"
            f"  python main.py --company \"<Company>\" --jd jd.txt --url \"{url}\" --output <file>.pdf"
        )
        return fallback

    return _llm_extract(text, url, fallback)
