"""
SQLite persistence layer for ApplyPilot.

Stores every scraped and processed job so that:
- Jobs are never re-processed even if jobs.csv is cleared.
- Dedup uses URL first, then company + role + JD fingerprint
  (same company can post the same role with a different JD — those count as separate jobs).
- main.py manual runs are also recorded, preventing re-scrape of manually optimized jobs.
"""
import csv
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("applypilot.db")

# Extra columns that mirror jobs.csv / applications.csv beyond the base schema
_EXTRA_COLS = [
    ("timestamp",          "TEXT"),
    ("location",           "TEXT"),
    ("original_verdict",   "TEXT"),
    ("optimized_verdict",  "TEXT"),
    ("jd_match_score",     "INTEGER"),
    ("eval_iterations",    "INTEGER"),
    ("corrections_count",  "INTEGER"),
    ("why_this_role",      "TEXT"),
    ("why_this_company",   "TEXT"),
    ("responsibilities",   "TEXT"),
    ("start_date",         "TEXT"),
    ("end_date",           "TEXT"),
    ("applied",            "INTEGER DEFAULT 0"),
    ("applied_at",         "TEXT"),
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                job_url              TEXT,
                company_name         TEXT,
                job_role             TEXT,
                job_location         TEXT,
                jd_hash              TEXT,
                job_description      TEXT,
                scraped_at           TEXT,
                status               TEXT DEFAULT 'scraped',
                original_ats_score   INTEGER,
                optimized_ats_score  INTEGER,
                eval_score           INTEGER,
                suggested_resume     TEXT,
                resume_path          TEXT,
                processed_at         TEXT
            )
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_url
            ON jobs(job_url)
            WHERE job_url IS NOT NULL AND job_url != ''
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_co_role_hash
            ON jobs(company_name, job_role, jd_hash)
        """)
        # Migrate: add extra columns if this DB was created before they existed
        existing = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        for col_name, col_type in _EXTRA_COLS:
            if col_name not in existing:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")
        conn.commit()


def jd_fingerprint(jd_text: str) -> str:
    """MD5 of first 600 normalised chars — stable across whitespace changes."""
    normalised = " ".join(jd_text.lower().split())[:600]
    return hashlib.md5(normalised.encode()).hexdigest()[:16]


def load_seen_urls() -> set:
    """All job URLs already in the DB (any status)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT job_url FROM jobs WHERE job_url IS NOT NULL AND job_url != ''"
        ).fetchall()
    return {r["job_url"] for r in rows}


def is_duplicate_jd(company: str, role: str, jd_text: str) -> bool:
    """
    True if we have already seen this exact JD for this company+role.
    Allows the same company to post the same title with a different JD.
    """
    h = jd_fingerprint(jd_text)
    with _connect() as conn:
        row = conn.execute(
            """SELECT 1 FROM jobs
               WHERE company_name = ? AND job_role = ? AND jd_hash = ?
               LIMIT 1""",
            (company.lower().strip(), role.lower().strip(), h),
        ).fetchone()
    return row is not None


def upsert_scraped(job: dict) -> None:
    """Insert a freshly scraped job. Silently skips if URL already present."""
    url = (job.get("job_url") or "").strip()
    if not url:
        return
    with _connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO jobs
               (job_url, company_name, job_role, job_location, job_description, scraped_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                url,
                job.get("company_name", ""),
                job.get("job_role", ""),
                job.get("job_location", ""),
                (job.get("job_description") or "")[:2000],
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            ),
        )
        conn.commit()


