---
name: gate1-eval
description: Run, check and extend the Gate 1 model-upgrade evaluation in this repo (ai-model-lifecycle). Use when asked to compare a current model with a newer one, run or re-run a model pair, read or explain a REPORT.md scorecard, check whether failures are real, add a new model pair, or export results to MLflow.
---

# Gate 1 evaluation

Gate 1 gives a **current** model and its **target** (newer) model the same 4 real
coding tasks, scores every answer automatically, and writes a scorecard per pair:
`ai-model-lifecycle/runs/<pair>/REPORT.md`.

All commands run from the harness folder `ai-model-lifecycle/`, with the Python
environment active (`source .venv/bin/activate`). Setup from scratch:
`ai-model-lifecycle/RUN_AT_HOME.md`.

## Rules (each one exists because breaking it gave a wrong result before)

1. **Health check before spending money.** `docker compose -f docker/docker-compose.yml up -d`,
   then `pytest -q` must pass with **nothing skipped**. A broken setup makes models
   look like they failed.
2. **Model runs cost money.** Confirm with the human before a full run. Try the
   cheap smoke test first.
3. **A real evaluation is `--repeats 3` with all tasks.** Never add `--case` to a real
   run: partial runs are not used as the scorecard.
4. **Never trust a failure until you've seen why it failed.** Run
   `verify_failures.py` and read the evidence before reporting results.
5. **Both models must run on the same provider.** Check `Provider (runs)` in the
   report; otherwise time and cost compare providers, not models.
6. **Cost must be billed.** `Cost source` should say `billed by OpenRouter (12/12)`.
7. **Small samples.** 12 runs per model is rarely statistically significant (the
   report prints Fisher p). Say so; don't call a winner on a 1–2 task difference.
8. **Secrets and commits.** Never read, print or paste `.env`. Don't commit or push
   unless the human has reviewed and approved.

## Workflow: run a pair

```bash
python report.py --list-runs                                        # pairs and existing runs
python runner.py --pair <pair> --case r3_oracle_to_postgres         # smoke test, a few cents
python runner.py --pair <pair> --repeats 3                          # full run (confirm cost first)
python report.py --pair <pair>                                      # writes runs/<pair>/REPORT.md
python verify_failures.py --pair <pair> --repeat 3                  # why each failure failed
```

Check the top of `REPORT.md` before using it:

| Line | Must show |
|---|---|
| `runs loaded` | `24` (4 tasks × 2 models × 3 repeats), no "Partial run" warning |
| `Infra errors (excluded)` | `0` (otherwise API calls failed: re-run) |
| `Provider (runs)` | the same provider for both models, no "different providers" warning |
| `Cost source` | `billed by OpenRouter (12/12)` |

An interrupted run is harmless: run the same command again. Each run gets its
own run id and nothing is overwritten.

## Workflow: verify failures

`python verify_failures.py --pair <pair> --repeat 3` (or `--all-pairs`) re-scores
every failing run with the real scorers and prints the evidence:

| Label | Meaning | What to do |
|---|---|---|
| `MODEL` | The answer is wrong | Read the error line; quote it when reporting |
| `HARNESS?` | Scorer couldn't run (Postgres, Maven, timeout, crash) | Fix the setup, re-run `report.py`; don't blame the model |
| `FLAKY` | Same answer passes sometimes | Report it as unreliable; the check needs fixing |
| `INFRA` | The API call failed | Re-run the pair |

Exit code 1 means at least one `HARNESS?` or `INFRA`: the scorecard isn't
trustworthy yet. Known flaky check: R4's index-scan test on borderline answers.

## Workflow: add a new model pair

1. Find both models' OpenRouter IDs, then check which providers serve **both**:
   `https://openrouter.ai/api/v1/models/<model id>/endpoints` (no key needed).
2. In `models.yaml`, add or uncomment the pair. The default provider is
   `Amazon Bedrock` with fallbacks off; if it doesn't serve both models, set
   `provider: {order: ["<provider>"], allow_fallbacks: false}` on the pair.
3. In `pricing.py`, set both models' input/output prices (USD per 1M tokens). It's
   only a fallback when no billed cost is recorded, but keep it right.
4. `pytest -q`, then the smoke test, then the full run (workflow above).

## Optional: MLflow

Results can be copied into MLflow for charts and history; `runs/` stays the
source of truth. See `ai-model-lifecycle/MLFLOW.md`:

```bash
docker compose -f docker/docker-compose.yml --profile mlflow up -d
python mlflow_export.py --all-pairs          # http://127.0.0.1:5050
```

## Reporting results

Lead with quality, then speed, then cost, for each pair. Give passes as `x/12`,
the overall score and verdict from `REPORT.md`, Fisher p, and one line per
failure with its real error from `verify_failures.py`. Mention any rule above
that wasn't met.
