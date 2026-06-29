# ApplyPilot

> AI-powered job search automation: scrapes jobs, filters by your eligibility, optimizes your resume for each one using the HackerRank scoring framework, and saves an ATS-ready PDF — all from a web dashboard or CLI.

---

## What It Does

- **Discovers jobs** across LinkedIn, Indeed, Google Jobs, Jobright.ai, Workday, Greenhouse, and Lever
- **Filters listings** by seniority, visa/sponsorship eligibility, and excluded companies
- **Optimizes your resume** for each job using Google's XYZ bullet formula and a HackerRank ATS scoring loop
- **Saves only fully optimized jobs** to the database — no noise from raw scrape results
- **Web dashboard** to manage config, trigger scrapes, view results, and run optimizations

---

## Project Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/applypilot.git
cd applypilot
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browser (one-time)

Required for JavaScript-rendered job portals.

```bash
python -m playwright install chromium
```

### 5. Create your `.env` file

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
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4o

# Ollama (local, fully private)
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3.1:8b
```

### 6. Add your resume

Place your resume PDF in the project root:

```
applypilot/
└── resume.pdf
```

### 7. Configure your job search

Edit `job_search_config.yml`:

```yaml
candidate:
  nationality: Indian
  visa_status: h1b_required
  needs_sponsorship: true

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

### 8. Start the dashboard

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

For full usage, CLI reference, scoring details, and project structure see [DOCUMENTATION.md](DOCUMENTATION.md).
