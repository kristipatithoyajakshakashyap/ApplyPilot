# ApplyPilot — Command Reference

---

## 1. Resume Optimizer (`main.py`)

Optimize your resume against a single job. Saves the result to `applications.csv` and `applypilot.db`.

### Optimize from a job URL (auto-scrapes the JD)
```
python main.py --url "https://linkedin.com/jobs/view/1234567" --optimize
```

### Optimize using a JD text file
```
python main.py --company "Google" --jd jd.txt --optimize
```

### Optimize using a pasted JD string
```
python main.py --company "Stripe" --jd "We are looking for an ML Engineer with 3+ years..." --optimize
```

### ATS score check only — no PDF generated
```
python main.py --check --url "https://linkedin.com/jobs/view/1234567"
python main.py --check --jd jd.txt --company "Google"
```

### Override the resume file (default is set in .env as RESUME_PATH)
```
python main.py --url "https://..." --optimize --resume resume_v2.pdf
```

**Output:**
- PDF saved to `resumes/<Role>/<Company>_<Role>.pdf`
- Row appended to `applications.csv`
- Row saved to `applypilot.db`

---

## 2. Job Scraper (`scrape_jobs.py`)

Bulk scrape, validate, and optionally optimize jobs for multiple roles. Reads from `job_search_config.yml` by default.

### Run with config file (no args needed)
```
python scrape_jobs.py
```

### Override roles and locations from CLI
```
python scrape_jobs.py --roles "ML Engineer, Data Scientist" --locations "Austin, United States"
```

### Override count and seniority level
```
python scrape_jobs.py --roles "ML Engineer" --count 5 --level senior
```

### Change posting recency window
```
python scrape_jobs.py --posted 24h
python scrape_jobs.py --posted 7d
python scrape_jobs.py --posted 30d
python scrape_jobs.py --posted all
```

### Change pipeline mode
```
# Scrape only — no LLM calls, just collect listings
python scrape_jobs.py --mode scrape_only

# ATS report — validate jobs + score your original resume, no rewrite
python scrape_jobs.py --mode ats_report

# Full pipeline — validate + optimize resume for each job (default)
python scrape_jobs.py --mode full
```

**Output:**
- One CSV per role: `ml_engineer.csv`, `data_scientist.csv`, etc.
- Resumes saved to `resumes/<Role>/<Company>_<Role>.pdf`
- All rows saved to `applypilot.db`

---

## 3. Database Viewer (`show_db.py`)

View and manage the `applypilot.db` SQLite database from the terminal.

### Show all jobs — all columns, vertical record view (default)
```
python show_db.py
```

### Filter by status
```
python show_db.py --status done       # fully optimized jobs
python show_db.py --status scraped    # scraped but not yet optimized
python show_db.py --status skipped    # duplicate JD — skipped automatically
```

### Show full detail for a single job by ID
```
python show_db.py --id 5
```

### Compact horizontal summary table
```
python show_db.py --table
python show_db.py --table --status done
```

### Import existing CSV data into the DB
```
python show_db.py --import-csv jobs.csv
python show_db.py --import-csv applications.csv
```

---

## 4. Config File (`job_search_config.yml`)

Controls all default settings for `scrape_jobs.py`. Edit once, run without args.

```yaml
candidate:
  visa_status: h1b_required       # citizen | green_card | h1b_required | opt | cpt | tn
  needs_sponsorship: true

exclude_companies:
  - Amazon
  - Infosys

search:
  roles:
    - ML Engineer
    - Data Scientist
  locations:
    - United States
  level: junior                   # junior | mid | senior | all
  count: 10                       # validated jobs to find per role
  posted_within: 7d               # 24h | 7d | 30d | all

pipeline:
  mode: full                      # scrape_only | ats_report | full
```

---

## 5. Output Layout

```
job-hunt/
├── resumes/
│   ├── ML_Engineer/
│   │   ├── Google_ML_Engineer.pdf
│   │   └── OpenAI_ML_Engineer.pdf
│   └── Data_Scientist/
│       └── Meta_Data_Scientist.pdf
├── ml_engineer.csv               # one CSV per scraped role
├── data_scientist.csv
├── applications.csv              # manual main.py runs
├── applypilot.db                 # all jobs, all runs, never cleared
└── job_search_config.yml
```

---

## 6. Common Workflows

### First-time setup — import existing CSVs into DB
```
python show_db.py --import-csv jobs.csv
python show_db.py --import-csv applications.csv
```

### Daily job search run
```
python scrape_jobs.py
```

### Check what was found today
```
python show_db.py --status done --table
```

### Manually optimize a job you found yourself
```
python main.py --url "https://greenhouse.io/jobs/abc123" --optimize
```

### Clear a role CSV and re-run (DB prevents re-processing)
```
del ml_engineer.csv
python scrape_jobs.py --roles "ML Engineer"
```
