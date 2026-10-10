"""verify_failures.py — re-check every failing run and show WHY it failed.

A failure in REPORT.md is only a number until someone reads the real error.
This tool re-scores each failing run with the same scorers report.py uses and
prints the evidence, so a human (or an agent) can decide whether it is a
genuine model mistake or a harness problem.

For each failing run it shows:
  * the scorer's reason and the failed checks;
  * the real error: the FIRST error lines from psql (R4/R5 scorers keep only the
    tail of psql's output, which can cut off the line that matters), the R3
    error or result mismatch, the R1 Maven tail, or the R4 query plan;
  * a classification:
      INFRA      the API call itself failed (excluded from the scorecard)
      HARNESS?   the scorer could not do its job (Postgres/Maven unavailable,
                 scorer crash, timeout) - fix the setup, not the model
      FLAKY      re-scoring the same answer gave different results
      MODEL      the answer itself is wrong - read the error to confirm

Usage (Postgres running, Docker available):
    python verify_failures.py --pair haiku-4.5-vs-5.5            # latest complete run
    python verify_failures.py --pair haiku-4.5-vs-5.5 --run 20261009T154316Z
    python verify_failures.py --all-pairs --repeat 3             # also check stability
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field

import common
import report
from common import load_config, load_env
from scorers import dispatch

# reasons that mean the scorer, not the model, failed
_HARNESS_PATTERNS = re.compile(
    r"scorer error|postgres unavailable|maven unavailable|UNVERIFIED|no scorer registered|"
    r"timeout after|could not connect|connection refused|command not found",
    re.I,
)
_PSQL_ERROR = re.compile(r"^(?:psql:\S*\s*)?(ERROR|FATAL):.*$", re.M)


@dataclass
class Finding:
    file: str
    model: str
    case: str
    verdict: str                     # MODEL / HARNESS? / FLAKY / INFRA
    reason: str
    evidence: list[str] = field(default_factory=list)
    results: list[bool] = field(default_factory=list)


class _PsqlCapture:
    """Wraps run_psql in the R4/R5 scorers to keep psql's FULL output."""

    MODULES = ("scorers.r4_scorer", "scorers.r5_scorer")

    def __init__(self):
        self.outputs: list[str] = []
        self._saved: list[tuple[object, object]] = []

    def __enter__(self):
        import importlib
        for name in self.MODULES:
            mod = importlib.import_module(name)
            orig = mod.run_psql

            def wrapped(sql, schema, *a, _orig=orig, **kw):
                rc, out = _orig(sql, schema, *a, **kw)
                self.outputs.append(out or "")
                return rc, out

            self._saved.append((mod, orig))
            mod.run_psql = wrapped
        return self

    def __exit__(self, *exc):
        for mod, orig in self._saved:
            mod.run_psql = orig
        return False


def _evidence(case_id: str, sr, psql_outputs: list[str]) -> list[str]:
    d = sr.details or {}
    ev: list[str] = []
    failed = [k for k, ok in (sr.checks or {}).items() if not ok]
    if failed:
        ev.append("failed checks: " + ", ".join(failed))
    for out in psql_outputs:                              # first error lines, full text
        for m in _PSQL_ERROR.finditer(out):
            start = out.rfind("\n", 0, m.start()) + 1
            ev.append(" ".join(out[start:start + 400].split()))
            break
    if d.get("error") and not any("ERROR" in e for e in ev):
        ev.append(" ".join(str(d["error"]).split())[:400])
    if case_id.startswith("r3"):
        if d.get("missing_objects"):
            ev.append(f"missing objects: {d['missing_objects']}")
        if d.get("golden_shape") is not None:
            ev.append(f"result shape: expected {d.get('golden_shape')}, got {d.get('produced_shape')}")
        if d.get("dialect_hits"):
            ev.append(f"Oracle syntax left: {d['dialect_hits']}")
    if case_id.startswith("r4") and d.get("plan"):
        scans = [ln.strip() for ln in str(d["plan"]).splitlines() if "Scan" in ln][:4]
        ev.append("plan: " + " | ".join(scans))
    if case_id.startswith("r1"):
        for k in ("compile_tail", "test_tail", "hidden_test_tail"):
            if d.get(k) and ("ERROR" in d[k] or "FAIL" in d[k]):
                lines = [ln for ln in d[k].splitlines() if "ERROR" in ln or "FAIL" in ln][:4]
                ev.append(f"{k}: " + " | ".join(ln.strip()[:200] for ln in lines))
        if d.get("tests_run"):
            ev.append(f"tests run: {d['tests_run']}")
    return list(dict.fromkeys(ev))           # R5 runs the script twice: drop repeated errors


