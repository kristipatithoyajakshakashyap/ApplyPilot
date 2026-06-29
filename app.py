#!/usr/bin/env python3
"""ApplyPilot Dashboard — Flask backend.
Run:  pip install flask
      python app.py
Open: http://127.0.0.1:5000
"""
import json, queue, shutil, sqlite3, subprocess, sys, threading
from datetime import datetime
from pathlib import Path

import yaml
from flask import Flask, Response, jsonify, request, send_from_directory

app      = Flask(__name__)
BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "applypilot.db"
CONFIG_PATH = BASE_DIR / "job_search_config.yml"

_log_queue: "queue.Queue[str | None]" = queue.Queue(maxsize=2000)
_is_running = threading.Event()
_current_proc: subprocess.Popen | None = None


# ── DB ──────────────────────────────────────────────────────────────────────────
def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ── Pages ────────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(str(BASE_DIR), "dashboard.html")


# ── Jobs ─────────────────────────────────────────────────────────────────────────
@app.route("/api/jobs")
def get_jobs():
    if not DB_PATH.exists():
        return jsonify([])
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY processed_at DESC, scraped_at DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/jobs/<int:job_id>/applied", methods=["POST"])
def set_applied(job_id):
    data    = request.get_json(force=True)
    applied = bool(data.get("applied", False))
    ts      = datetime.now().strftime("%Y-%m-%d %H:%M") if applied else None
    with _db() as conn:
        conn.execute(
            "UPDATE jobs SET applied=?, applied_at=? WHERE id=?",
            (1 if applied else 0, ts, job_id),
        )
        conn.commit()
    return jsonify({"ok": True, "applied": applied, "applied_at": ts})


# ── Config ───────────────────────────────────────────────────────────────────────
@app.route("/api/config", methods=["GET"])
def get_config():
    if not CONFIG_PATH.exists():
        return jsonify({})
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    return jsonify(cfg)


@app.route("/api/config", methods=["POST"])
def save_config():
    data = request.get_json(force=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return jsonify({"ok": True})


# ── Process runner ───────────────────────────────────────────────────────────────
def _run(cmd: list) -> None:
    global _current_proc
    _is_running.set()
    _log_queue.put("$ " + " ".join(cmd))
    try:
        _current_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(BASE_DIR),
        )
        for line in _current_proc.stdout:
            _log_queue.put(line.rstrip("\n\r"))
        _current_proc.wait()
        code = _current_proc.returncode
        _log_queue.put(f"\n[Process exited — code {code}]")
    except Exception as exc:
        _log_queue.put(f"[ERROR] {exc}")
    finally:
        _current_proc = None
        _is_running.clear()
        _log_queue.put(None)  # SSE sentinel


def _clear_queue() -> None:
    while not _log_queue.empty():
        try:
            _log_queue.get_nowait()
        except queue.Empty:
            break


# ── Scrape ───────────────────────────────────────────────────────────────────────
@app.route("/api/scrape", methods=["POST"])
def start_scrape():
    if _is_running.is_set():
        return jsonify({"error": "A process is already running"}), 409
    _clear_queue()
    threading.Thread(
        target=_run,
        args=([sys.executable, "-u", "scrape_jobs.py"],),
        daemon=True,
    ).start()
    return jsonify({"ok": True})


@app.route("/api/scrape/stop", methods=["POST"])
def stop_scrape():
    global _current_proc
    if _current_proc and _is_running.is_set():
        try:
            _current_proc.terminate()
            _log_queue.put("\n[Process terminated by user]")
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
    _is_running.clear()
    _log_queue.put(None)
    return jsonify({"ok": True})


# ── Optimize ──────────────────────────────────────────────────────────────────────
@app.route("/api/optimize", methods=["POST"])
def start_optimize():
    if _is_running.is_set():
        return jsonify({"error": "A process is already running"}), 409
    data = request.get_json(force=True)
    _clear_queue()

    if data.get("url"):
        cmd = [sys.executable, "-u", "main.py", "--url", data["url"], "--optimize"]
    else:
        company = data.get("company", "Unknown")
        role    = data.get("role", "")
        jd_text = data.get("jd", "")
        if not jd_text.strip():
            return jsonify({"error": "JD text is required"}), 400
        tmp = BASE_DIR / "_tmp_jd.txt"
        tmp.write_text(jd_text, encoding="utf-8")
        cmd = [sys.executable, "-u", "main.py",
               "--company", company, "--jd", str(tmp), "--optimize"]
        if role:
            cmd += ["--role", role]

    threading.Thread(target=_run, args=(cmd,), daemon=True).start()
    return jsonify({"ok": True})


# ── SSE log stream ────────────────────────────────────────────────────────────────
@app.route("/api/logs/stream")
def log_stream():
    def generate():
        yield "data: " + json.dumps({"line": "--- Log stream connected ---"}) + "\n\n"
        while True:
            try:
                line = _log_queue.get(timeout=25)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            if line is None:
                yield "data: " + json.dumps({"line": "--- Process finished ---", "done": True}) + "\n\n"
                break
            yield "data: " + json.dumps({"line": line}) + "\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/status")
def api_status():
    return jsonify({"running": _is_running.is_set()})


# ── Reset ─────────────────────────────────────────────────────────────────────────
@app.route("/api/reset", methods=["POST"])
def reset():
    if _is_running.is_set():
        return jsonify({"error": "Stop the running process first"}), 409
    # Clear all jobs from DB
    if DB_PATH.exists():
        with _db() as conn:
            conn.execute("DELETE FROM jobs")
            conn.commit()
    # Delete resume output folders
    for folder in ["resumes", "optimized", "job_resumes"]:
        p = BASE_DIR / folder
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    # Delete per-role CSVs (files like ml_engineer.csv, data_scientist.csv)
    for csv_file in BASE_DIR.glob("*.csv"):
        if csv_file.name not in ("applications.csv",):
            csv_file.unlink(missing_ok=True)
    return jsonify({"ok": True})


if __name__ == "__main__":
    from src.db import init_db
    init_db()
    print("\nApplyPilot Dashboard  ->  http://127.0.0.1:5000\n")
    app.run(debug=False, threaded=True, port=5000)
