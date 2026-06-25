# ApplyPilot

> AI-powered job search automation: discovers jobs, filters by your eligibility, optimizes your resume for each one using the HackerRank scoring framework, and saves an ATS-ready PDF — all from one command.

---

## What It Does

ApplyPilot has two tools that work together:

### 1. Resume Optimizer (`main.py`)

Give it a single job URL or JD and it:

1. Scrapes the job posting (including JS-rendered portals via Playwright)
2. Audits your resume against the job using the HackerRank ATS scoring framework
3. Rewrites every bullet using Google's XYZ formula (result → metric → method)
4. Rewrites the full resume, skills section, summary, and experience to match the JD
5. Runs up to 5 evaluation iterations until both ATS score and JD match score reach 85+
6. Generates a single-page ATS-safe PDF → `optimized/<Company>_<Role>.pdf`
7. Generates first-person "why this role" and "why this company" answers
8. Logs every run to `applications.csv`

### 2. Job Discovery + Bulk Optimizer (`scrape_jobs.py`)

Configure once in `job_search_config.yml`, then just run `python scrape_jobs.py`. It:

1. Scrapes job listings from **LinkedIn, Indeed, Google Jobs, Jobright.ai, Workday, Greenhouse, Lever**
2. Filters by **seniority level** (junior / mid / senior) using role-prefixed search terms
3. Runs an **AI validator** to reject off-topic listings, wrong seniority, and ineligible jobs (US citizenship required, security clearance, no sponsorship, federal/DoD roles)
4. Skips **excluded companies** you list in the config
5. Runs the selected **pipeline mode** on each validated job:
   - `scrape_only` - save listings to CSV, zero LLM calls
   - `ats_report` - ATS score on your original resume, no rewrite
   - `full` - complete optimization + optimized PDF
6. Saves an optimized PDF per job → `job_resumes/<Company>_<Role>.pdf`
7. Appends every result to `jobs.csv` (same columns as `applications.csv`)

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/applypilot.git
cd applypilot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Install the Playwright browser (one-time)

Required for JavaScript-rendered job portals and Google Jobs scraping.

```bash
python -m playwright install chromium
```

### 4. Create your `.env` file

```bash
cp .env.example .env
```

Fill in your values:

```env
# Path to your resume PDF
RESUME_PATH=resume.pdf

# LLM provider — openai | featherless | ollama
LLM_PROVIDER=featherless

# Featherless (recommended — free tier, no GPU needed)
FEATHERLESS_API_KEY=your_key_here
FEATHERLESS_MODEL=Qwen/Qwen2.5-72B-Instruct

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Ollama (local, fully private)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

### 5. Add your resume

```
applypilot/
└── resume.pdf   ← your resume goes here
```

---

## Usage

### Resume Optimizer (`main.py`)

#### --optimize - Full Pipeline

Rewrites and optimizes your resume for a single job. PDF auto-named `optimized/<Company>_<Role>.pdf`.

```bash
# Optimize from a job URL (scrapes company, role, and JD automatically)
python main.py --url "https://careers.blackline.com/jobs/7512?lang=en-us" --optimize

# Optimize from a Greenhouse posting
python main.py --url "https://boards.greenhouse.io/stripe/jobs/12345" --optimize

# Optimize using a JD saved in a text file (when the site blocks scraping)
python main.py --company "Google" --jd jd.txt --optimize

# Use a different resume than the .env default for one run
python main.py --url "https://jobs.google.com/jobs/12345" --optimize --resume resume_v2.pdf
```

> **Windows CMD/PowerShell:** Always quote URLs. The `&` character in query strings splits the command if unquoted.

#### --check — ATS Score Only (no PDF)

Scores your resume against a job in seconds without generating a PDF.

```bash
python main.py --check --url "https://jobs.lever.co/company/role-id"
python main.py --check --jd jd.txt --company "Google"
```

---

### Job Discovery + Bulk Optimizer (`scrape_jobs.py`)

#### Config-driven (recommended)

Edit `job_search_config.yml` once, then just run:

```bash
python scrape_jobs.py
```

CLI args override config values when passed explicitly:

```bash
python scrape_jobs.py --roles "ML Engineer" --level senior --count 3
python scrape_jobs.py --mode scrape_only --posted 24h
```

---

## job_search_config.yml

This file is the single source of truth for all job search preferences.

```yaml
# ── Company Exclusions ────────────────────────────────────────────────────────
# Jobs from these companies are skipped (case-insensitive, partial match)
exclude_companies:
  # - Amazon
  # - Infosys
  # - TCS

