# ApplyPilot — Complete Documentation

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Web Dashboard](#2-web-dashboard)
3. [CLI — Resume Optimizer](#3-cli--resume-optimizer-mainpy)
4. [CLI — Job Scraper](#4-cli--job-scraper-scrape_jobspy)
5. [Database Viewer](#5-database-viewer-show_dbpy)
6. [job_search_config.yml Reference](#6-job_search_configyml-reference)
7. [Environment Variables](#7-environment-variables)
8. [LLM Providers](#8-llm-providers)
9. [How Scoring Works](#9-how-scoring-works)
10. [AI Job Validator](#10-ai-job-validator)
11. [Pipeline Modes](#11-pipeline-modes)
12. [Supported Job Sources](#12-supported-job-sources)
13. [Output Files & Folder Layout](#13-output-files--folder-layout)
14. [Database Schema](#14-database-schema)
15. [Project Structure](#15-project-structure)
16. [Common Workflows](#16-common-workflows)
17. [Tips & Troubleshooting](#17-tips--troubleshooting)

---

## 1. Architecture Overview

```
job_search_config.yml
        │
        ▼
scrape_jobs.py ──► src/job_scraper.py
                        │
                        ├── Scrape (jobspy + Playwright)
                        ├── AI Validate (role / level / eligibility)
                        ├── Optimize resume (XYZ loop)
                        └── mark_processed() ──► applypilot.db
                                                        │
app.py (Flask) ◄────────────────────────────────────────┘
        │
        └── dashboard.html (SPA)
                ├── Jobs page  (only optimized jobs)
                ├── Config & Scrape page
                ├── Logs page  (live SSE stream)
                └── Optimize Resume page

main.py ──► manual single-job optimization ──► applypilot.db
```

**Key design decision:** the database only stores jobs that completed the full optimization pipeline. Raw scraped listings stay in memory and are discarded if they fail validation or `scrape_only` mode is active.

---

## 2. Web Dashboard

Start with:

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

### Pages

| Page | What it does |
|---|---|
| **Jobs** | Shows optimized jobs as cards. Tabs come from `job_search_config.yml` roles. Cards show score pill, New badge (until opened), and Applied badge. Click to open the full detail modal. |
| **Config & Scrape** | Edit every field in `job_search_config.yml` via dropdowns. Save then click Scrape Now to run `scrape_jobs.py`. Stop button cancels a running process. |
| **Logs** | Live terminal output streamed via SSE from the running process. Auto-switches here when a process starts. |
| **Optimize Resume** | Enter a job URL or paste company/role/JD manually. Runs `main.py` and streams output to Logs. |

### Dashboard Features

| Feature | Detail |
|---|---|
| Dark / Light mode | Toggle in sidebar footer; saved in localStorage |
| New badge | Shown on unread cards; disappears when modal is opened; tracked per-ID in localStorage |
| Applied toggle | Toggle in modal; writes `applied` + `applied_at` to DB |
| Visit Job button | Opens `job_url` in a new tab |
| Config dropdowns | All structured fields use dropdowns (visa status, level, count, posted within, pipeline mode, nationality, sponsorship, disabled, veteran) |
| Optimize Role dropdown | Populated from `config.search.roles` |
| Reset All Data | Clears DB, removes `resumes/` folder, deletes per-role CSVs |
| Job categorisation | Jobs are matched to config roles by keyword overlap — not by the portal's raw job title |

### API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Serve dashboard.html |
| GET | `/api/jobs` | All jobs from DB, newest first |
| POST | `/api/jobs/<id>/applied` | Toggle applied status |
| GET | `/api/config` | Read `job_search_config.yml` as JSON |
| POST | `/api/config` | Write `job_search_config.yml` from JSON |
| POST | `/api/scrape` | Start `scrape_jobs.py` subprocess |
| POST | `/api/scrape/stop` | Terminate the running process |
| POST | `/api/optimize` | Start `main.py` subprocess |
| GET | `/api/logs/stream` | SSE stream of process stdout |
| GET | `/api/status` | `{"running": true/false}` |
| POST | `/api/reset` | Clear DB + delete output folders |

---

## 3. CLI — Resume Optimizer (`main.py`)

Optimizes your resume against a single job posting and saves an ATS-ready PDF.

### Full optimization from a URL

```bash
python main.py --url "https://careers.company.com/jobs/12345" --optimize
```

### Full optimization from a JD file

```bash
python main.py --company "Google" --jd jd.txt --optimize
```

### Full optimization from inline JD text

```bash
python main.py --company "Stripe" --jd "We are looking for an ML Engineer..." --optimize
```

### ATS score check only (no PDF)

```bash
python main.py --check --url "https://jobs.lever.co/company/role-id"
python main.py --check --jd jd.txt --company "Google"
```

### Override the resume file

```bash
python main.py --url "https://..." --optimize --resume resume_v2.pdf
```

### Arguments

| Argument | Description |
|---|---|
| `--url "https://..."` | Job posting URL. Always quote in CMD/PowerShell. |
| `--jd text_or_file` | JD as inline text or path to a `.txt` file. |
| `--company "Name"` | Company name. Used when `--jd` is provided without `--url`. |
| `--role "Title"` | Job role/title. Optional with `--jd`. |
| `--optimize` | Run the full pipeline. PDF saved to `resumes/<Role>/`. |
| `--check` | Score only — prints ATS and evaluator scores. No PDF. |
| `--resume path.pdf` | Override resume path (default: `RESUME_PATH` from `.env`). |

### What `--optimize` does

```
[1/8] Scrape or load JD
[2/8] Extract resume text
[3/8] ATS audit — original resume
[4/8] JD match analysis
[5/8] XYZ bullet optimization
[6/8] Extract job info + generate answers
[7/8] Rewrite loop (up to 5x, target ATS >= 85 and Eval >= 85)
[8/8] Build PDF + save to DB
```

### Output

- PDF saved to `resumes/<Role>/<Company>_<Role>.pdf`
- Row written to `applypilot.db`

---

## 4. CLI — Job Scraper (`scrape_jobs.py`)

Bulk scrapes, validates, and optimizes jobs for all roles in your config.

### Run with config (recommended)

```bash
python scrape_jobs.py
```

### Override specific settings

```bash
python scrape_jobs.py --roles "ML Engineer, Data Scientist"
python scrape_jobs.py --locations "Austin, United States"
python scrape_jobs.py --count 5 --level senior
python scrape_jobs.py --posted 24h
python scrape_jobs.py --mode full
python scrape_jobs.py --mode scrape_only
```

### CLI Arguments

| Argument | Default (from config) | Description |
|---|---|---|
| `--roles "R1, R2"` | `search.roles` | Comma-separated job titles |
| `--locations "L1, L2"` | `search.locations` | Comma-separated locations |
| `--level` | `search.level` | `junior`, `mid`, `senior`, or `all` |
| `--count N` | `search.count` | Validated jobs to find per role |
| `--posted` | `search.posted_within` | `24h`, `48h`, `72h`, `168h`, `336h`, `720h` |
| `--mode` | `pipeline.mode` | `scrape_only` or `full` |

### Per-role flow

```
Scrape (jobspy + Playwright sources)
  └── Deduplicate by URL (DB + per-role CSV)
  └── Exclude blocked companies
  └── AI Validate (role match + seniority + eligibility)
        └── PASS → run pipeline mode
              scrape_only → skip (nothing saved)
              full        → optimize resume → save PDF → write to DB
        └── FAIL → skip (nothing saved)
```

---

## 5. Database Viewer (`show_db.py`)

View and manage `applypilot.db` from the terminal.

```bash
# All jobs — vertical record view
python show_db.py

# Filter by status
python show_db.py --status done
python show_db.py --status skipped

# Single job by ID
python show_db.py --id 5

# Compact horizontal table
python show_db.py --table
python show_db.py --table --status done

# Import existing CSV into DB
python show_db.py --import-csv applications.csv
```

---

## 6. `job_search_config.yml` Reference

```yaml
candidate:
  nationality: Indian
  visa_status: h1b_required
  needs_sponsorship: true
  is_disabled: false
  is_veteran: false

exclude_companies:
  - Amazon

search:
  roles:
    - ML Engineer
    - Data Scientist
  locations:
    - United States
  level: junior
  count: 10
  posted_within: 24h

pipeline:
  mode: full
```

### Field Reference

| Field | Options | Description |
|---|---|---|
| `candidate.nationality` | `Indian`, `American`, `Canadian`, … | Context for the AI validator |
| `candidate.visa_status` | `h1b_required`, `h1b_transfer`, `opt`, `opt_stem`, `cpt`, `tn_visa`, `l1`, `o1`, `green_card`, `citizen`, `no_sponsorship_needed` | Rejects ineligible listings |
| `candidate.needs_sponsorship` | `true` / `false` | Rejects "no sponsorship", clearance, and citizenship-required roles |
| `candidate.is_disabled` | `true` / `false` | EEO disclosure |
| `candidate.is_veteran` | `true` / `false` | EEO disclosure |
| `exclude_companies` | list of strings | Partial, case-insensitive match |
| `search.roles` | list of strings | Job titles; also used as tab labels in the dashboard |
| `search.locations` | list of strings | Passed to each job source |
| `search.level` | `junior`, `mid`, `senior`, `all` | Applied at search and re-validated by AI |
| `search.count` | integer | Target optimized jobs per role |
| `search.posted_within` | `12h`, `24h`, `48h`, `72h`, `168h`, `336h`, `720h` | Listing recency filter |
| `pipeline.mode` | `scrape_only`, `full` | `scrape_only` collects listings only; `full` runs complete optimization |

---

## 7. Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `RESUME_PATH` | Yes | `resume.pdf` | Path to your resume PDF |
| `LLM_PROVIDER` | Yes | `openai` | `openai`, `featherless`, or `ollama` |
| `FEATHERLESS_API_KEY` | If featherless | — | API key from featherless.ai |
| `FEATHERLESS_MODEL` | No | `Qwen/Qwen2.5-72B-Instruct` | Model on Featherless |
| `OPENAI_API_KEY` | If openai | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model name |
| `OLLAMA_BASE_URL` | If ollama | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | No | `llama3.1:8b` | Ollama model name |

---

## 8. LLM Providers

### Featherless (recommended)

No GPU required. Free tier available.

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

## 9. How Scoring Works

Raw scores are 0–120, normalized to 0–100. LLM temperature 0.5, top_p 0.9.

### ATS Auditor

| Dimension | Max | What it checks |
|---|---|---|
| Keyword Coverage | 35 | % of JD keywords present in the resume |
| Format Compliance | 30 | No tables/columns, standard section names, consistent dates, contact info in body |
| Section Completeness | 25 | Summary, Experience, Education, and Skills all present |
| Content Quality | 10 | Action verbs on every bullet, no graphics, correct page length |
| Bonus | +20 | 100% keyword coverage, every bullet quantified, exact title match, certifications |
| Deductions | variable | Missing critical keywords, tables, weak openers, mixed date formats |

**Verdict:** PASS >= 85 | RISK 65–84 | REJECT < 65

### JD Match Evaluator

| Dimension | Max | What it checks |
|---|---|---|
| Keyword Coverage | 35 | JD keyword density throughout the resume |
| Skills Alignment | 30 | Required skills present verbatim in the skills section |
| Experience Relevance | 25 | Domain match, seniority, quantified achievements |
| Summary & Format | 10 | JD themes in summary, ATS-safe formatting |
| Bonus | +20 | All skills present, every bullet has a metric, exact role match |
| Deductions | variable | Missing critical skills, weak bullets, format gaps |

**Pass threshold:** both ATS >= 85 and Eval >= 85. Rewrite loop runs up to 5 iterations.

---

## 10. AI Job Validator

Checks every scraped listing before optimization:

| Criterion | What it checks |
|---|---|
| **Role match** | Is the title semantically equivalent to the requested role? |
| **Seniority level** | Does the role match the configured level? |
| **Eligibility** | When `needs_sponsorship: true` — rejects US citizenship required, clearance, "no sponsorship", federal/DoD roles |

Jobs failing any criterion are dropped and never saved.

---

## 11. Pipeline Modes

| Mode | LLM calls | What you get |
|---|---|---|
| `scrape_only` | AI validator only | Listings validated and printed. Nothing saved to DB. |
| `full` | All agents | AI validate → ATS audit → XYZ bullets → rewrite loop → PDF → DB |

---

## 12. Supported Job Sources

### `main.py` — single URL

| Method | Sites |
|---|---|
| requests | Any plain HTML job board |
| Playwright | LinkedIn, Greenhouse, Lever, Workday, BlackLine, Taleo, iCIMS, Ashby, Rippling, BambooHR, SmartRecruiters, Jobvite |
| `--jd` manual | Sites requiring login or CAPTCHA |

### `scrape_jobs.py` — bulk

| Source | Coverage |
|---|---|
| python-jobspy (LinkedIn) | LinkedIn listings with full descriptions |
| python-jobspy (Indeed) | Indeed USA listings |
| python-jobspy (Google Jobs) | Aggregates from company career pages |
| Jobright.ai (Playwright) | Workday / Greenhouse / Lever aggregator |
| Google Jobs (Playwright) | Direct Google Jobs results |

---

## 13. Output Files & Folder Layout

```
job-hunt/
├── resumes/
│   ├── ML_Engineer/
│   │   ├── Google_ML_Engineer.pdf
│   │   └── OpenAI_ML_Engineer.pdf
│   └── Data_Scientist/
│       └── Meta_Data_Scientist.pdf
├── ml_engineer.csv               # per-role scrape log (dedup safety net)
├── data_scientist.csv
├── applypilot.db                 # all optimized jobs
├── job_search_config.yml
├── resume.pdf                    # not committed
└── .env                          # not committed
```

| Tool | CSV | DB | PDF |
|---|---|---|---|
| `main.py --optimize` | — | Yes | `resumes/<Role>/` |
| `scrape_jobs.py --mode full` | `<role>.csv` | Yes | `resumes/<Role>/` |
| `scrape_jobs.py --mode scrape_only` | — | No | No |

---

## 14. Database Schema

Table: `jobs` in `applypilot.db`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `job_url` | TEXT UNIQUE | Source URL (primary dedup key) |
| `company_name` | TEXT | Company |
| `job_role` | TEXT | Role title |
| `job_location` | TEXT | Location |
| `jd_hash` | TEXT | MD5 of first 600 chars of JD (secondary dedup) |
| `job_description` | TEXT | First 2000 chars of JD |
| `scraped_at` | TEXT | When listing was found |
| `status` | TEXT | `done` or `skipped` |
| `original_ats_score` | INTEGER | ATS score before optimization |
| `optimized_ats_score` | INTEGER | ATS score after optimization |
| `eval_score` | INTEGER | HackerRank evaluator score |
| `suggested_resume` | TEXT | Resume variant recommended |
| `resume_path` | TEXT | Path to saved PDF |
| `processed_at` | TEXT | When optimization completed |
| `timestamp` | TEXT | Run timestamp |
| `location` | TEXT | Resolved location |
| `original_verdict` | TEXT | PASS / RISK / REJECT before |
| `optimized_verdict` | TEXT | PASS / RISK / REJECT after |
| `jd_match_score` | INTEGER | JD match percentage |
| `eval_iterations` | INTEGER | Rewrite iterations used (1–5) |
| `corrections_count` | INTEGER | Bullet corrections applied |
| `why_this_role` | TEXT | First-person answer |
| `why_this_company` | TEXT | First-person answer |
| `responsibilities` | TEXT | Role responsibilities |
| `start_date` | TEXT | Start date from JD |
| `end_date` | TEXT | End date (contract roles) |
| `applied` | INTEGER | 0 or 1 |
| `applied_at` | TEXT | Timestamp when marked applied |

**Dedup layers:**
1. URL unique index — same URL never processed twice
2. `company + role + jd_hash` index — same JD at a different URL is skipped
3. Per-role CSV URLs — survives a DB clear; prevents re-scraping within a run

---

## 15. Project Structure

```
applypilot/
├── app.py                         # Flask dashboard backend
├── main.py                        # Single-job optimizer CLI
├── scrape_jobs.py                 # Bulk job discovery + optimizer CLI
├── show_db.py                     # Terminal DB viewer
├── dashboard.html                 # SPA frontend (4 pages)
├── job_search_config.yml
├── .env / .env.example
├── requirements.txt
├── README.md                      # Overview + setup
├── DOCUMENTATION.md               # This file
└── src/
    ├── db.py                      # SQLite layer
    ├── llm_client.py              # Unified LLM client
    ├── web_scraper.py             # requests + Playwright
    ├── pdf_reader.py              # pdfplumber extraction
    ├── pdf_builder.py             # reportlab PDF builder
    ├── csv_logger.py              # Per-role CSV writer
    ├── job_scraper.py             # Bulk scrape + validate + optimize
    ├── report.py                  # Terminal report printer
    ├── skills.py                  # Loads SKILL.md prompts
    ├── skills/
    │   ├── ats-auditor/SKILL.md
    │   ├── job-matcher/SKILL.md
    │   ├── resume-optimizer/SKILL.md
    │   └── hiring-manager/SKILL.md
    └── agents/
        ├── ats_auditor.py
        ├── evaluator.py
        ├── job_matcher.py
        ├── job_info.py
        ├── job_validator.py
        ├── resume_optimizer.py
        └── resume_writer.py
```

---

## 16. Common Workflows

### Daily job search (dashboard)

```
python app.py
→ Config & Scrape → Scrape Now
→ Logs (watch progress)
→ Jobs (review optimized results)
```

### Daily job search (CLI)

```bash
python scrape_jobs.py
python show_db.py --table --status done
```

### Manually optimize one job

```bash
# CLI
python main.py --url "https://greenhouse.io/jobs/abc123" --optimize

# Dashboard: Optimize Resume page → enter URL → Optimize Resume
```

### Import existing CSV data into DB

```bash
python show_db.py --import-csv applications.csv
```

### Re-run a role after clearing its CSV

```bash
del ml_engineer.csv          # Windows
python scrape_jobs.py --roles "ML Engineer"
```

### Full reset (fresh start)

```
Dashboard → sidebar footer → Reset All Data
```

---

## 17. Tips & Troubleshooting

| Situation | Fix |
|---|---|
| URLs break in CMD/PowerShell | Always quote URLs — `&` splits the command if unquoted |
| Excel has jobs CSV open | Close Excel before running; the CSV writer will otherwise pause and prompt |
| JS job portals slow | Greenhouse, Lever, Workday use headless Chromium — expect 5–10s extra per job |
| ~3–5 min per job in `full` mode | Normal — ATS audit + up to 5 LLM rewrite iterations per job |
| Jobs page is empty | Only fully optimized jobs appear — run with `mode: full` or use Optimize Resume page |
| DB locked error | Stop the running process first, then retry |
| Playwright not installed | Run `python -m playwright install chromium` once in the active venv |
| PyYAML missing | Run `pip install pyyaml` in the active venv |
| Want to scout quickly first | Run with `--mode scrape_only` — no LLM calls, just prints validated listings |
| Same job reappears after DB clear | Per-role CSVs still track seen URLs — delete the CSV to allow re-scraping |
