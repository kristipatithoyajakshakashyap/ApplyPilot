"""
Job discovery + automated resume optimization for ApplyPilot.

For each role/location:
  1. Scrape listings from LinkedIn, Indeed, Google Jobs, Jobright.ai
  2. LLM validates each listing against requested role + location
  3. For each validated job: run full ATS audit + resume optimization pipeline
  4. Save optimized PDF to job_resumes/<Company>_<Role>.pdf
  5. Log all results to jobs.csv (same columns as applications.csv)
"""
import csv
import logging
import os
import re
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

logging.getLogger("JobSpy").setLevel(logging.CRITICAL)

RESUMES_BASE = Path("resumes")
RESUMES_DIR  = RESUMES_BASE  # updated per-role inside discover_jobs

MAX_EVAL_ITERATIONS = 5
ATS_TARGET  = 85
EVAL_TARGET = 85

_DEFAULT_HOURS_OLD = 168  # 7 days

# Mirrors applications.csv columns from main.py
CSV_FIELDS = [
    "timestamp", "company_name", "job_role", "location", "job_url",
    "original_ats_score", "original_verdict",
    "optimized_ats_score", "optimized_verdict",
    "eval_score", "jd_match_score", "eval_iterations", "corrections_count", "suggested_resume",
    "resume_path",
    "why_this_role", "why_this_company", "responsibilities",
    "start_date", "end_date", "job_description",
]

_JOBSPY_SITES = ["linkedin", "indeed", "google"]

_COL_MAP = {
    "company":     "company_name",
    "title":       "job_role",
    "location":    "job_location",
    "description": "job_description",
    "job_url":     "job_url",
}

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _jobspy():
    try:
        from jobspy import scrape_jobs
        return scrape_jobs
    except ImportError:
        raise SystemExit(
            "\nError: python-jobspy is not installed.\n"
            "Run:  pip install python-jobspy\n"
        )


def _norm(val) -> str:
    import math
    if val is None:
        return ""
    try:
        if math.isnan(float(val)):
            return ""
    except (TypeError, ValueError):
        pass
    return str(val).replace("\n", " ").replace("\r", " ").strip()


def _role_slug(role: str) -> str:
    """'ML Engineer' -> 'ml_engineer' — used as the CSV filename stem."""
    return re.sub(r"[^\w]+", "_", role.lower()).strip("_")


def _role_folder(role: str) -> str:
    """'ML Engineer' -> 'ML_Engineer' — used as the resumes sub-folder name."""
    return re.sub(r"[^\w\s-]+", "", role).strip().replace(" ", "_")


def _auto_filename(company: str, role: str) -> str:
    co = re.sub(r"[^\w]+", "_", company).strip("_")
    ro = re.sub(r"[^\w]+", "_", role).strip("_")
    return f"{co}_{ro}.pdf"


def _load_existing_urls(csv_path: Path) -> set:
    if not csv_path.exists():
        return set()
    with open(csv_path, newline="", encoding="utf-8") as fh:
        return {
            row.get("job_url", "").strip()
            for row in csv.DictReader(fh)
            if row.get("job_url", "").strip()
        }


def _is_excluded(company: str, exclude_list: list) -> bool:
    name = company.lower()
    return any(ex.lower() in name for ex in exclude_list if ex)

# ─── source scrapers ──────────────────────────────────────────────────────────

def _scrape_jobspy(role: str, location: str, count: int, hours_old: int | None = _DEFAULT_HOURS_OLD) -> list:
    scrape_jobs = _jobspy()
    try:
        df = scrape_jobs(
            site_name=_JOBSPY_SITES,
            search_term=role,
            location=location,
            results_wanted=count,
            hours_old=hours_old,
            country_indeed="USA",
            linkedin_fetch_description=True,
            verbose=0,
        )
        if df is None or df.empty:
            return []
        out = []
        for _, row in df.iterrows():
            url = _norm(row.get("job_url", ""))
            if not url:
                continue
            out.append({our: _norm(row.get(js, "")) for js, our in _COL_MAP.items()})
        return out
    except Exception as e:
        print(f"      jobspy error ({location}): {e}")
        return []


