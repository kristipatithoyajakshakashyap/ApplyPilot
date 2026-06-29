#!/usr/bin/env python3
"""
Resume optimizer pipeline.

Optimize from a URL (auto-scrape):
    python main.py --url "https://..." --optimize

Optimize with a manual JD file or text:
    python main.py --company "Google" --jd jd.txt --optimize
    python main.py --company "Stripe" --jd "We are looking for..." --optimize

ATS score check only (no PDF generated):
    python main.py --check --url "https://..."
    python main.py --check --jd jd.txt --company "Google"
    python main.py --check --url "https://..." --resume resume_v2.pdf

Output PDF is always saved as optimized/<Company>_<Role>.pdf
RESUME_PATH is read from .env. No --resume arg needed unless overriding.
All runs are logged to applications.csv.
"""
from dotenv import load_dotenv
load_dotenv()

import argparse, os, re, sys, time
from pathlib import Path

MAX_EVAL_ITERATIONS = 5
ATS_TARGET  = 85
EVAL_TARGET = 85
RESUMES_BASE = Path("resumes")


def _preview(text: str, chars: int = 300) -> str:
    s = " ".join(text.split())[:chars]
    return s + "..." if len(text) > chars else s


def _auto_filename(company: str, role: str) -> str:
    co = re.sub(r"[^\w]+", "_", company).strip("_")
    ro = re.sub(r"[^\w]+", "_", role).strip("_")
    return f"{co}_{ro}.pdf"


def _load_url(url: str) -> dict:
    from src.web_scraper import scrape_job
    result = scrape_job(url)
    if result.get("scrape_failed"):
        print(f"\nError: {result['scrape_error']}")
        sys.exit(1)
    return result


