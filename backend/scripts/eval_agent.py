"""
Eval harness: compare /api/workout/generate vs /api/workout/generate-agent.

Usage
-----
    # With login credentials:
    python -m scripts.eval_agent --base-url http://localhost:8000 \\
        --email demo@fitforge.app --password Demo1234! \\
        --log-file backend.log

    # With a pre-obtained token:
    python -m scripts.eval_agent --token <jwt> --log-file backend.log

    # Without a log file (client-side metrics only):
    python -m scripts.eval_agent --token <jwt>

Server-side telemetry note
--------------------------
The agent emits structured log lines (agent_critique, run_agent complete) that
this script parses from the backend log file to derive rejection rates, issue
category frequencies, parse-error rates, and refine-cycle distributions.

If --log-file is not supplied, those metrics are reported as UNAVAILABLE.
To capture the log locally:

    uvicorn app.main:app --port 8000 2>&1 | tee backend.log

Then pass --log-file backend.log.

For a remote server (e.g. Render), logs are not accessible client-side.
The cleanest alternative there is to add a `debug_telemetry` field to the
/generate-agent response body (gated behind an env flag) and read it here —
but that requires modifying workout.py, which is out of scope for this task.
Ask if you want that route instead.

Env vars (override defaults / avoid putting creds in shell history)
-------------------------------------------------------------------
    FITFORGE_BASE_URL   default: http://localhost:8000
    FITFORGE_TOKEN      skip login, use this token directly
    FITFORGE_EMAIL      for login
    FITFORGE_PASSWORD   for login
    BACKEND_LOG_FILE    path to backend stdout/stderr log file
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent
_DEFAULT_PROFILES = _SCRIPTS_DIR / "eval_profiles.json"
_OUT_DIR = _SCRIPTS_DIR / "out"


# ---------------------------------------------------------------------------
# Log parsing — reads lines emitted by agent_service.py
# ---------------------------------------------------------------------------

# Normal critique line (non-parse-error path):
#   agent_critique iter=0 score=0.750 accepted=False equip_violation=False
#   issue_categories=['equipment'] elapsed_ms=1234
_CRITIQUE_NORMAL_RE = re.compile(
    r"agent_critique iter=(\d+) score=([\d.]+) accepted=(True|False) "
    r"equip_violation=(True|False) issue_categories=(\[.*?\]) elapsed_ms=(\d+)"
)

# Parse-error critique line:
#   agent_critique iter=0 score=0.000 accepted=True equip_violation=False
#   parse_error=1 elapsed_ms=456
_CRITIQUE_PARSE_ERR_RE = re.compile(
    r"agent_critique iter=(\d+) score=0\.000 accepted=True equip_violation=False "
    r"parse_error=1 elapsed_ms=(\d+)"
)

# Final summary line:
#   run_agent complete: total_refine_cycles=1 best_score=0.800 elapsed_ms=5678
_RUN_AGENT_RE = re.compile(
    r"run_agent complete: total_refine_cycles=(\d+) best_score=([\d.]+) elapsed_ms=(\d+)"
)


def _file_size(path: str) -> int:
    try:
        return Path(path).stat().st_size
    except FileNotFoundError:
        return 0


def _read_new_lines(path: str, offset: int) -> list[str]:
    try:
        with open(path, errors="replace") as f:
            f.seek(offset)
            return f.readlines()
    except FileNotFoundError:
        return []


def _parse_telemetry(lines: list[str]) -> dict:
    """Extract agent_critique and run_agent entries from new log lines."""
    critiques: list[dict] = []
    run_agent: dict | None = None

    for line in lines:
        m = _CRITIQUE_NORMAL_RE.search(line)
        if m:
            try:
                categories = ast.literal_eval(m.group(5))
            except (ValueError, SyntaxError):
                categories = []
            critiques.append(
                {
                    "iter": int(m.group(1)),
                    "score": float(m.group(2)),
                    "accepted": m.group(3) == "True",
                    "equip_violation": m.group(4) == "True",
                    "issue_categories": categories,
                    "parse_error": False,
                    "elapsed_ms": int(m.group(6)),
                }
            )
            continue

        m = _CRITIQUE_PARSE_ERR_RE.search(line)
        if m:
            critiques.append(
                {
                    "iter": int(m.group(1)),
                    "score": 0.0,
                    "accepted": True,
                    "equip_violation": False,
                    "issue_categories": [],
                    "parse_error": True,
                    "elapsed_ms": int(m.group(2)),
                }
            )
            continue

        m = _RUN_AGENT_RE.search(line)
        if m:
            run_agent = {
                "total_refine_cycles": int(m.group(1)),
                "best_score": float(m.group(2)),
                "elapsed_ms": int(m.group(3)),
            }

    if not critiques and run_agent is None:
        return {}

    return {
        "critiques": critiques,
        "total_refine_cycles": run_agent["total_refine_cycles"] if run_agent else None,
        "best_score": run_agent["best_score"] if run_agent else None,
        "source": "log_file",
    }


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(base_url: str, email: str, password: str, client: httpx.Client) -> str:
    resp = client.post(
        f"{base_url}/api/auth/login",
        data={"username": email, "password": password},
        timeout=30.0,
    )
    if resp.status_code != 200:
        print(f"Login failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()["access_token"]


def _post_with_backoff(
    client: httpx.Client,
    url: str,
    body: dict,
    token: str,
    max_retries: int = 6,
) -> tuple[httpx.Response | None, int | None]:
    """POST with exponential backoff on 429. Returns (response, elapsed_ms).

    A 429 is not recorded as an elapsed_ms sample — the returned elapsed_ms
    reflects only the successful (non-429) call.
    """
    delay = 2.0
    for attempt in range(max_retries):
        t0 = time.perf_counter()
        try:
            resp = client.post(
                url,
                json=body,
                headers=_auth_headers(token),
                timeout=180.0,
            )
        except httpx.TimeoutException:
            print(f"  [timeout] attempt {attempt + 1}/{max_retries}", file=sys.stderr)
            time.sleep(delay)
            delay = min(delay * 2, 60.0)
            continue

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", delay))
            wait = max(retry_after, delay)
            print(f"  [429] rate-limited. waiting {wait:.0f}s (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait)
            delay = min(delay * 2, 60.0)
            continue

        return resp, elapsed_ms

    return None, None  # exhausted retries


# ---------------------------------------------------------------------------
# Per-profile result
# ---------------------------------------------------------------------------

def _run_profile(
    profile: dict,
    profile_id: int,
    base_url: str,
    token: str,
    log_file: str | None,
    client: httpx.Client,
) -> dict:
    # Strip metadata fields before sending to the API
    body = {k: v for k, v in profile.items() if not k.startswith("_")}
    label = profile.get("_label", profile.get("name", str(profile_id)))
    adversarial = profile.get("_adversarial", False)

    result: dict = {
        "profile_id": profile_id,
        "profile_label": label,
        "adversarial": adversarial,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "generate": None,
        "generate_agent": None,
    }

    # ── /generate ────────────────────────────────────────────────────────────
    resp, elapsed_ms = _post_with_backoff(client, f"{base_url}/api/workout/generate", body, token)
    if resp is None:
        result["generate"] = {"success": False, "status_code": None, "elapsed_ms": None, "error": "max retries exceeded"}
    elif resp.status_code == 200:
        result["generate"] = {"success": True, "status_code": 200, "elapsed_ms": elapsed_ms, "error": None}
    else:
        result["generate"] = {
            "success": False,
            "status_code": resp.status_code,
            "elapsed_ms": elapsed_ms,
            "error": resp.text[:300],
        }

    # ── /generate-agent ───────────────────────────────────────────────────────
    log_offset = _file_size(log_file) if log_file else None

    resp, elapsed_ms = _post_with_backoff(client, f"{base_url}/api/workout/generate-agent", body, token)

    if log_file and log_offset is not None:
        new_lines = _read_new_lines(log_file, log_offset)
        telemetry = _parse_telemetry(new_lines) or None
    else:
        telemetry = None

    if resp is None:
        result["generate_agent"] = {
            "success": False,
            "status_code": None,
            "elapsed_ms": None,
            "error": "max retries exceeded",
            "telemetry": telemetry,
        }
    elif resp.status_code == 200:
        result["generate_agent"] = {
            "success": True,
            "status_code": 200,
            "elapsed_ms": elapsed_ms,
            "error": None,
            "telemetry": telemetry,
        }
    else:
        result["generate_agent"] = {
            "success": False,
            "status_code": resp.status_code,
            "elapsed_ms": elapsed_ms,
            "error": resp.text[:300],
            "telemetry": telemetry,
        }

    return result


# ---------------------------------------------------------------------------
# Summary computation
# ---------------------------------------------------------------------------

def _percentile(data: list[float], p: int) -> float | None:
    if not data:
        return None
    data = sorted(data)
    idx = (p / 100) * (len(data) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(data) - 1)
    frac = idx - lo
    return data[lo] + frac * (data[hi] - data[lo])


def _compute_summary(results: list[dict], log_available: bool) -> dict:
    n = len(results)
    n_fail_gen = sum(1 for r in results if not r["generate"]["success"])
    n_fail_agent = sum(1 for r in results if not r["generate_agent"]["success"])

    gen_latencies = [
        r["generate"]["elapsed_ms"]
        for r in results
        if r["generate"]["success"] and r["generate"]["elapsed_ms"] is not None
    ]
    agent_latencies = [
        r["generate_agent"]["elapsed_ms"]
        for r in results
        if r["generate_agent"]["success"] and r["generate_agent"]["elapsed_ms"] is not None
    ]

    # Telemetry-based stats ─────────────────────────────────────────────────
    tel_results = [
        r for r in results
        if r["generate_agent"].get("telemetry") and r["generate_agent"]["telemetry"]
    ]
    tel_n = len(tel_results)

    # Critic rejection rate: share of runs where first critique rejected
    first_accepted: list[bool] = []
    for r in tel_results:
        crits = r["generate_agent"]["telemetry"].get("critiques", [])
        if crits:
            first_accepted.append(crits[0]["accepted"])

    rejection_rate = (
        sum(1 for a in first_accepted if not a) / len(first_accepted)
        if first_accepted else None
    )
    adv_first_accepted = [
        crits[0]["accepted"]
        for r in tel_results
        if r["adversarial"]
        for crits in [r["generate_agent"]["telemetry"].get("critiques", [])]
        if crits
    ]
    adv_rejection_rate = (
        sum(1 for a in adv_first_accepted if not a) / len(adv_first_accepted)
        if adv_first_accepted else None
    )

    # Issue category frequency (across all critique calls)
    cat_counts: dict[str, int] = {"goal": 0, "equipment": 0, "level": 0, "completeness": 0}
    total_critique_calls = 0
    parse_errors = 0
    for r in tel_results:
        crits = r["generate_agent"]["telemetry"].get("critiques", [])
        total_critique_calls += len(crits)
        for c in crits:
            parse_errors += int(c.get("parse_error", False))
            for cat in c.get("issue_categories", []):
                if cat in cat_counts:
                    cat_counts[cat] += 1

    parse_error_rate = (
        parse_errors / total_critique_calls if total_critique_calls > 0 else None
    )

    # Refine cycle distribution
    cycle_dist: dict[str, int] = {"0": 0, "1": 0, "2+": 0}
    for r in tel_results:
        cycles = r["generate_agent"]["telemetry"].get("total_refine_cycles")
        if cycles is None:
            continue
        if cycles == 0:
            cycle_dist["0"] += 1
        elif cycles == 1:
            cycle_dist["1"] += 1
        else:
            cycle_dist["2+"] += 1

    # Refine outcome: of runs that refined, how many had best_score > score_iter_0
    refined = [
        r for r in tel_results
        if (r["generate_agent"]["telemetry"].get("total_refine_cycles") or 0) > 0
    ]
    refinement_improved = 0
    refinement_unchanged = 0
    for r in refined:
        crits = r["generate_agent"]["telemetry"].get("critiques", [])
        best = r["generate_agent"]["telemetry"].get("best_score")
        if crits and best is not None:
            score_iter_0 = crits[0]["score"]
            if best > score_iter_0 + 1e-6:
                refinement_improved += 1
            else:
                refinement_unchanged += 1

    return {
        "n": n,
        "n_fail_gen": n_fail_gen,
        "n_fail_agent": n_fail_agent,
        "gen_latencies": gen_latencies,
        "agent_latencies": agent_latencies,
        "log_available": log_available,
        "tel_n": tel_n,
        "rejection_rate": rejection_rate,
        "adv_rejection_rate": adv_rejection_rate,
        "cat_counts": cat_counts,
        "total_critique_calls": total_critique_calls,
        "parse_error_rate": parse_error_rate,
        "cycle_dist": cycle_dist,
        "refined_n": len(refined),
        "refinement_improved": refinement_improved,
        "refinement_unchanged": refinement_unchanged,
    }


def _format_summary(s: dict) -> str:
    pct = lambda x: f"{x * 100:.1f}%" if x is not None else "UNAVAILABLE"
    ms = lambda x: f"{x:.0f}ms" if x is not None else "—"
    na = "UNAVAILABLE (pass --log-file to capture server-side telemetry)"

    gen_lats = s["gen_latencies"]
    agt_lats = s["agent_latencies"]
    gen_p50 = _percentile(gen_lats, 50)
    gen_p95 = _percentile(gen_lats, 95)
    agt_p50 = _percentile(agt_lats, 50)
    agt_p95 = _percentile(agt_lats, 95)

    delta_p50 = (agt_p50 - gen_p50) if (agt_p50 is not None and gen_p50 is not None) else None
    delta_p95 = (agt_p95 - gen_p95) if (agt_p95 is not None and gen_p95 is not None) else None

    cat = s["cat_counts"]
    tel_n = s["tel_n"]
    n_runs = tel_n or s["n"]

    def cat_line(name: str) -> str:
        count = cat.get(name, 0)
        share = count / n_runs if n_runs else 0
        return f"    {name:<14} {count:>4}  ({pct(share)} of runs)"

    lines = [
        "=" * 60,
        "FITFORGE AGENT EVAL SUMMARY",
        "=" * 60,
        "",
        f"Profiles run:        {s['n']}",
        f"Failures /generate:  {s['n_fail_gen']}",
        f"Failures /agent:     {s['n_fail_agent']}",
        "",
        "── Latency (client-side wall-clock) ─────────────────────",
        f"  /generate       p50={ms(gen_p50)}   p95={ms(gen_p95)}",
        f"  /generate-agent p50={ms(agt_p50)}   p95={ms(agt_p95)}",
        f"  delta (agent - base)  p50={ms(delta_p50)}   p95={ms(delta_p95)}",
        "",
    ]

    if not s["log_available"]:
        lines += [
            "── Server-side telemetry ─────────────────────────────────",
            f"  {na}",
            "",
            "  To enable: run the backend with",
            "    uvicorn app.main:app 2>&1 | tee backend.log",
            "  and pass --log-file backend.log",
        ]
    else:
        lines += [
            f"── Telemetry ({tel_n}/{s['n']} runs with log data) ────────",
            "",
            f"  Critic rejection rate (1st critique):  {pct(s['rejection_rate'])}",
            f"  Adversarial profiles rejection rate:   {pct(s['adv_rejection_rate'])}",
            "",
            "  Issue-category frequency (all critique calls):",
            cat_line("equipment"),
            cat_line("goal"),
            cat_line("level"),
            cat_line("completeness"),
            "",
            f"  Total critique calls:  {s['total_critique_calls']}",
            f"  Parse-error rate:      {pct(s['parse_error_rate'])}",
            "",
            "  Refine-cycle distribution:",
            f"    0 cycles  {s['cycle_dist']['0']:>4}  ({pct(s['cycle_dist']['0']/n_runs if n_runs else None)})",
            f"    1 cycle   {s['cycle_dist']['1']:>4}  ({pct(s['cycle_dist']['1']/n_runs if n_runs else None)})",
            f"    2+ cycles {s['cycle_dist']['2+']:>4}  ({pct(s['cycle_dist']['2+']/n_runs if n_runs else None)})",
            "",
            f"  Runs that entered refine: {s['refined_n']}",
            f"  Of those, refinement improved best_score:  {s['refinement_improved']}",
            f"  Of those, refinement did not improve:      {s['refinement_unchanged']}",
        ]

    lines += ["", "=" * 60]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Eval harness: /generate vs /generate-agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--base-url",
        default=os.environ.get("FITFORGE_BASE_URL", "http://localhost:8000"),
        help="Backend base URL (default: http://localhost:8000)",
    )
    p.add_argument(
        "--token",
        default=os.environ.get("FITFORGE_TOKEN"),
        help="JWT token (skip login)",
    )
    p.add_argument(
        "--email",
        default=os.environ.get("FITFORGE_EMAIL"),
        help="Email for login",
    )
    p.add_argument(
        "--password",
        default=os.environ.get("FITFORGE_PASSWORD"),
        help="Password for login",
    )
    p.add_argument(
        "--profiles",
        type=Path,
        default=_DEFAULT_PROFILES,
        help="Path to eval_profiles.json",
    )
    p.add_argument(
        "--log-file",
        default=os.environ.get("BACKEND_LOG_FILE"),
        help="Backend stdout/stderr log file for server-side telemetry",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N profiles (for quick smoke tests)",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    # ── Load profiles ─────────────────────────────────────────────────────────
    try:
        profiles: list[dict] = json.loads(args.profiles.read_text())
    except FileNotFoundError:
        print(f"Profiles file not found: {args.profiles}", file=sys.stderr)
        sys.exit(1)

    if args.limit:
        profiles = profiles[: args.limit]

    print(f"Loaded {len(profiles)} profiles from {args.profiles}")

    # ── Output file ───────────────────────────────────────────────────────────
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = _OUT_DIR / f"eval_raw_{ts}.jsonl"
    summary_path = _OUT_DIR / f"eval_summary_{ts}.md"
    raw_file = raw_path.open("w")
    print(f"Writing raw results to {raw_path}")

    # ── Auth ──────────────────────────────────────────────────────────────────
    with httpx.Client() as client:
        if args.token:
            token = args.token
        elif args.email and args.password:
            print("Logging in…")
            token = _login(args.base_url, args.email, args.password, client)
            print("Authenticated.")
        else:
            print(
                "ERROR: provide --token or (--email + --password) / env vars "
                "FITFORGE_TOKEN / FITFORGE_EMAIL + FITFORGE_PASSWORD",
                file=sys.stderr,
            )
            sys.exit(1)

        # Log file existence check
        log_available = False
        if args.log_file:
            if not Path(args.log_file).exists():
                print(
                    f"WARNING: --log-file {args.log_file!r} does not exist yet. "
                    "Server-side telemetry will be partial until the file appears.",
                )
            else:
                log_available = True

        # ── Main loop ─────────────────────────────────────────────────────────
        results: list[dict] = []
        for i, profile in enumerate(profiles):
            label = profile.get("_label", profile.get("name", str(i)))
            adv_tag = " [ADVERSARIAL]" if profile.get("_adversarial") else ""
            print(f"\n[{i + 1}/{len(profiles)}] {label}{adv_tag}")

            result = _run_profile(
                profile=profile,
                profile_id=i,
                base_url=args.base_url,
                token=token,
                log_file=args.log_file,
                client=client,
            )
            results.append(result)

            raw_file.write(json.dumps(result) + "\n")
            raw_file.flush()

            # Determine log availability after first result
            if args.log_file and not log_available:
                if Path(args.log_file).exists():
                    log_available = True

            # Quick status print
            gen = result["generate"]
            agt = result["generate_agent"]
            gen_status = f"{gen['elapsed_ms']}ms" if gen["success"] else f"FAIL({gen['status_code']})"
            agt_status = f"{agt['elapsed_ms']}ms" if agt["success"] else f"FAIL({agt['status_code']})"

            tel = agt.get("telemetry") or {}
            tel_str = ""
            if tel.get("critiques"):
                first = tel["critiques"][0]
                rejected = "rejected" if not first["accepted"] else "accepted"
                cycles = tel.get("total_refine_cycles", "?")
                best = tel.get("best_score", "?")
                tel_str = f"  critic={rejected}, cycles={cycles}, best={best}"

            print(f"  /generate: {gen_status}  /agent: {agt_status}{tel_str}")

    raw_file.close()
    print(f"\nRaw results written to {raw_path}")

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = _compute_summary(results, log_available)
    summary_text = _format_summary(summary)

    print("\n" + summary_text)

    # Write summary to markdown file
    summary_path.write_text(
        f"# FitForge Agent Eval — {ts}\n\n```\n{summary_text}\n```\n"
    )
    print(f"\nSummary written to {summary_path}")


if __name__ == "__main__":
    main()
