"""scorers/dispatch.py — score a run-record against every applicable scorer.

Given a run JSON (from runs/<pair>/<model>.<case>.json) and the model's raw
output, dispatch to the case's scorer and return a ScoreResult dict. Unknown or
not-yet-implemented cases return a structured "skipped" result.

This is the single entry point report.py uses, so adding a case = adding a mapping
entry here (pair-agnostic by construction).
"""

from __future__ import annotations

from pathlib import Path

from .base import ScoreResult

# case_id -> scorer module name (imported lazily so a missing DB dep never blocks
# the report from importing).
SCORER_MAP: dict[str, str] = {
    "r1_springboot2to3": "scorers.r1_scorer",
    "r3_oracle_to_postgres": "scorers.r3_scorer",
    "r4_schema_load_optimize": "scorers.r4_scorer",
    "r5_etl_dashboard": "scorers.r5_scorer",
    # real suite (models.yaml `suites: real`)
    "r1b_jhipster_boot3": "scorers.r1b_scorer",
    "r2_gwt_to_angular": "scorers.r2_scorer",
    "r7_shogun_hibernate6": "scorers.r7_scorer",
    "r8_shogun_rust": "scorers.r8_scorer",
}


def score_case(case_id: str, output_text: str, model_slug: str = "",
               base: Path | None = None) -> ScoreResult:
    """Dispatch to the registered scorer for `case_id`, or return a skipped result.

    `base` (repair rounds only) is the project tree to apply the answer onto;
    only the project-based scorers (r1b, r2) accept it."""
    mod_name = SCORER_MAP.get(case_id)
    if not mod_name:
        return ScoreResult(
            case_id=case_id,
            model_slug=model_slug,
            passed=False,
            score=0.0,
            reason=f"no scorer registered for case {case_id!r} (skipped)",
        )
    try:
        import importlib

        mod = importlib.import_module(mod_name)
        if base is not None:
            return mod.score(output_text, model_slug=model_slug, base=base)
        return mod.score(output_text, model_slug=model_slug)
    except Exception as exc:  # noqa: BLE001 - a broken scorer must not kill the report
        return ScoreResult(
            case_id=case_id,
            model_slug=model_slug,
            passed=False,
            score=0.0,
            reason=f"scorer error: {type(exc).__name__}: {exc}",
        )


def score_run_record(record: dict) -> ScoreResult:
    """Score a single run record (dict) by its embedded output_text."""
    case_id = record.get("case_id", "")
    model_slug = record.get("model_slug", "")
    text = record.get("output_text") or ""
    return score_case(case_id, text, model_slug)