def _check_mode(args) -> None:
    from src.pdf_reader import extract_text
    from src.agents.ats_auditor import audit_ats
    from src.agents.evaluator import evaluate

    resume_path = Path(args.resume or os.getenv("RESUME_PATH", "resume.pdf"))
    if not resume_path.exists():
        print(f"Error: Resume not found at {resume_path}.")
        sys.exit(1)

    bar = "=" * 62
    print(f"\n{bar}\n  ATS SCORE CHECK\n{bar}")

    if args.url and not args.jd:
        print("\nScraping job URL...")
        scraped = _load_url(args.url)
        jd_text = scraped.get("job_description", "")
        print(f"  Company: {scraped.get('company_name')}  |  Role: {scraped.get('job_role')}")
    elif args.jd:
        jd_file = Path(args.jd)
        jd_text = jd_file.read_text(encoding="utf-8") if jd_file.exists() else args.jd
    else:
        print("Error: --check requires --url or --jd.")
        sys.exit(1)

    resume_text = extract_text(str(resume_path))
    print(f"\nResume: {resume_path}")
    print(f"JD preview: {_preview(jd_text)}\n")

    print("Running ATS audit...")
    ats = audit_ats(resume_text, jd_text)
    dims_a = ats.get("dimension_scores", {})
    print(f"\n{'─'*40}")
    print(f"  ATS Score        : {ats.get('score','?')}/100  [{ats.get('verdict','?')}]")
    print(f"  Keyword cov.     : {dims_a.get('keyword_coverage','?')}/35  ({ats.get('keyword_coverage_pct') or 0:.1f}%)")
    print(f"  Format           : {dims_a.get('format_compliance','?')}/30")
    print(f"  Sections         : {dims_a.get('section_completeness','?')}/25")
    print(f"  Content          : {dims_a.get('content_quality','?')}/10")
    print(f"  Bonus            : +{ats.get('bonus_points',{}).get('total',0)}")
    print(f"  Deductions       : -{ats.get('deductions',{}).get('total',0)}")
    for issue in ats.get("critical_issues", []):
        print(f"  [CRITICAL] {issue}")
    for issue in ats.get("high_priority", []):
        print(f"  [HIGH]     {issue}")

    print("\nRunning evaluator (HackerRank hiring-agent framework)...")
    ev = evaluate(resume_text, jd_text)
    sc = ev.get("scores", {})
    bp = ev.get("bonus_points", {})
    dd = ev.get("deductions", {})
    print(f"\n  Final score      : {ev.get('final_score','?')}/120  (normalized {ev.get('normalized_score','?')}/100)  ({'PASS' if ev.get('passed') else 'FAIL'})")
    print(f"  Open Source      : {sc.get('open_source',{}).get('score','?')}/35  — {sc.get('open_source',{}).get('evidence','')[:80]}")
    print(f"  Self Projects    : {sc.get('self_projects',{}).get('score','?')}/30  — {sc.get('self_projects',{}).get('evidence','')[:80]}")
    print(f"  Production       : {sc.get('production',{}).get('score','?')}/25  — {sc.get('production',{}).get('evidence','')[:80]}")
    print(f"  Technical Skills : {sc.get('technical_skills',{}).get('score','?')}/10  — {sc.get('technical_skills',{}).get('evidence','')[:80]}")
    print(f"  Bonus points     : +{bp.get('total',0)}  {bp.get('breakdown','')[:80]}")
    print(f"  Deductions       : -{dd.get('total',0)}  {dd.get('reasons','')[:80]}")
    for s in ev.get("key_strengths", []):
        print(f"  [STRENGTH] {s}")
    for kw in ev.get("missing_critical", []):
        print(f"  [MISSING]  {kw}")
    for area in ev.get("improvement_areas", []):
        print(f"  [IMPROVE]  {area}")
    print(f"{'─'*40}\n{bar}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ATS-aware resume optimizer.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--url",      help="Job posting URL (always quote it).")
    parser.add_argument("--company",  help="Company name — used when providing --jd manually.")
    parser.add_argument("--role",     help="Job role/title — used when providing --jd manually.")
    parser.add_argument("--jd",       help="Job description text or path to a .txt file.")
    parser.add_argument("--optimize", action="store_true",
                        help="Run the full optimization pipeline.\n"
                             "Output PDF is auto-named optimized/<Company>_<Role>.pdf")
    parser.add_argument("--check",    action="store_true",
                        help="ATS score check only — no PDF generated.\n"
                             "Requires --url or --jd.")
    parser.add_argument("--resume",   default="",
                        help="Override resume PDF path (default: RESUME_PATH from .env).")
    args = parser.parse_args()

    # ── Route to correct mode ─────────────────────────────────────
    if args.check:
        _check_mode(args)
        return

    if not args.optimize:
        parser.print_help()
        print("\nError: pass --optimize to run the full pipeline, or --check for a score-only audit.")
        sys.exit(1)

    if not args.url and not args.jd:
        print("Error: --optimize requires --url or --jd.")
        sys.exit(1)

    url_mode   = bool(args.url and not args.jd)
    manual_mode = bool(args.jd)

    resume_path = Path(args.resume or os.getenv("RESUME_PATH", "resume.pdf"))
    if not resume_path.exists():
        print(f"Error: Resume not found at {resume_path}. Set RESUME_PATH in .env.")
        sys.exit(1)

    from src.pdf_reader import extract_text
    from src.agents.ats_auditor import audit_ats
    from src.agents.job_matcher import match_jd
    from src.agents.resume_optimizer import optimize_bullets
    from src.agents.resume_writer import rewrite_resume
    from src.agents.evaluator import evaluate
    from src.agents.job_info import extract_job_info
    from src.pdf_builder import build_pdf
    from src.report import print_report
    from src import csv_logger

    bar = "=" * 62
    print(f"\n{bar}\n  RESUME OPTIMIZER\n{bar}")

    # ── Step 1: Load JD ──────────────────────────────────────────
    job_url = args.url or ""
    if url_mode:
        print(f"\n[1/8] Scraping job URL...")
        scraped = _load_url(args.url)
        company_name = scraped.get("company_name", "Unknown")
        job_role     = scraped.get("job_role", "Unknown")
        job_location = scraped.get("location", "Unknown")
        jd_text      = scraped.get("job_description", "")
        jd_start     = scraped.get("start_date", "Immediate")
        jd_end       = scraped.get("end_date", "N/A")
        print(f"      Company : {company_name}")
        print(f"      Role    : {job_role}")
        print(f"      Location: {job_location}")
    else:
        print(f"\n[1/8] Loading job description...")
        jd_file = Path(args.jd)
        jd_text = jd_file.read_text(encoding="utf-8") if jd_file.exists() else args.jd
        company_name = args.company or "Unknown"
        job_role = args.role or ""
        job_location = ""
        jd_start = "Immediate"; jd_end = "N/A"
        if not jd_text.strip():
            print("Error: Job description is empty."); sys.exit(1)

    if not jd_text.strip():
        print("Error: Could not extract job description. Use --jd."); sys.exit(1)

    print(f"\n      --- JD PREVIEW ---\n      {_preview(jd_text)}\n      ------------------")

    # ── Step 2: Extract resume ────────────────────────────────────
    print(f"\n[2/8] Extracting resume from {resume_path}...")
    resume_text = extract_text(str(resume_path))
    print(f"      {len(resume_text)} chars extracted.")

    # ── Step 3: ATS audit (original) ─────────────────────────────
    print(f"\n[3/8] ATS audit — original resume...")
    ats_original = audit_ats(resume_text, jd_text)
    print(f"      Score: {ats_original.get('score','?')}/100  [{ats_original.get('verdict','?')}]")

    # ── Step 4: JD match ─────────────────────────────────────────
    print(f"\n[4/8] Matching resume against JD...")
    jd_match = match_jd(resume_text, jd_text)
    print(f"      Match score: {jd_match.get('match_score','?')}/100")

    # ── Step 5: Bullet optimization ──────────────────────────────
    print(f"\n[5/8] Optimizing bullets with XYZ formula...")
    optimized = optimize_bullets(resume_text, jd_match, jd_text=jd_text)
    print(f"      {len(optimized.get('rewrites', []))} bullets rewritten.")

    # ── Step 6: Job info + answers ───────────────────────────────
    print(f"\n[6/8] Extracting job info and generating answers...")
    job_info = extract_job_info(jd_text, resume_text, company_name, job_role)
    if url_mode:
        job_info.setdefault("location", job_location)
        job_info.setdefault("start_date", jd_start)
        job_info.setdefault("end_date", jd_end)
    print(f"      Company: {job_info.get('company_name')} | Role: {job_info.get('job_role')}")

    _resolved_role    = job_info.get("job_role", job_role or "Role")
    _resolved_company = job_info.get("company_name", company_name or "Company")
    _role_folder = re.sub(r"[^\w\s-]+", "", _resolved_role).strip().replace(" ", "_")
    output_dir = RESUMES_BASE / _role_folder
    output_dir.mkdir(parents=True, exist_ok=True)

    _filename = _auto_filename(_resolved_company, _resolved_role)
    output_path = output_dir / _filename
    print(f"      Output: {output_path}")

    # ── Step 7: Evaluation loop ───────────────────────────────────
    print(f"\n[7/8] Building optimized resume (evaluator >= {EVAL_TARGET} and ATS >= {ATS_TARGET})...")
    new_resume = {}
    eval_result = {}
    ats_loop = {}
    evaluator_feedback = ""
    missing_critical: list = []
    missing_preferred: list = []
    ats_issues: list = []
    iterations_used = 0

    for iteration in range(1, MAX_EVAL_ITERATIONS + 1):
        iterations_used = iteration
        print(f"\n      Iteration {iteration}/{MAX_EVAL_ITERATIONS}: rewriting...")
        new_resume = rewrite_resume(
            resume_text, optimized, jd_match,
            jd_text=jd_text,
            evaluator_feedback=evaluator_feedback,
            missing_critical=missing_critical,
            missing_preferred=missing_preferred,
            ats_issues=ats_issues,
            iteration=iteration,
        )
        build_pdf(new_resume, str(output_path))
        new_text = extract_text(str(output_path))

        eval_result = evaluate(new_text, jd_text)
        ats_loop    = audit_ats(new_text, jd_text)

        ev_score  = eval_result.get("score", 0)
        ats_score = ats_loop.get("score", 0)
        ev_passed  = ev_score  >= EVAL_TARGET
        ats_passed = ats_score >= ATS_TARGET
        both_pass  = ev_passed and ats_passed

        sc       = eval_result.get("scores", {})
        os_s     = round(sc.get("open_source",      {}).get("score", 0))
        sp_s     = round(sc.get("self_projects",    {}).get("score", 0))
        pr_s     = round(sc.get("production",       {}).get("score", 0))
        ts_s     = round(sc.get("technical_skills", {}).get("score", 0))
        final    = eval_result.get("final_score", ev_score)
        bonus    = eval_result.get("bonus_points", {}).get("total", 0)
        deduct   = eval_result.get("deductions", {}).get("total", 0)
        ats_dims = ats_loop.get("dimension_scores", {})
        print(f"      Evaluator : {ev_score}/100  raw={final}/120  os={os_s}/35  sp={sp_s}/30  prod={pr_s}/25  tech={ts_s}/10  bonus=+{bonus}  deduct=-{deduct}  {'OK' if ev_passed else 'FAIL'}")
        print(f"      ATS       : {ats_score}/100  fmt={ats_dims.get('format_compliance','?')}/30  kw={ats_dims.get('keyword_coverage','?')}/35  {'OK' if ats_passed else 'FAIL'}")

        if both_pass:
            print(f"      Both scores >= {EVAL_TARGET}. PASSED.")
            break

        evaluator_feedback = eval_result.get("feedback", "")
        missing_critical   = eval_result.get("missing_critical", [])
        missing_preferred  = eval_result.get("missing_preferred", [])
        ats_issues = ats_loop.get("critical_issues", []) + ats_loop.get("high_priority", [])
        if missing_critical:
            print(f"      Missing keywords : {', '.join(missing_critical[:6])}")
        if ats_issues:
            print(f"      ATS issues       : {'; '.join(ats_issues[:3])}")

    if not (eval_result.get("score", 0) >= EVAL_TARGET and ats_loop.get("score", 0) >= ATS_TARGET):
        print(f"\n      Warning: could not reach {EVAL_TARGET} on both scores after {MAX_EVAL_ITERATIONS} iterations.")
        print(f"      Evaluator={eval_result.get('score',0)}  ATS={ats_loop.get('score',0)} — best-effort resume saved.")

    # ── Step 8: Final report + log ────────────────────────────────
    print(f"\n[8/8] Logging...")
    ats_optimized = ats_loop
    elapsed_total = time.time() - _optimize_start

    suggestion = print_report(
        ats_orig=ats_original,
        ats_opt=ats_optimized,
        jd_match=jd_match,
        new_resume=new_resume,
        job_info=job_info,
        eval_result=eval_result,
        iterations=iterations_used,
        elapsed_secs=elapsed_total,
    )

    _log_row = {
        "company_name":        job_info.get("company_name", company_name),
        "job_role":            job_info.get("job_role", job_role),
        "location":            job_info.get("location", ""),
        "job_url":             job_url,
        "original_ats_score":  ats_original.get("score", 0),
        "original_verdict":    ats_original.get("verdict", ""),
        "optimized_ats_score": ats_optimized.get("score", 0),
        "optimized_verdict":   ats_optimized.get("verdict", ""),
        "eval_score":          eval_result.get("score", 0),
        "jd_match_score":      jd_match.get("match_score", 0),
        "eval_iterations":     iterations_used,
        "corrections_count":   len(new_resume.get("corrections", [])),
        "suggested_resume":    suggestion,
        "resume_path":         str(output_path.resolve()),
        "why_this_role":       job_info.get("why_this_role", ""),
        "why_this_company":    job_info.get("why_this_company", ""),
        "responsibilities":    job_info.get("responsibilities", ""),
        "start_date":          job_info.get("start_date", ""),
        "end_date":            job_info.get("end_date", ""),
        "job_description":     jd_text[:1000],
    }
    csv_logger.log(_log_row)
    from src.db import init_db, mark_processed as _db_mark
    init_db()
    _db_mark(job_url, _log_row["company_name"], _log_row["job_role"], jd_text, _log_row)
    print(f"      Logged to applications.csv + applypilot.db")
    print(f"Optimized resume: {output_path.resolve()}")
    print(f"{bar}\n")


if __name__ == "__main__":
    main()