def _scrape_jobright(role: str, location: str, count: int) -> list:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    params = urllib.parse.urlencode({"q": role, "location": location})
    url = f"https://jobright.ai/jobs?{params}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=_UA)
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
            jobs_data = page.evaluate("""() => {
                const seen = new Set();
                const results = [];
                for (const el of document.querySelectorAll('a[href*="/jobs/info/"], a[href*="/job/"]')) {
                    const href = el.href || '';
                    if (!href || seen.has(href)) continue;
                    seen.add(href);
                    const card = el.closest('article') || el.closest('[class*="card"]') || el.parentElement;
                    const titleEl = card && card.querySelector('h2,h3,h4,[class*="title"],[class*="role"]');
                    const compEl  = card && card.querySelector('[class*="company"],[class*="employer"]');
                    const locEl   = card && card.querySelector('[class*="location"],[class*="city"]');
                    results.push({
                        url:      href,
                        title:    titleEl ? titleEl.textContent.trim() : el.textContent.trim(),
                        company:  compEl  ? compEl.textContent.trim()  : '',
                        location: locEl   ? locEl.textContent.trim()   : '',
                    });
                }
                return results;
            }""")
            browser.close()
        out = []
        for j in jobs_data[:count]:
            if j.get("url") and j.get("title"):
                out.append({
                    "company_name":    j.get("company", ""),
                    "job_role":        j.get("title", ""),
                    "job_location":    j.get("location", ""),
                    "job_description": "",
                    "job_url":         j.get("url", ""),
                })
        return out
    except Exception as e:
        print(f"      Jobright error ({location}): {e}")
        return []


def _scrape_google_jobs(role: str, location: str, count: int) -> list:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    query = f"{role} jobs {location}"
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&ibp=htl;jobs&hl=en"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=_UA, locale="en-US")
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            try:
                page.locator("text=More jobs").first.click(timeout=2000)
                page.wait_for_timeout(1500)
            except Exception:
                pass
            jobs_data = page.evaluate("""() => {
                const results = [];
                const items = document.querySelectorAll('[data-ved] li, .iFjolb, [jsname] li');
                for (const item of items) {
                    const titleEl = item.querySelector('.BjJfJf, [class*="title"], h3, b');
                    const compEl  = item.querySelector('.vNEEBe, [class*="company"]');
                    const locEl   = item.querySelector('.Qk80Jf, [class*="location"]');
                    const linkEl  = item.querySelector('a[href]');
                    if (!titleEl) continue;
                    results.push({
                        title:    titleEl.textContent.trim(),
                        company:  compEl  ? compEl.textContent.trim()  : '',
                        location: locEl   ? locEl.textContent.trim()   : '',
                        url:      linkEl  ? linkEl.href                : '',
                    });
                }
                return results;
            }""")
            browser.close()
        out = []
        for j in jobs_data[:count]:
            if j.get("title") and j.get("url"):
                out.append({
                    "company_name":    j.get("company", ""),
                    "job_role":        j.get("title", ""),
                    "job_location":    j.get("location", ""),
                    "job_description": "",
                    "job_url":         j.get("url", ""),
                })
        return out
    except Exception as e:
        print(f"      Google Jobs error ({location}): {e}")
        return []


# ─── aggregate + validate ─────────────────────────────────────────────────────

# Seniority search terms to use per level when querying job boards
_LEVEL_PREFIXES = {
    "junior": ["junior", "entry level", "associate"],
    "mid":    [""],           # no prefix — mid is the unmarked default
    "senior": ["senior", "sr", "lead", "principal", "staff"],
}


def _level_search_terms(role: str, level: str | None) -> list:
    """Return a list of search strings to use for jobspy / Playwright scrapers."""
    if not level:
        return [role]
    return [f"{prefix} {role}".strip() for prefix in _LEVEL_PREFIXES.get(level, [""])]


def _scrape_all_sources(role: str, locations: list, fetch_target: int, level: str | None = None, hours_old: int | None = _DEFAULT_HOURS_OLD) -> list:
    combined = {}
    per_source = max(fetch_target, 10)
    search_terms = _level_search_terms(role, level)

    for location in locations:
        for term in search_terms:
            print(f"    [{location}] LinkedIn/Indeed/Google Jobs (jobspy): {term!r}...")
            for job in _scrape_jobspy(term, location, per_source, hours_old=hours_old):
                url = job.get("job_url", "")
                if url and url not in combined:
                    combined[url] = job

            print(f"    [{location}] Jobright.ai: {term!r}...")
            for job in _scrape_jobright(term, location, per_source):
                url = job.get("job_url", "")
                if url and url not in combined:
                    combined[url] = job

            print(f"    [{location}] Google Jobs / Workday / Greenhouse (Playwright): {term!r}...")
            for job in _scrape_google_jobs(term, location, per_source):
                url = job.get("job_url", "")
                if url and url not in combined:
                    combined[url] = job

    return list(combined.values())