def check_run(cfg, pair_id: str, rid: str, repeat: int = 1, score=dispatch.score_case) -> list[Finding]:
    """Re-score every run file of one harness run; return a Finding per failure."""
    findings: list[Finding] = []
    for rec in common.load_runs(pair_id, run=rid):
        name, case = rec.get("model_name", rec.get("model_slug", "?")), rec.get("case_id", "?")
        if report.is_infra_error(rec):
            findings.append(Finding(rec["_file"], name, case, "INFRA", f"API call failed: {rec.get('error')}"))
            continue
        results, first, outputs = [], None, []
        for i in range(max(1, repeat)):
            with _PsqlCapture() as cap:
                sr = score(case, rec.get("output_text") or "", rec.get("model_slug", ""))
            results.append(bool(sr.passed))
            if first is None or (not sr.passed and first.passed):
                first, outputs = sr, cap.outputs
            if i == 0 and sr.passed:
                break                    # passing answers are scored once; only failures are repeated
        if all(results):
            continue
        reason = first.reason or ""
        if len(set(results)) > 1:
            verdict = "FLAKY"
        elif _HARNESS_PATTERNS.search(reason) or _HARNESS_PATTERNS.search(str((first.details or {}).get("error", ""))):
            verdict = "HARNESS?"
        else:
            verdict = "MODEL"
        findings.append(Finding(rec["_file"], name, case, verdict, reason, _evidence(case, first, outputs), results))
    return findings


def render(pair_id: str, rid: str, findings: list[Finding]) -> str:
    lines = [f"== {pair_id}  run {rid}: {len(findings)} failing run(s)"]
    for f in findings:
        rep = f"  [{sum(f.results)}/{len(f.results)} passes on re-score]" if len(f.results) > 1 else ""
        lines.append(f"\n[{f.verdict}] {f.model} · {f.case}{rep}\n  file:   {f.file}\n  reason: {f.reason}")
        lines += [f"  - {e}" for e in f.evidence]
    counts = {v: sum(f.verdict == v for f in findings) for v in ("MODEL", "HARNESS?", "FLAKY", "INFRA")}
    lines.append("\nsummary: " + ", ".join(f"{k} {n}" for k, n in counts.items() if n) if findings
                 else "\nsummary: no failures")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Re-check failing Gate 1 runs and show why they failed")
    ap.add_argument("--pair", help="pair id (e.g. haiku-4.5-vs-5.5)")
    ap.add_argument("--all-pairs", action="store_true")
    ap.add_argument("--run", help="run id; default: the latest complete run (same as report.py)")
    ap.add_argument("--repeat", type=int, default=1,
                    help="score each failing answer N times to spot flaky checks (default 1)")
    args = ap.parse_args(argv)
    if not (args.pair or args.all_pairs):
        ap.error("give --pair <id> or --all-pairs")

    load_env()
    cfg = load_config()
    pair_ids = [p.id for p in cfg.pairs] if args.all_pairs else [args.pair]
    any_harness = False
    for pid in pair_ids:
        rid = args.run or report.pick_run(cfg, pid)[0]
        if not rid:
            print(f"== {pid}: no runs")
            continue
        findings = check_run(cfg, pid, rid, args.repeat)
        any_harness |= any(f.verdict in ("HARNESS?", "INFRA") for f in findings)
        print(render(pid, rid, findings) + "\n")
    return 1 if any_harness else 0


if __name__ == "__main__":
    raise SystemExit(main())