# ── Candidate Profile ─────────────────────────────────────────────────────────
candidate:
  nationality: Indian

  # Options: citizen | green_card | h1b_required | opt | cpt | tn | other
  visa_status: h1b_required

  # Set true if you need the employer to sponsor your visa
  needs_sponsorship: true

  is_disabled: false
  is_veteran: false

# ── Job Search ────────────────────────────────────────────────────────────────
search:
  roles:
    - AI/ML Engineer
    - ML Engineer
    - Data Scientist

  locations:
    - Texas
    - California
    - United States

  # Options: junior | mid | senior | all
  level: junior

  # Number of validated jobs per role
  count: 5

  # Options: 24h | 7d | 30d | all
  posted_within: 7d

# ── Pipeline Mode ─────────────────────────────────────────────────────────────
pipeline:
  # scrape_only  → listings saved to CSV, no LLM calls
  # ats_report   → ATS score on your original resume, no rewrite
  # full         → complete optimization + optimized PDF
  mode: full

# ── Output ───────────────────────────────────────────────────────────────────
output:
  jobs_csv: jobs.csv
  resumes_dir: job_resumes
```

### Config fields

| Field | Options / Example | Description |
|---|---|---|
| `exclude_companies` | `[Amazon, TCS]` | Company names to skip (partial, case-insensitive) |
| `candidate.visa_status` | `h1b_required` | Used by AI validator to reject ineligible listings |
| `candidate.needs_sponsorship` | `true` | Rejects jobs that say "no sponsorship" or require US citizenship |
| `search.roles` | `[AI/ML Engineer]` | Job titles to search for |
| `search.locations` | `[Texas, United States]` | Locations to search in |
| `search.level` | `junior` / `mid` / `senior` / `all` | Seniority filter - applied at search time and validated by AI |
| `search.count` | `5` | Validated jobs to find per role |
| `search.posted_within` | `24h` / `7d` / `30d` / `all` | Only include jobs posted within this window |
| `pipeline.mode` | `scrape_only` / `ats_report` / `full` | How much processing to run per job |
| `output.jobs_csv` | `jobs.csv` | Output CSV path |
| `output.resumes_dir` | `job_resumes` | Folder for optimized PDFs |

---

### CLI Arguments (override config)

| Argument | Default (from config) | Description |
|---|---|---|
| `--roles "R1, R2"` | `search.roles` | Comma-separated job titles |
| `--locations "L1, L2"` | `search.locations` | Comma-separated locations |
| `--level junior\|mid\|senior\|all` | `search.level` | Seniority filter |
| `--count N` | `search.count` | Validated jobs per role |
| `--posted 24h\|7d\|30d\|all` | `search.posted_within` | Recency window |
| `--mode scrape_only\|ats_report\|full` | `pipeline.mode` | Pipeline mode |
| `--output path.csv` | `output.jobs_csv` | Output CSV path |

---

### Pipeline Modes

| Mode | LLM calls | What you get |
|---|---|---|
| `scrape_only` | None | Raw listings saved to CSV. Fast - good for quick scouting. |
| `ats_report` | AI validator + ATS auditor | ATS score for your original resume against each JD. No rewrite. |
| `full` | All agents | AI validate → ATS audit → XYZ bullet rewrite → optimization loop → PDF |

---

### What happens in `full` mode

```
Scrape sources → AI validate (role + seniority + eligibility) → exclude companies
→ Fetch full JD → ATS audit (original) → JD match + XYZ bullet optimization
→ Rewrite loop (up to 5x, target ATS 85+ and Eval 85+)
→ Save PDF to job_resumes/ → Log to jobs.csv
```

---

## AI Job Validator

Before running the optimization pipeline, every scraped listing is checked by an LLM against three criteria:

| Criterion | What it checks |
|---|---|
| **Role match** | Is the title semantically equivalent to the requested role? ("Machine Learning Engineer" matches "ML Engineer"; "Software Engineer II" does not) |
| **Seniority level** | Does the role match the requested level? A "Senior Staff Engineer" is rejected when `level: junior` is set. |
| **Eligibility** | When `needs_sponsorship: true` - rejects listings that require US citizenship, security clearance (TS/SCI, Secret, DoD), "no sponsorship", or federal/defense roles. |

Jobs failing any criterion are dropped before any LLM optimization runs.

---

## How the Scoring Works

ApplyPilot uses the [HackerRank hiring-agent](https://github.com/interviewstreet/hiring-agent) scoring framework for both its ATS auditor and JD match evaluator. The framework uses evidence-based category scores, bonus points, deductions, and a 0–120 raw scale normalized to 0–100. LLM temperature is set to 0.5 and top_p to 0.9.

### ATS Auditor

| Dimension | Max | What it checks |
|---|---|---|
| Keyword Coverage | 35 | % of JD keywords present in the resume |
| Format Compliance | 30 | No tables or columns, standard section names, consistent dates, contact info in body |
| Section Completeness | 25 | Summary, Experience, Education, and Skills all present |
| Content Quality | 10 | Action verbs on every bullet, no graphics, correct page length |
| Bonus | +20 | 100% keyword coverage, every bullet quantified, exact title match, certifications |
| Deductions | variable | Missing critical keywords, tables detected, weak bullet openers, mixed date formats |

**Verdict:** PASS ≥ 85 | RISK 65–84 | REJECT < 65

### JD Match Evaluator

| Dimension | Max | What it checks |
|---|---|---|
| Keyword Coverage | 35 | JD keyword density throughout the resume |
| Skills Alignment | 30 | Required JD skills present verbatim in the skills section |
| Experience Relevance | 25 | Domain match, seniority, quantified achievements |
| Summary & Format | 10 | JD themes in summary, ATS-safe formatting |
| Bonus | +20 | All skills present, every bullet has a metric, exact role match, open source contributions |
| Deductions | variable | Missing critical skills, weak bullets, format gaps |

**Pass threshold:** both ATS ≥ 85 and Eval ≥ 85. The loop runs up to 5 iterations, feeding missing keywords and format issues back to the resume writer each time.

---

## Output Files

| File | Generated by | Description |
|---|---|---|
| `optimized/<Company>_<Role>.pdf` | `main.py` | Single-page ATS-optimized resume per manual run |
| `job_resumes/<Company>_<Role>.pdf` | `scrape_jobs.py` (`full` mode) | One optimized resume per discovered job |
| `applications.csv` | `main.py` | Log of every manual optimization run |
| `jobs.csv` | `scrape_jobs.py` | Log of every discovered job (all modes) |

### CSV Columns (`jobs.csv` and `applications.csv`)

| Column | Description |
|---|---|
| `timestamp` | Run time (YYYY-MM-DD HH:MM) |
| `company_name` | Company name |
| `job_role` | Role title |
| `location` | Job location |
| `job_url` | Source URL |
| `original_ats_score` | ATS score of your original resume against this JD |
| `original_verdict` | PASS / RISK / REJECT before optimization |
| `optimized_ats_score` | ATS score after optimization (`full` mode only) |
| `optimized_verdict` | PASS / RISK / REJECT after optimization |
| `eval_score` | HackerRank evaluator score (0–100) |
| `jd_match_score` | JD match percentage |
| `eval_iterations` | Rewrite iterations used (1–5) |
| `corrections_count` | Number of bullet corrections applied |
| `resume_path` | Absolute path to the optimized PDF |
| `why_this_role` | First-person answer - copy-paste ready |
| `why_this_company` | First-person answer - copy-paste ready |
| `responsibilities` | Role responsibilities (second person) |
| `start_date` | Start date from JD |
| `end_date` | End date for contract roles, else N/A |
| `job_description` | First 1000 chars of JD |

> Columns `optimized_ats_score`, `eval_score`, `resume_path` etc. are blank in `scrape_only` and `ats_report` modes where those steps don't run.

---

## Supported Sources

### `main.py` — Job URL scraping

| Method | Sites |
|---|---|
| requests (~1s) | Any plain HTML job board |
| Playwright headless Chromium (~5–10s) | LinkedIn, Greenhouse, Lever, Workday, BlackLine, Taleo, iCIMS, Ashby, Rippling, BambooHR, SmartRecruiters, Jobvite |
| Manual `--jd` | Sites requiring login or CAPTCHA |

### `scrape_jobs.py` — Job discovery

| Source | Coverage |
|---|---|
| python-jobspy (LinkedIn) | LinkedIn job listings with full descriptions |
| python-jobspy (Indeed) | Indeed USA listings |
| python-jobspy (Google Jobs) | Aggregates from company career pages |
| Jobright.ai (Playwright) | Modern job aggregator covering Workday/Greenhouse/Lever |
| Google Jobs search (Playwright) | Direct Google Jobs results - covers Workday, Greenhouse, Lever, and company career pages |

---

## Project Structure

```
applypilot/
├── main.py                        # Single-job optimizer CLI
├── scrape_jobs.py                 # Job discovery + bulk optimizer CLI
├── job_search_config.yml          # Job search preferences (edit this)
├── .env                           # Secrets and model config (not committed)
├── .env.example                   # Template — commit this
├── requirements.txt
├── resume.pdf                     # Your resume (not committed)
├── applications.csv               # Log from main.py (not committed)
├── jobs.csv                       # Log from scrape_jobs.py (not committed)
├── optimized/                     # PDFs from main.py (not committed)
├── job_resumes/                   # PDFs from scrape_jobs.py (not committed)
└── src/
    ├── llm_client.py              # Unified OpenAI-compatible LLM client
    ├── web_scraper.py             # requests + Playwright fallback
    ├── pdf_reader.py              # pdfplumber text extraction
    ├── pdf_builder.py             # reportlab single-page PDF builder
    ├── csv_logger.py              # Appends to applications.csv
    ├── job_scraper.py             # Job discovery + bulk optimization logic
    ├── report.py                  # Terminal report printer
    ├── skills.py                  # Loads src/skills/*/SKILL.md
    ├── skills/                    # LLM system prompt library
    │   ├── ats-auditor/SKILL.md
    │   ├── job-matcher/SKILL.md
    │   ├── resume-optimizer/SKILL.md
    │   └── hiring-manager/SKILL.md
    └── agents/
        ├── ats_auditor.py         # HackerRank ATS compliance scorer
        ├── evaluator.py           # HackerRank JD match scorer
        ├── job_matcher.py         # Gap analysis
        ├── job_info.py            # Job info + answer generation
        ├── job_validator.py       # AI job listing validator (role/level/eligibility)
        ├── resume_optimizer.py    # XYZ bullet rewriter
        └── resume_writer.py       # Full resume rewrite