def _validate(candidates: list, role: str, locations: list, level: str | None = None, candidate: dict | None = None) -> list:
    if not candidates:
        return []
    print(f"  Running AI validator on {len(candidates)} candidates...")
    try:
        from src.agents.job_validator import validate_jobs
        result = validate_jobs(candidates, role, locations, level=level, candidate=candidate or {})
        print(f"  Validated: {len(result)} genuine matches.")
        return result
    except Exception as e:
        print(f"  Warning: AI validator failed ({e}). Keeping all candidates.")
        return candidates


# --- full optimization pipeline ---

def _run_pipeline(job: dict, resume_text: str, resume_path: str, existing_urls: set | None = None) -> dict | None:
    from src.agents.ats_auditor import audit_ats
    from src.agents.job_matcher import match_jd
    from src.agents.resume_optimizer import optimize_bullets
    from src.agents.resume_writer import rewrite_resume
    from src.agents.evaluator import evaluate
    from src.agents.job_info import extract_job_info
    from src.pdf_builder import build_pdf
    from src.pdf_reader import extract_text
    from src.web_scraper import scrape_job
    from src.report import print_report

    company  = job.get("company_name", "Unknown")
    role_ttl = job.get("job_role", "Unknown")
    location = job.get("job_location", "")
    url      = job.get("job_url", "")

    # Guard: skip if URL already seen (CSV or DB)
    if existing_urls is not None and url and url in existing_urls:
        print(f"    Skipped -- already processed: {url}")
        return None

    _pipeline_start = time.time()

    # 1. Get full JD -- fall back to scraping if description is short
    jd_text = job.get("job_description", "").strip()
    if len(jd_text) < 200 and url:
        print(f"    Fetching full JD from URL...")
        scraped = scrape_job(url)
        if not scraped.get("scrape_failed"):
            jd_text  = scraped.get("job_description") or scraped.get("jd_text") or jd_text
            company  = scraped.get("company_name", company) or company
            role_ttl = scraped.get("job_role", role_ttl) or role_ttl
            location = scraped.get("location", location) or location

    if not jd_text.strip():
        print(f"    Skipped -- could not get JD.")
        return None

    # JD-level dedup: same company + role + JD fingerprint = already processed
    from src.db import is_duplicate_jd, mark_processed as db_mark_processed, mark_skipped as db_mark_skipped
    if is_duplicate_jd(company, role_ttl, jd_text):
        print(f"    Skipped -- same company/role/JD already in DB.")
        db_mark_skipped(url)
        return None

    # 2. Initial ATS audit on original resume
    print(f"    [1] Initial ATS audit...")
    ats_orig  = audit_ats(resume_text, jd_text)
    ats_dims  = ats_orig.get("dimension_scores", {})
    print(f"        ATS: {ats_orig.get('score','?')}/100 [{ats_orig.get('verdict','?')}]  "
          f"kw={ats_dims.get('keyword_coverage','?')}/35  fmt={ats_dims.get('format_compliance','?')}/30")

    # 3. JD match + bullet optimization
    print(f"    [2] JD match analysis...")
    jd_match  = match_jd(resume_text, jd_text)
    print(f"        Match: {jd_match.get('match_score','?')}/100  "
          f"missing critical: {sum(1 for k in jd_match.get('missing_keywords',[]) if k.get('importance') in ('Critical','High'))}")
    print(f"    [3] Rewriting bullets toward JD...")
    optimized = optimize_bullets(resume_text, jd_match, jd_text=jd_text)
    print(f"        {len(optimized.get('rewrites', []))} bullets rewritten.")

    # 4. Job info + answers
    print(f"    [4] Generating job info answers...")
    job_info = extract_job_info(jd_text, resume_text, company, role_ttl)
    company  = job_info.get("company_name", company) or company
    role_ttl = job_info.get("job_role", role_ttl) or role_ttl

    # 5. Output path
    RESUMES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESUMES_DIR / _auto_filename(company, role_ttl)

    # 6. Evaluation loop
    print(f"    [5] Optimization loop (target: ATS >= {ATS_TARGET} and Eval >= {EVAL_TARGET})...")
    new_resume = {}
    eval_result = {}
    ats_loop   = {}
    evaluator_feedback = ""
    missing_critical: list = []
    missing_preferred: list = []
    ats_issues: list = []
    iterations_used = 0

    for iteration in range(1, MAX_EVAL_ITERATIONS + 1):
        iterations_used = iteration
        print(f"        Iteration {iteration}/{MAX_EVAL_ITERATIONS}: rewriting...")
        new_resume = rewrite_resume(
            resume_text, optimized, jd_match,
            jd_text=jd_text,
            evaluator_feedback=evaluator_feedback,
            missing_critical=missing_critical,
            missing_preferred=missing_preferred,
            ats_issues=ats_issues,
            iteration=iteration,
        )
        build_pdf(new_resume, str(out_path))
        new_text = extract_text(str(out_path))

        eval_result = evaluate(new_text, jd_text)
        ats_loop    = audit_ats(new_text, jd_text)

        ev_score  = eval_result.get("score", 0)
        ats_score = ats_loop.get("score", 0)
        ev_passed  = ev_score  >= EVAL_TARGET
        ats_passed = ats_score >= ATS_TARGET

        sc_ev   = eval_result.get("scores", {})
        os_s    = round(sc_ev.get("open_source",      {}).get("score", 0))
        sp_s    = round(sc_ev.get("self_projects",    {}).get("score", 0))
        pr_s    = round(sc_ev.get("production",       {}).get("score", 0))
        ts_s    = round(sc_ev.get("technical_skills", {}).get("score", 0))
        raw_ev  = eval_result.get("final_score", ev_score)
        bonus   = eval_result.get("bonus_points", {}).get("total", 0)
        deduct  = eval_result.get("deductions", {}).get("total", 0)
        ad      = ats_loop.get("dimension_scores", {})
        print(f"        Evaluator : {ev_score}/100  raw={raw_ev}/120  os={os_s}/35  sp={sp_s}/30  prod={pr_s}/25  tech={ts_s}/10  bonus=+{bonus}  deduct=-{deduct}  {'OK' if ev_passed else 'FAIL'}")
        print(f"        ATS       : {ats_score}/100  fmt={ad.get('format_compliance','?')}/30  kw={ad.get('keyword_coverage','?')}/35  {'OK' if ats_passed else 'FAIL'}")

        if ev_passed and ats_passed:
            print(f"        Both targets met. PASSED.")
            break

        evaluator_feedback = eval_result.get("feedback", "")
        missing_critical   = eval_result.get("missing_critical", [])
        missing_preferred  = eval_result.get("missing_preferred", [])
        ats_issues = ats_loop.get("critical_issues", []) + ats_loop.get("high_priority", [])
        if missing_critical:
            print(f"        Missing keywords : {', '.join(missing_critical[:6])}")
        if ats_issues:
            print(f"        ATS issues       : {'; '.join(ats_issues[:3])}")

    final_ev  = eval_result.get("score", 0)
    final_ats = ats_loop.get("score", 0)
    if not (final_ev >= EVAL_TARGET and final_ats >= ATS_TARGET):
        print(f"        Warning: best-effort after {MAX_EVAL_ITERATIONS} iterations "
              f"(Eval={final_ev} ATS={final_ats}).")

    elapsed = time.time() - _pipeline_start
    print(f"    PDF saved: {out_path}")

    # 7. Detailed report (same as main.py)
    suggestion = print_report(
        ats_orig=ats_orig,
        ats_opt=ats_loop,
        jd_match=jd_match,
        new_resume=new_resume,
        job_info={**job_info, "location": location},
        eval_result=eval_result,
        iterations=iterations_used,
        elapsed_secs=elapsed,
    )

    row = {
        "timestamp":           datetime.now().strftime("%Y-%m-%d %H:%M"),
        "company_name":        company,
        "job_role":            role_ttl,
        "location":            location,
        "job_url":             url,
        "original_ats_score":  ats_orig.get("score", 0),
        "original_verdict":    ats_orig.get("verdict", ""),
        "optimized_ats_score": final_ats,
        "optimized_verdict":   ats_loop.get("verdict", ""),
        "eval_score":          final_ev,
        "jd_match_score":      jd_match.get("match_score", 0),
        "eval_iterations":     iterations_used,
        "corrections_count":   len(new_resume.get("corrections", [])),
        "suggested_resume":    suggestion,
        "resume_path":         str(out_path.resolve()),
        "why_this_role":       job_info.get("why_this_role", ""),
        "why_this_company":    job_info.get("why_this_company", ""),
        "responsibilities":    job_info.get("responsibilities", ""),
        "start_date":          job_info.get("start_date", "Immediate"),
        "end_date":            job_info.get("end_date", "N/A"),
        "job_description":     jd_text[:1000],
    }
    db_mark_processed(url, company, role_ttl, jd_text, row)
    return row


