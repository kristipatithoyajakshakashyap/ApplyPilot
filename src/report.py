"""Terminal report printer."""


def _suggested_resume(orig_score: int, opt_score: int) -> str:
    if opt_score >= 85 and opt_score >= orig_score:
        return "Optimized"
    if orig_score >= 85 and orig_score >= opt_score:
        return "Original"
    if opt_score > orig_score:
        return "Optimized (best effort)"
    return "Original (optimized did not improve)"


def print_report(
    ats_orig: dict,
    ats_opt: dict,
    jd_match: dict,
    new_resume: dict,
    job_info: dict = None,
    eval_result: dict = None,
    iterations: int = 1,
    elapsed_secs: float = 0.0,
) -> str:
    """Print full optimization report. Returns the suggested_resume value."""
    bar = "=" * 62
    print(f"\n{bar}")
    print("  OPTIMIZATION REPORT")
    print(bar)

    # Job info block
    if job_info:
        print(f"\nCOMPANY     {job_info.get('company_name', 'Unknown')}")
        print(f"ROLE        {job_info.get('job_role', 'Unknown')}")
        print(f"LOCATION    {job_info.get('location', 'Unknown')}")
        print(f"START DATE  {job_info.get('start_date', 'Immediate')}")
        print(f"END DATE    {job_info.get('end_date', 'N/A')}")

        responsibilities = job_info.get("responsibilities", "")
        if responsibilities:
            print(f"\nROLE OVERVIEW")
            _wrap(responsibilities, 60)

        why_role = job_info.get("why_this_role", "")
        if why_role:
            print(f"\nWHY THIS ROLE")
            _wrap(why_role, 60)

        why_company = job_info.get("why_this_company", "")
        if why_company:
            print(f"\nWHY THIS COMPANY")
            _wrap(why_company, 60)

    # ATS scores
    orig_score = ats_orig.get("score", 0)
    opt_score  = ats_opt.get("score", 0)
    delta = opt_score - orig_score
    sign  = "+" if delta >= 0 else ""

    print(f"\nATS SCORE")
    print(f"  Original   {orig_score}/100  [{ats_orig.get('verdict', '?')}]")
    print(f"  Optimized  {opt_score}/100  [{ats_opt.get('verdict', '?')}]")
    print(f"  Change     {sign}{delta} pts")

    # Evaluator result (HackerRank hiring-agent framework)
    if eval_result:
        ev_score  = eval_result.get("score", 0)
        ev_passed = eval_result.get("passed", False)
        final_raw = eval_result.get("final_score", 0)
        bonus     = eval_result.get("bonus_points", {}).get("total", 0)
        deduct    = eval_result.get("deductions",   {}).get("total", 0)
        sc        = eval_result.get("scores", {})
        print(f"\nEVALUATOR SCORE  {ev_score}/100  raw={final_raw}/120  ({'PASSED' if ev_passed else 'FAILED'})")
        print(f"  Open Source        {round(sc.get('open_source',      {}).get('score', 0))}/35")
        print(f"  Self Projects      {round(sc.get('self_projects',    {}).get('score', 0))}/30")
        print(f"  Production         {round(sc.get('production',       {}).get('score', 0))}/25")
        print(f"  Technical Skills   {round(sc.get('technical_skills', {}).get('score', 0))}/10")
        print(f"  Bonus Points      +{bonus}")
        print(f"  Deductions        -{deduct}")
        print(f"  Iterations needed  {iterations}")

    # JD match
    dim = jd_match.get("dimension_scores", {})
    print(f"\nJD MATCH SCORE  {jd_match.get('match_score', '?')}/100")
    if dim:
        for k, v in dim.items():
            print(f"  {k.replace('_', ' ').title():<20} {v}/100")

    # Corrections
    corrections = new_resume.get("corrections", [])
    if corrections:
        print(f"\nCORRECTIONS APPLIED ({len(corrections)})")
        for c in corrections:
            print(f"  + {c}")

    # Issues fixed
    critical = ats_orig.get("critical_issues", [])
    if critical:
        print(f"\nCRITICAL ISSUES FIXED ({len(critical)})")
        for i in critical:
            print(f"  x {i}")

    high = ats_orig.get("high_priority", [])
    if high:
        print(f"\nHIGH-PRIORITY ISSUES FIXED ({len(high)})")
        for i in high:
            print(f"  ! {i}")

    # Strengths retained
    strengths = jd_match.get("strengths", [])
    if strengths:
        print(f"\nSTRENGTHS RETAINED")
        for s in strengths[:5]:
            print(f"  + {s}")

    # Suggested resume
    suggestion = _suggested_resume(orig_score, opt_score)
    print(f"\nSUGGESTED RESUME")
    print(f"  Submit     {suggestion}")
    if opt_score >= 85:
        print(f"  Reason     Optimized resume passes ATS threshold (>= 85)")
    elif orig_score >= 85:
        print(f"  Reason     Original already passes ATS threshold; optimization did not improve further")
    else:
        print(f"  Reason     Neither version passes ATS threshold — submit optimized as best effort")

    # Time taken
    if elapsed_secs > 0:
        m, s = divmod(int(elapsed_secs), 60)
        time_str = f"{m}m {s}s" if m else f"{s}s"
        print(f"\nTIME TAKEN   {time_str}")

    print()
    return suggestion


def _wrap(text: str, width: int = 60) -> None:
    words = text.split()
    line = "  "
    for word in words:
        if len(line) + len(word) + 1 > width:
            print(line)
            line = "  " + word
        else:
            line = line + (" " if line != "  " else "") + word
    if line.strip():
        print(line)