```

---

## `main.py` Arguments

| Argument | Description |
|---|---|
| `--url "https://..."` | Job posting URL. Always quote it in CMD/PowerShell. |
| `--jd text_or_file` | JD as inline text or path to a `.txt` file. |
| `--company "Name"` | Company name. Required when using `--jd` without `--url`. |
| `--optimize` | Run the full optimization pipeline. PDF auto-named from company + role. |
| `--check` | Score check only — prints ATS and evaluator scores. No PDF generated. |
| `--resume path.pdf` | Override resume path. Default: `RESUME_PATH` from `.env`. |

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `RESUME_PATH` | Yes | `resume.pdf` | Path to your resume PDF |
| `LLM_PROVIDER` | Yes | `openai` | `openai`, `featherless`, or `ollama` |
| `FEATHERLESS_API_KEY` | If featherless | — | API key from featherless.ai |
| `FEATHERLESS_MODEL` | No | `Qwen/Qwen2.5-72B-Instruct` | Model on Featherless |
| `OPENAI_API_KEY` | If openai | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model |
| `OLLAMA_BASE_URL` | If ollama | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | No | `llama3.1:8b` | Ollama model name |

---

## LLM Providers

Both tools use whichever provider is set in `.env`.

### Featherless (recommended)

No GPU required. Free tier available. Runs open-source models via an OpenAI-compatible API.

```env
LLM_PROVIDER=featherless
FEATHERLESS_API_KEY=your_key
FEATHERLESS_MODEL=Qwen/Qwen2.5-72B-Instruct
```

### OpenAI

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
```