# ─── CSV writer ───────────────────────────────────────────────────────────────

def _write_row(row: dict, csv_path: Path) -> None:
    is_new = not csv_path.exists()
    for attempt in range(10):
        try:
            with open(csv_path, "a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
                if is_new:
                    writer.writeheader()
                    is_new = False
                writer.writerow(row)
            return
        except PermissionError:
            if attempt == 0:
                print(f"\n  {csv_path.name} is locked (open in Excel?). Close it and press Enter...", end="", flush=True)
                input()
            else:
                time.sleep(1)



# ─── mode-specific row builders ──────────────────────────────────────────────

def _scrape_only_row(job: dict) -> dict:
    return {
        "timestamp":           datetime.now().strftime("%Y-%m-%d %H:%M"),
        "company_name":        job.get("company_name", ""),
        "job_role":            job.get("job_role", ""),
        "location":            job.get("job_location", ""),
        "job_url":             job.get("job_url", ""),
        "original_ats_score":  "",
        "original_verdict":    "",
        "optimized_ats_score": "",
        "optimized_verdict":   "",
        "eval_score":          "",
        "jd_match_score":      "",
        "eval_iterations":     "",
        "corrections_count":   "",
        "suggested_resume":    "",
        "resume_path":         "",
        "why_this_role":       "",
        "why_this_company":    "",
        "responsibilities":    "",
        "start_date":          "",
        "end_date":            "",
        "job_description":     job.get("job_description", "")[:1000],
    }


def _ats_report_row(job: dict, resume_text: str) -> dict | None:
    from src.agents.ats_auditor import audit_ats
    from src.web_scraper import scrape_job

    company  = job.get("company_name", "Unknown")
    role_ttl = job.get("job_role", "Unknown")
    location = job.get("job_location", "")
    url      = job.get("job_url", "")

    jd_text = job.get("job_description", "").strip()
    if len(jd_text) < 200 and url:
        scraped = scrape_job(url)
        if not scraped.get("scrape_failed"):
            jd_text  = scraped.get("job_description") or scraped.get("jd_text") or jd_text
            company  = scraped.get("company_name", company) or company
            role_ttl = scraped.get("job_role", role_ttl) or role_ttl
            location = scraped.get("location", location) or location

    if not jd_text.strip():
        print(f"    Skipped -- could not get JD.")
        return None

    ats = audit_ats(resume_text, jd_text)
    ats_score = ats.get("score", 0)
    print(f"    ATS: {ats_score}/100 [{ats.get('verdict','?')}]")
    suggestion = "Original" if ats_score >= 85 else "Optimized recommended"

    row = {
        "timestamp":           datetime.now().strftime("%Y-%m-%d %H:%M"),
        "company_name":        company,
        "job_role":            role_ttl,
        "location":            location,
        "job_url":             url,
        "original_ats_score":  ats_score,
        "original_verdict":    ats.get("verdict", ""),
        "optimized_ats_score": "",
        "optimized_verdict":   "",
        "eval_score":          "",
        "jd_match_score":      "",
        "eval_iterations":     "",
        "corrections_count":   "",
        "suggested_resume":    suggestion,
        "resume_path":         "",
        "why_this_role":       "",
        "why_this_company":    "",
        "responsibilities":    "",
        "start_date":          "",
        "end_date":            "",
        "job_description":     jd_text[:1000],
    }
# ─── public API ───────────────────────────────────────────────────────────────

def discover_jobs(roles: list, locations: list, count: int, level: str | None = None, mode: str = "full", hours_old: int | None = _DEFAULT_HOURS_OLD, candidate: dict | None = None, exclude_companies: list | None = None) -> None:
    """
    Scrape, validate, and optionally optimize jobs for each role.
    Each role gets its own CSV ({role_slug}.csv) and resume subfolder
    (resumes/{role_folder}/) so results are kept cleanly separated.
    """
    from src.db import init_db, load_seen_urls, db_stats

    resume_text = ""
    resume_path = os.getenv("RESUME_PATH", "resume.pdf")
    if mode != "scrape_only":
        from src.pdf_reader import extract_text
        if not Path(resume_path).exists():
            raise SystemExit(f"Error: Resume not found at {resume_path}. Set RESUME_PATH in .env.")
        resume_text = extract_text(resume_path)
        if not resume_text.strip():
            raise SystemExit(f"Error: Could not extract text from {resume_path}.")

    init_db()
    # DB is the primary source of truth; per-role CSVs add an extra safety net
    existing_urls = load_seen_urls()
    total_new = 0
    session_start = time.time()

    stats = db_stats()
    print(f"  DB state: {stats['total']} total | {stats['done']} done | {stats['skipped']} skipped")

    for role in roles:
        global RESUMES_DIR
        # Per-role CSV: ml_engineer.csv, data_scientist.csv, etc.
        role_csv  = Path(f"{_role_slug(role)}.csv")
        # Per-role resume folder: resumes/ML_Engineer/, resumes/Data_Scientist/, etc.
        RESUMES_DIR = RESUMES_BASE / _role_folder(role)
        # Also pull URLs already in this role's CSV (survives DB clear)
        existing_urls |= _load_existing_urls(role_csv)

        role_start = time.time()
        print("\n" + "="*55)
        print(f"Role: {role!r}  ->  {role_csv}  |  resumes/{_role_folder(role)}/")
        print("="*55)

        # ── Scrape ──────────────────────────────────────────────
        scrape_start = time.time()
        raw = _scrape_all_sources(role, locations, count * 5, level=level, hours_old=hours_old)
        scrape_secs = time.time() - scrape_start

        raw = [j for j in raw if j.get("job_url") not in existing_urls]
        if exclude_companies:
            before = len(raw)
            raw = [j for j in raw if not _is_excluded(j.get("company_name", ""), exclude_companies)]
            excluded = before - len(raw)
            if excluded:
                print(f"  Excluded {excluded} job(s) from blocked companies.")

        print(f"  Raw candidates (new only): {len(raw)}  [scraped in {scrape_secs:.0f}s]")

        # ── Validate ─────────────────────────────────────────────
        if mode == "scrape_only":
            validated = raw
            validate_secs = 0.0
        else:
            validate_start = time.time()
            validated = _validate(raw, role, locations, level=level, candidate=candidate)
            validate_secs = time.time() - validate_start
            print(f"  Validated: {len(validated)} genuine matches  [took {validate_secs:.0f}s]")

        to_process = validated[:count]
        if len(to_process) < count:
            print(f"  Note: only {len(to_process)} validated job(s) found (requested {count}).")

        # ── Optimize ─────────────────────────────────────────────
        role_opt_secs = 0.0
        for i, job in enumerate(to_process, 1):
            url = job.get("job_url", "")
            company  = job.get("company_name", "?")
            role_ttl = job.get("job_role", "?")
            print(f"\n  [{i}/{len(to_process)}] {company} — {role_ttl}")
            job_start = time.time()
            try:
                if mode == "scrape_only":
                    result = _scrape_only_row(job)
                elif mode == "ats_report":
                    result = _ats_report_row(job, resume_text)
                else:
                    result = _run_pipeline(job, resume_text, resume_path, existing_urls=existing_urls)
                job_secs = time.time() - job_start
                if result:
                    _write_row(result, role_csv)
                    existing_urls.add(url)
                    total_new += 1
                    role_opt_secs += job_secs
                    jm, js = divmod(int(job_secs), 60)
                    time_str = f"{jm}m {js}s" if jm else f"{js}s"
                    print(f"  Job time: {time_str}")
            except Exception as e:
                print(f"  Error processing job: {e}")

        role_secs = time.time() - role_start
        rm, rs = divmod(int(role_secs), 60)
        print(f"\n  Role summary — scrape {scrape_secs:.0f}s | validate {validate_secs:.0f}s | optimize {role_opt_secs:.0f}s | total {rm}m {rs}s")

    session_secs = time.time() - session_start
    sm, ss = divmod(int(session_secs), 60)
    updated = db_stats()
    sep = "=" * 55
    print(f"\n{sep}")
    print(f"Done. {total_new} new job(s) logged (one CSV per role).")
    if mode != "scrape_only":
        print(f"Resumes saved under: {RESUMES_BASE.resolve()}/")
    print(f"DB: {updated['total']} total | {updated['done']} done | {updated['skipped']} skipped")
    print(f"Total session time: {sm}m {ss}s")
    print(sep)



