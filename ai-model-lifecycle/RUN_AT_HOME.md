# Run Gate 1 on your own PC

This guide gets you from nothing to a Gate 1 scorecard on a home PC, using
OpenRouter for the models. No OpenClaw is needed. You can type the commands
yourself, or ask a coding agent (opencode, Claude Code) to run them for you.

**What Gate 1 does:** it gives a current model and its newer version the same 4
real coding tasks, checks every answer automatically, and writes a scorecard
comparing quality, speed and cost.

**Time:** about 30 minutes to set up, then 10–30 minutes per model pair.
**Cost:** you pay OpenRouter for the model calls (see [Cost](#cost-and-time)).

---

## 1. What you need

| Item | Version / notes | Check it works |
|---|---|---|
| **Docker Desktop** | Any recent version, **running** | `docker ps` prints a table, not an error |
| **Python** | 3.11 or newer | `python3 --version` |
| **Git** | Any | `git --version` |
| **uv** (recommended) | Python package manager | `uv --version` |
| **OpenRouter API key** | From [openrouter.ai/keys](https://openrouter.ai/keys), with some credit | Starts with `sk-or-v1-` |
| **Free port 5432** | Used by the Postgres container | Stop any local Postgres you already run |

**Install links:**
[Docker Desktop](https://www.docker.com/products/docker-desktop/) ·
[Python](https://www.python.org/downloads/) ·
[Git](https://git-scm.com/downloads) ·
[uv](https://docs.astral.sh/uv/getting-started/installation/)

### Windows users

Run everything **inside WSL2 (Ubuntu)**, not in PowerShell:

1. Install WSL: open PowerShell as admin and run `wsl --install`, then restart.
2. In Docker Desktop: **Settings → Resources → WSL integration →** turn on your Ubuntu distro.
3. Open the **Ubuntu** app and run every command in this guide there.
4. Inside Ubuntu, install Python tools: `sudo apt update && sudo apt install -y python3 python3-venv git`

Mac (Intel or Apple Silicon) and Linux need nothing extra.

---

## 2. One-time setup

### 2.1 Get the code

```bash
git clone https://github.com/locky-bot2/ai-model-lifecycle.git
cd ai-model-lifecycle/ai-model-lifecycle
```

All commands below run from this `ai-model-lifecycle/ai-model-lifecycle` folder.

### 2.2 Add your API key

```bash
cp .env.example .env
```

Open `.env` in a text editor and replace `sk-or-v1-REPLACE_ME` with your real
OpenRouter key. Leave the Postgres lines as they are.

> **Keep the key private.** `.env` is ignored by Git, so it is never committed.
> Edit it yourself; don't paste the key into an AI chat.

### 2.3 Install the Python packages

With **uv** (recommended):

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

Or with plain **pip**:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> There is no `pyproject.toml`, so `uv sync` does **not** work here. Use one of
> the two options above.

Then activate the environment (do this in every new terminal):

```bash
source .venv/bin/activate
```

### 2.4 Start Postgres

```bash
docker compose -f docker/docker-compose.yml up -d
```

### 2.5 Check everything works

```bash
pytest -q
```

Expected: **`79 passed`** (the number may grow) and **nothing skipped**.

| You see | Meaning | Fix |
|---|---|---|
| `N skipped` | Postgres or Docker isn't reachable | Make sure Docker Desktop is running and step 2.4 worked |
| `ModuleNotFoundError` | Environment not active | Run `source .venv/bin/activate` |
| Tests take a few minutes the first time | Docker is downloading Postgres and Maven | Normal; later runs are fast |

Don't run any models until this passes. A broken setup makes models look like
they failed.

---

## 3. Run an evaluation

### 3.1 See which model pairs exist

```bash
python report.py --list-runs
```

Current pairs: `opus-4.8-vs-5.5`, `sonnet-5-vs-5.5`, `sonnet-4.6-vs-5.5`,
`haiku-4.5-vs-5.5`. They are defined in `models.yaml`.

### 3.2 (Recommended) Try one cheap task first

This checks your key works and costs only a few cents:

```bash
python runner.py --pair haiku-4.5-vs-5.5 --case r3_oracle_to_postgres
```

Each line should end in `OK`. If you see `FAIL (... 401 ...)` or
`AuthenticationError`, your key in `.env` is wrong or has no credit.

### 3.3 Run a full pair

```bash
python runner.py --pair sonnet-5-vs-5.5 --repeats 3
python report.py --pair sonnet-5-vs-5.5
```

Or every pair at once:

```bash
python runner.py --all-pairs --repeats 3
python report.py --all-pairs
```

**Rules for a valid run:**

- **Always use `--repeats 3`.** One run per task is too few to compare models.
- **Don't add `--case`** for a real evaluation. A run with only some tasks is
  marked *partial* and is not used as the scorecard.
- **Don't stop it halfway.** If it is interrupted, just run the same command
  again. Every run gets its own ID, so nothing is overwritten.

### 3.4 Read the result

Open `runs/<pair>/REPORT.md`. Check the top first:

```
> Run: 20261009T025500Z  ·  runs loaded: 24  ·  live scoring: on
```

- **`runs loaded: 24`** for a full pair (4 tasks × 2 models × 3 repeats).
- **No "Partial run" warning.**
- **`Infra errors (excluded)` is 0.** If not, some API calls failed; re-run.
- **`Provider (runs)` shows the same provider for both models**, e.g.
  `Amazon Bedrock ×12` in both columns, with no "different providers" warning.
  Otherwise speed and cost compare two providers, not two models.
- **`Cost source` says `billed by OpenRouter (12/12)`.** If it mentions the
  price table, those runs have no billed cost and their cost is an estimate.

---

## 4. How to read the scorecard

| Line | What it means |
|---|---|
| **Quality (pass rate)** | Share of tasks each model solved. Matters most. |
| **Fisher p** | Whether a quality difference is real. **Below 0.05** = real; above = could be luck. |
| **95% CI** | Likely range of the true pass rate. Wide range = not enough data. |
| **Time / Cost per run** | Speed and price per task. |
| **Provider (runs)** | Which provider served each model's runs. Both models should use the same one. |
| **Cost source** | Where the cost comes from: what OpenRouter billed (preferred) or the `pricing.py` table (fallback). |
| **Overall score** | Current model = **100**. Above 100: the new model is better overall. Below: worse. Weights: Quality 50%, Cost 30%, Time 20%. Cost and time each count between 50 and 150, so a huge price or speed gap can't outweigh quality on its own. A new model that passes fewer tasks is never marked "target ≥ baseline". |
| **Failing runs** | Every failure with its reason. Read these before trusting a result. |

> **Provider and cost:** every call is pinned to one provider (Amazon Bedrock for
> the Claude pairs, set in `models.yaml`) with fallbacks off, and the report uses
> the cost OpenRouter actually billed. The `pricing.py` table is only a fallback
> for runs without a billed cost.

---

## 5. Using opencode or Claude Code

You can let a coding agent do the work. Paste this prompt into opencode or
Claude Code, opened in the `ai-model-lifecycle/ai-model-lifecycle` folder:

```text
In this repo, run Gate 1 for the pair sonnet-5-vs-5.5 with 3 repeats.
1. Start Postgres: docker compose -f docker/docker-compose.yml up -d
2. Activate .venv and run `pytest -q`. Stop and tell me if anything fails or is skipped.
3. Run: python runner.py --pair sonnet-5-vs-5.5 --repeats 3
4. Run: python report.py --pair sonnet-5-vs-5.5
5. Show me the top of runs/sonnet-5-vs-5.5/REPORT.md and the "Failing runs" table.
Do not change any code or files other than what these commands create.
Do not read or print the .env file.
```

To check whether each failure is the model's fault or a harness problem, run:

```bash
python verify_failures.py --pair sonnet-5-vs-5.5 --repeat 3
```

It re-scores every failing run, shows the real error, and labels it `MODEL`
(genuine model mistake), `HARNESS?` (setup problem), `FLAKY` (result changes on
re-score) or `INFRA` (API call failed). Or ask the agent:

```text
Run python verify_failures.py --pair sonnet-5-vs-5.5 --repeat 3 and summarize
each failure: the model, the task, the real error, and whether it's a genuine
model mistake.
```

Agents get these rules and steps automatically from the repo's `gate1-eval`
skill (`.claude/skills/gate1-eval/`); see its README for OpenClaw and opencode.

---

## 6. Cost and time

Approximate, per pair, with `--repeats 3` (billed by OpenRouter, runs on
2026-10-09, all on Amazon Bedrock):

| Pair | Cost | Time |
|---|---|---|
| `opus-4.8-vs-5.5` | ~$2.50 | 20–30 min |
| `sonnet-5-vs-5.5` | ~$1.20 | 15–20 min |
| `sonnet-4.6-vs-5.5` | ~$1.20 | 15–20 min |
| `haiku-4.5-vs-5.5` | ~$0.20 | 10–15 min |
| **All 4 pairs** | **~$5** | **1–1.5 h** |

The smoke test in 3.2 (one Haiku task, both models) costs about $0.02.

The first R1 run is slower while Maven downloads its dependencies.

---

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `docker: command not found` or `Cannot connect to the Docker daemon` | Start Docker Desktop. On Windows, enable WSL integration (section 1). |
| `port is already allocated` / `5432` in use | Stop your local Postgres, or change `5432` in `docker/docker-compose.yml` **and** `POSTGRES_PORT` in `.env`. |
| `password authentication failed` | Make sure `.env` has `POSTGRES_HOST=127.0.0.1`, not `localhost`. |
| Every run shows `FAIL (AuthenticationError ...)` | Wrong or empty OpenRouter key, or no credit. |
| `RateLimitError` / `429` | The runner retries automatically. If it persists, wait and re-run. |
| `REPORT.md` didn't change | It only updates when you run `report.py`. Check the `Run:` line at the top. |
| Report shows an older run | The newest run is partial or incomplete. Run `python report.py --list-runs` to see which runs are complete. |

---

## 8. When you're done

Stop Postgres (your data is kept for next time):

```bash
docker compose -f docker/docker-compose.yml stop
```

Share results by sending the `runs/<pair>/REPORT.md` file, or commit the
`runs/` folder if you have push access:

```bash
git add runs/
git commit -m "Gate 1 results: <pair>, 3 repeats"
git push
```

---

## Quick reference

```bash
source .venv/bin/activate
docker compose -f docker/docker-compose.yml up -d
pytest -q                                              # 79 passed, 0 skipped
python report.py --list-runs                           # pairs and runs
python runner.py --pair <pair> --repeats 3             # run
python report.py --pair <pair>                         # scorecard → runs/<pair>/REPORT.md
python report.py --pair <pair> --run <run-id>          # scorecard for an older run
docker compose -f docker/docker-compose.yml stop
```
