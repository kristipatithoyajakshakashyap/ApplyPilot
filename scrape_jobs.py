"""
ApplyPilot — Job Discovery CLI
Config-first: reads job_search_config.yml automatically.
CLI args override config values when explicitly passed.

Usage (config-driven, no args needed):
  python scrape_jobs.py

Usage (CLI override):
  python scrape_jobs.py --roles "ML Engineer" --level senior --count 3
"""
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CONFIG_FILE = Path("job_search_config.yml")

_POSTED_WITHIN_HOURS = {
    "24h": 24,
    "7d":  168,
    "30d": 720,
    "all": None,
}


def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        import yaml
        with open(CONFIG_FILE, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception as e:
        print(f"Warning: could not read {CONFIG_FILE}: {e}")
        return {}


def _parse_csv_arg(value: str) -> list:
    return [item.strip() for item in value.split(",") if item.strip()]


def _get(cfg: dict, *keys, default=None):
    """Safe nested get: _get(cfg, 'search', 'roles', default=[])"""
    node = cfg
    for k in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(k)
        if node is None:
            return default
    return node


def main() -> None:
    cfg = _load_config()

    parser = argparse.ArgumentParser(
        prog="scrape_jobs",
        description=(
            "ApplyPilot Job Discovery — reads job_search_config.yml by default.\n"
            "All args below override the config when explicitly passed."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--roles",    default=None, help="Comma-separated job titles (overrides config)")
    parser.add_argument("--locations",default=None, help="Comma-separated locations (overrides config)")
    parser.add_argument("--level",    default=None, choices=["junior", "mid", "senior", "all"],
                        help="Seniority filter (overrides config)")
    parser.add_argument("--count",    default=None, type=int,
                        help="Jobs per role (overrides config)")
    parser.add_argument("--posted",   default=None, choices=["24h", "7d", "30d", "all"],
                        help="Only jobs posted within this window (overrides config)")
    parser.add_argument("--mode",     default=None, choices=["scrape_only", "ats_report", "full"],
                        help="Pipeline mode (overrides config)")
    args = parser.parse_args()

    # ── Resolve values: CLI arg wins, then config, then hardcoded default ──
    raw_roles     = args.roles     or ",".join(_get(cfg, "search", "roles", default=[]))
    raw_locations = args.locations or ",".join(_get(cfg, "search", "locations", default=[]))
    level         = args.level     or _get(cfg, "search", "level", default="all")
    count         = args.count     or _get(cfg, "search", "count", default=10)
    posted        = args.posted    or _get(cfg, "search", "posted_within", default="7d")
    mode          = args.mode      or _get(cfg, "pipeline", "mode", default="full")
    exclude_companies = _get(cfg, "exclude_companies", default=[]) or []

    # Candidate profile passed to validator
    candidate = _get(cfg, "candidate", default={})

    roles     = _parse_csv_arg(raw_roles)
    locations = _parse_csv_arg(raw_locations)

    if not roles:
        print("Error: no roles defined. Add them to job_search_config.yml or pass --roles.")
        sys.exit(1)
    if not locations:
        print("Error: no locations defined. Add them to job_search_config.yml or pass --locations.")
        sys.exit(1)

    hours_old = _POSTED_WITHIN_HOURS.get(posted)
    level_arg = None if level == "all" else level

    print("\nApplyPilot — Job Discovery")
    if exclude_companies:
        print("  Excluding     : " + ", ".join(exclude_companies))
    print("=" * 48)
    print(f"  Roles         : {', '.join(roles)}")
    print(f"  Locations     : {', '.join(locations)}")
    print(f"  Level         : {level}")
    print(f"  Count         : {count} per role")
    print(f"  Posted within : {posted}")
    print(f"  Mode          : {mode}")
    print(f"  Output        : <role>.csv per role  |  resumes/<role>/")
    if mode != "scrape_only":
        print(f"  Visa status   : {candidate.get('visa_status', 'not set')}")
        print(f"  Sponsorship   : {'required' if candidate.get('needs_sponsorship') else 'not required'}")
    if exclude_companies:
        print("  Excluding     : " + ", ".join(exclude_companies))
    print("=" * 48)

    from src.job_scraper import discover_jobs
    discover_jobs(
        roles=roles,
        locations=locations,
        count=count,
        level=level_arg,
        mode=mode,
        hours_old=hours_old,
        candidate=candidate,
        exclude_companies=exclude_companies,
    )


if __name__ == "__main__":
    main()
