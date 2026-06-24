# ApplyPilot

> AI-powered resume optimizer that tailors your resume to any job, scores it using the HackerRank hiring-agent framework, and generates a single-page ATS-ready PDF — all from one command.

---

## What It Does

You give ApplyPilot a job URL or a job description. It:

1. Scrapes the job posting (including JavaScript-rendered career portals)
2. Audits your current resume against the job using the HackerRank ATS scoring framework
3. Rewrites every bullet using Google's XYZ formula (result → metric → method)
4. Rewrites the full resume, skills section, summary, and experience to match the job
5. Runs up to 5 evaluation iterations until both the ATS score and JD match score reach 85+
6. Generates a single-page ATS-safe PDF saved as `optimized/<Company>_<Role>.pdf`
7. Writes first-person "why this role" and "why this company" answers you can copy directly into applications
8. Logs every run to `applications.csv`


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

Required for JavaScript-rendered job portals (Greenhouse, Lever, Workday, BlackLine, LinkedIn).

```bash
python -m playwright install chromium
```

### 4. Create your `.env` file

```bash
cp .env.example .env
```

Then fill in your values:

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

Place your resume PDF in the project root and set `RESUME_PATH` in `.env`.

```
applypilot/
└── resume.pdf   ← your resume goes here
```

---

## Usage

ApplyPilot has two modes: **optimize** (full pipeline, generates a PDF) and **check** (score your resume against a job, no PDF).

### --optimize - Full Pipeline

Rewrites and optimizes your resume for the job. PDF is auto-named `optimized/<Company>_<Role>.pdf`.

```bash
# Optimize from a job URL (scrapes company, role, and JD automatically)
# Output: optimized/BlackLine_Senior_AI_Engineer.pdf
python main.py --url "https://careers.blackline.com/jobs/7512?lang=en-us" --optimize

# Optimize from a Greenhouse posting
# Output: optimized/Stripe_ML_Engineer.pdf
python main.py --url "https://boards.greenhouse.io/stripe/jobs/12345" --optimize

# Optimize from a Lever posting
# Output: optimized/Figma_Senior_Software_Engineer.pdf
python main.py --url "https://jobs.lever.co/figma/role-id" --optimize

# Optimize using a JD saved in a text file (when the site blocks scraping)
# Output: optimized/Google_Software_Engineer.pdf
python main.py --company "Google" --jd jd.txt --optimize

# Optimize with a JD pasted inline
# Output: optimized/Meta_Data_Scientist.pdf
python main.py --company "Meta" --jd "We are looking for a Data Scientist with 5+ years..." --optimize

# Optimize with manual JD but still log the source URL to applications.csv
# Output: optimized/BlackLine_Senior_AI_Engineer.pdf
python main.py --company "BlackLine" --jd jd.txt --url "https://careers.blackline.com/jobs/7512" --optimize

# Use a different resume than the .env default for one run
# Output: optimized/Google_Software_Engineer.pdf
python main.py --url "https://jobs.google.com/jobs/12345" --optimize --resume resume_v2.pdf
```

> **Windows CMD/PowerShell:** Always quote URLs. The `&` character in query strings splits the command if unquoted.

---

### --check - ATS Score Check (no PDF)

Scores your resume against a job in seconds. Useful for comparing your resume across multiple roles before committing to a full optimization run.

```bash
# Score against a job URL
# Output: ATS + evaluator score report printed to terminal
python main.py --check --url "https://jobs.lever.co/company/role-id"

# Score against a JD file
# Output: ATS + evaluator score report printed to terminal
python main.py --check --jd jd.txt --company "Google"

# Score a different resume without changing .env
# Output: ATS + evaluator score report printed to terminal
python main.py --check --url "https://..." --resume resume_v2.pdf
```

---

## How the Scoring Works