def mark_processed(url: str, company: str, role: str, jd_text: str, result: dict) -> None:
    """
    Upsert a fully processed job record with all CSV columns.
    Works for both scrape_jobs.py pipeline and main.py manual runs.
    """
    h = jd_fingerprint(jd_text) if jd_text else ""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with _connect() as conn:
        # Ensure the row exists (main.py skips upsert_scraped)
        conn.execute(
            """INSERT OR IGNORE INTO jobs
               (job_url, company_name, job_role, job_location, job_description, scraped_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                url, company, role,
                result.get("location", ""),
                (jd_text or "")[:2000],
                result.get("timestamp", now),
            ),
        )
        conn.execute(
            """UPDATE jobs SET
                company_name        = ?,
                job_role            = ?,
                job_location        = ?,
                jd_hash             = ?,
                job_description     = ?,
                status              = 'done',
                original_ats_score  = ?,
                optimized_ats_score = ?,
                eval_score          = ?,
                suggested_resume    = ?,
                resume_path         = ?,
                processed_at        = ?,
                timestamp           = ?,
                location            = ?,
                original_verdict    = ?,
                optimized_verdict   = ?,
                jd_match_score      = ?,
                eval_iterations     = ?,
                corrections_count   = ?,
                why_this_role       = ?,
                why_this_company    = ?,
                responsibilities    = ?,
                start_date          = ?,
                end_date            = ?
               WHERE job_url = ?""",
            (
                company,
                role,
                result.get("location", ""),
                h,
                (jd_text or "")[:2000],
                result.get("original_ats_score"),
                result.get("optimized_ats_score"),
                result.get("eval_score"),
                result.get("suggested_resume", ""),
                result.get("resume_path", ""),
                now,
                result.get("timestamp", now),
                result.get("location", ""),
                result.get("original_verdict", ""),
                result.get("optimized_verdict", ""),
                result.get("jd_match_score"),
                result.get("eval_iterations"),
                result.get("corrections_count"),
                result.get("why_this_role", ""),
                result.get("why_this_company", ""),
                result.get("responsibilities", ""),
                result.get("start_date", ""),
                result.get("end_date", ""),
                url,
            ),
        )
        conn.commit()


def mark_skipped(url: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE jobs SET status='skipped' WHERE job_url=?", (url,))
        conn.commit()


def db_stats() -> dict:
    """Quick summary counts for the session header."""
    with _connect() as conn:
        total   = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        done    = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='done'").fetchone()[0]
        skipped = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='skipped'").fetchone()[0]
    return {"total": total, "done": done, "skipped": skipped}


def import_from_csv(csv_path: str) -> int:
    """
    Seed the DB from an existing jobs.csv or applications.csv.
    Rows whose job_url is already in the DB are skipped (INSERT OR IGNORE).
    Returns the number of rows newly imported.
    """
    path = Path(csv_path)
    if not path.exists():
        return 0
    imported = 0
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            url = (row.get("job_url") or "").strip()
            if not url:
                continue
            jd_text = row.get("job_description", "")
            company = row.get("company_name", "")
            role    = row.get("job_role", "")
            h = jd_fingerprint(jd_text) if jd_text else ""
            ts = row.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M")
            loc = row.get("location") or row.get("job_location", "")
            status = "done" if _int(row.get("optimized_ats_score")) else "scraped"
            with _connect() as conn:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO jobs (
                        job_url, company_name, job_role, job_location,
                        jd_hash, job_description, scraped_at, status,
                        original_ats_score, optimized_ats_score, eval_score,
                        suggested_resume, resume_path, processed_at,
                        timestamp, location, original_verdict, optimized_verdict,
                        jd_match_score, eval_iterations, corrections_count,
                        why_this_role, why_this_company, responsibilities,
                        start_date, end_date
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        url, company, role, loc,
                        h, jd_text[:2000], ts, status,
                        _int(row.get("original_ats_score")),
                        _int(row.get("optimized_ats_score")),
                        _int(row.get("eval_score")),
                        row.get("suggested_resume", ""),
                        row.get("resume_path", ""),
                        ts, ts, loc,
                        row.get("original_verdict", ""),
                        row.get("optimized_verdict", ""),
                        _int(row.get("jd_match_score")),
                        _int(row.get("eval_iterations")),
                        _int(row.get("corrections_count")),
                        row.get("why_this_role", ""),
                        row.get("why_this_company", ""),
                        row.get("responsibilities", ""),
                        row.get("start_date", ""),
                        row.get("end_date", ""),
                    ),
                )
                conn.commit()
                if cur.rowcount:
                    imported += 1
    return imported


def _int(val) -> int | None:
    try:
        return int(val) if val not in (None, "", "None") else None
    except (ValueError, TypeError):
        return None