### Ollama (local, fully private)

```bash
ollama pull llama3.1:8b
```

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

---

## Tips

- **Start with `scrape_only`** to quickly see what's available before committing to the full pipeline
- **Quote all URLs** in CMD/PowerShell - `&` in query strings splits the command if unquoted
- **Close Excel** before running if `jobs.csv` is open — ApplyPilot will pause and prompt you
- **JS portals** (Greenhouse, Lever, Workday) take 5–10s extra for the headless browser to render
- **Expect ~3–5 min per job** in `full` mode - each job runs ATS audit + up to 5 rewrite iterations
- **Dedup is automatic** - re-running skips any URL already in `jobs.csv`
- **Exclude companies** by adding them to `job_search_config.yml` under `exclude_companies` - matching is partial and case-insensitive
- **Override config for one run** without editing the file:
  ```bash
  python scrape_jobs.py --mode scrape_only --count 20 --posted 24h
  ```

---

## Roadmap

- [x] Auto-discover jobs by role and location (multiple job boards)
- [x] AI validator - filter off-topic listings, wrong seniority, and ineligible jobs
- [x] Visa/sponsorship filtering - rejects US citizenship required, security clearance, no sponsorship
- [x] Company exclusion list in config
- [x] Three pipeline modes - scrape_only, ats_report, full
- [x] Config file - run with no args
- [x] Bulk optimize - run the full pipeline for each discovered job
- [ ] Resume comparison dashboard - side-by-side before/after scores across all `jobs.csv` entries
- [ ] Cover letter generation
- [ ] Web UI

---

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you would like to change.

---

## License

MIT