ApplyPilot uses the [HackerRank hiring-agent](https://github.com/interviewstreet/hiring-agent) scoring framework for both its ATS auditor and JD match evaluator. The framework uses evidence-based category scores, bonus points, deductions, and a 0–120 raw scale normalized to 0–100. LLM temperature is set to 0.5 and top_p to 0.9 — the exact same parameters as the official hiring-agent.

### ATS Auditor

Simulates how enterprise ATS systems (Workday, Greenhouse, Lever, Taleo, iCIMS) parse and rank resumes.

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

Checks how well the optimized resume matches the specific job description.

| Dimension | Max | What it checks |
|---|---|---|
| Keyword Coverage | 35 | JD keyword density throughout the resume |
| Skills Alignment | 30 | Required JD skills present verbatim in the skills section |
| Experience Relevance | 25 | Domain match, seniority, quantified achievements |
| Summary & Format | 10 | JD themes in summary, ATS-safe formatting |
| Bonus | +20 | All skills present, every bullet has a metric, exact role match, open source contributions |
| Deductions | variable | Missing critical skills, weak bullets, format gaps |

**Pass threshold:** raw score ≥ 85 out of 120

The optimization loop runs up to 5 iterations. After each rewrite it scores both agents, collects missing keywords and format issues, and feeds them back to the resume writer for the next iteration. It stops as soon as both scores pass 85.

---

## Output Files

### `optimized/<Company>_<Role>.pdf`

Single-page ATS-optimized resume, auto-named from the job's company and role title. Saved to the `optimized/` folder after each run.

### `applications.csv`

Every run is appended here. Open it in Excel or Google Sheets to track your applications.

| Column | Description |
|---|---|
| `timestamp` | Run time (YYYY-MM-DD HH:MM) |
| `company_name` | Company name |
| `job_role` | Role title |
| `location` | Job location |
| `job_url` | Source URL |
| `original_ats_score` | ATS score before optimization |
| `original_verdict` | PASS / RISK / REJECT before |
| `optimized_ats_score` | ATS score after optimization |
| `optimized_verdict` | PASS / RISK / REJECT after |
| `eval_score` | HackerRank evaluator score (0–100) |
| `jd_match_score` | JD match percentage |
| `eval_iterations` | Number of rewrite iterations used |
| `resume_path` | Absolute path to the output PDF |
| `why_this_role` | First-person answer — copy-paste ready |
| `why_this_company` | First-person answer — copy-paste ready |
| `responsibilities` | Paragraph summary of role responsibilities |
| `start_date` | Start date from the JD |
| `end_date` | End date (for contract roles), else N/A |

---

## Supported Job Sites

| Method | Sites |
|---|---|
| requests (~1s) | Any plain HTML job board |
| Playwright headless Chromium (~5–10s) | LinkedIn, Greenhouse, Lever, Workday, BlackLine, Taleo, iCIMS, Ashby, Rippling, BambooHR, SmartRecruiters, Jobvite |
| Manual `--jd` | Sites requiring login or CAPTCHA |

---

## Project Structure

```
applypilot/
├── main.py                        # CLI — all three modes
├── .env                           # Your config (not committed)
├── .env.example                   # Template — commit this
├── requirements.txt
├── resume.pdf                     # Your resume (not committed)
├── applications.csv               # Application log (not committed)
├── optimized/                     # Output PDFs (not committed)
└── src/
    ├── llm_client.py              # Unified OpenAI-compatible client
    ├── web_scraper.py             # requests + Playwright fallback
    ├── pdf_reader.py              # pdfplumber text extraction
    ├── pdf_builder.py             # reportlab single-page builder
    ├── csv_logger.py              # Append to applications.csv
    ├── report.py                  # Terminal report
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
        ├── resume_optimizer.py    # XYZ bullet rewriter
        └── resume_writer.py       # Full resume rewrite
```

---

## Arguments Reference

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
| `FEATHERLESS_MODEL` | No | `Qwen/Qwen2.5-72B-Instruct` | Model name on Featherless |
| `OPENAI_API_KEY` | If openai | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model |
| `OLLAMA_BASE_URL` | If ollama | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | No | `llama3.1:8b` | Ollama model name |

---

## LLM Providers

### Featherless (recommended)

No GPU required. Free tier available. Runs open-source models via an OpenAI-compatible API.

```env
LLM_PROVIDER=featherless
FEATHERLESS_API_KEY=your_key
FEATHERLESS_MODEL=Qwen/Qwen2.5-72B-Instruct
```

Other non-gated models: `mistralai/Mistral-7B-Instruct-v0.2`, `NousResearch/Hermes-3-Llama-3.1-70B`

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

- **Quote all URLs** — `&` in query strings splits the command in CMD/PowerShell if unquoted
- **Close Excel** before running if `applications.csv` is open — Windows locks the file; ApplyPilot will pause and prompt you
- **JS portals** (Greenhouse, Lever, Workday, BlackLine) take 5–10s extra for the headless browser to render
- **Override resume for one run** without touching `.env`:
  ```bash
  python main.py --check --url "https://..." --resume resume_v2.pdf
  ```
- **Log the URL without scraping**: pass both `--jd` and `--url` — the JD comes from the file, the URL is only stored in `applications.csv`

---

## Roadmap

- [ ] Auto-discover jobs by role and location (scrape multiple job boards)
- [ ] Batch optimize - run against a list of URLs in one command
- [ ] Cover letter generation
- [ ] Web UI / dashboard

---

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you would like to change.

---

## License

MIT
