"""tests/test_verify_failures.py — the failure re-check tool.

Offline: a fake scorer stands in for the real ones, except the last test, which
checks the psql capture against the real R5 scorer and needs Postgres.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import common
import verify_failures as vf
from common import load_config

PAIR = "haiku-4.5-vs-5.5"
RID = "20261010T000000Z"


def _write(runs_dir, cfg, *, error_for=None):
    pair = cfg.get_pair(PAIR)
    d = runs_dir / PAIR
    d.mkdir(parents=True, exist_ok=True)
    for role, m in (("current", pair.current), ("target", pair.target)):
        for case in cfg.cases:
            rec = {"pair_id": PAIR, "case_id": case, "model_slug": m.id, "model_name": m.name, "role": role,
                   "rep": 0, "run_id": RID, "output_text": f"{role}:{case}", "ok": True, "error": None}
            if error_for == (role, case):
                rec.update(ok=False, error="RateLimitError: 429", output_text="")
            (d / f"{m.id.replace('/', '__')}.{case}.{RID}.json").write_text(json.dumps(rec))


def _scorer(rule):
    """rule(case, text, call_no) -> (passed, reason, details)."""
    calls: dict[str, int] = {}

    def score(case, text, slug):
        calls[text] = calls.get(text, 0) + 1
        passed, reason, details = rule(case, text, calls[text])
        return SimpleNamespace(passed=passed, reason=reason, checks={"x": passed}, details=details)
    score.calls = calls
    return score


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "RUNS_DIR", tmp_path / "runs")
    return load_config()


def test_model_failure_with_evidence(cfg, tmp_path):
    _write(tmp_path / "runs", cfg)
    score = _scorer(lambda c, t, n: (not t.startswith("target:r3"),
                                     "result set != golden", {"error": "UndefinedObject: type \"exception\""}))
    (f,) = vf.check_run(cfg, PAIR, RID, score=score)
    assert f.verdict == "MODEL" and f.case.startswith("r3")
    assert any("exception" in e for e in f.evidence)


def test_harness_problem_is_not_blamed_on_the_model(cfg, tmp_path):
    _write(tmp_path / "runs", cfg)
    score = _scorer(lambda c, t, n: (not c.startswith("r4"), "postgres unavailable (no psycopg2)", {}))
    findings = vf.check_run(cfg, PAIR, RID, score=score)
    assert {f.verdict for f in findings} == {"HARNESS?"} and len(findings) == 2


def test_flaky_check_is_detected_and_only_failures_are_repeated(cfg, tmp_path):
    _write(tmp_path / "runs", cfg)
    # target R4 fails on the first score, passes on the second
    score = _scorer(lambda c, t, n: (t != "target:r4_schema_load_optimize" or n == 2, "index_scan", {}))
    (f,) = vf.check_run(cfg, PAIR, RID, repeat=3, score=score)
    assert f.verdict == "FLAKY" and f.results == [False, True, False]
    assert max(n for t, n in score.calls.items() if t != "target:r4_schema_load_optimize") == 1


def test_infra_error_is_reported_without_scoring(cfg, tmp_path):
    _write(tmp_path / "runs", cfg, error_for=("target", "r1_springboot2to3"))
    score = _scorer(lambda c, t, n: (True, "ok", {}))
    (f,) = vf.check_run(cfg, PAIR, RID, score=score)
    assert f.verdict == "INFRA" and "429" in f.reason
    assert "" not in score.calls                        # the empty answer was never scored


def test_render_summary(cfg, tmp_path):
    _write(tmp_path / "runs", cfg)
    score = _scorer(lambda c, t, n: (not t.startswith("current:r5"), "failed checks: etl_runs", {}))
    out = vf.render(PAIR, RID, vf.check_run(cfg, PAIR, RID, score=score))
    assert "[MODEL]" in out and "summary: MODEL 1" in out


def test_psql_capture_keeps_the_first_error_line():
    """The capture sees psql's full output, so the real ERROR line reaches the evidence."""
    from scorers import r5_scorer
    from scorers.base import pg_available
    if not pg_available()[0]:
        pytest.skip("Postgres not running")
    long_sql = "SELECT 1/0;\n" + "\n".join(f"-- filler {i} " + "x" * 80 for i in range(40))
    with vf._PsqlCapture() as cap:
        sr = r5_scorer.score(f"### FILE: etl.sql\n```sql\n{long_sql}\n```\n")
    assert not sr.passed
    ev = vf._evidence("r5_etl_dashboard", sr, cap.outputs)
    assert any("division by zero" in e for e in ev), ev
