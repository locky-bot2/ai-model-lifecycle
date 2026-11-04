# Plan: a harder, less memorizable successor to r1b

Status: **proposal, not started** (2026-11-04). Nothing here has been built or run.

## Why

The owner's manager: "Haiku can solve it so fast, r1b seems easy."

What the results actually show:

| Evidence | What it means |
|---|---|
| Single-shot (one reply, no tools): **every model scored 0%** on r1b | The migration is genuinely hard without building and testing |
| Agentic: **every counted attempt passes** (all 9 Claude rows, GLM-5.3) | r1b no longer **separates** the models on pass rate (a ceiling); only time and cost do |
| Haiku 5.5 high re-run: 18.3 min vs 28.6–40.7 min before | Mostly the **easier setup** (migrated tests now provided), not a jump in skill |
| The project is the public `jhipster-sample-app`; its Boot 3 version is public too | Models have very likely **seen the answer in training**. The sandbox stops looking it up, not remembering it (GLM-5.3's log recalls JHipster 8 from memory) |
| No model passes r1b within 15 minutes (Pass@900s = 0% for every row) | Time-based measures still separate the models |

So the next real-project task should (1) not be memorizable, (2) be hard
enough that not everyone passes, and (3) be measured over repeats, so time and
pass-within-a-budget can rank models with some confidence.

## Options

### A. Disguised r1b ("r1c"): same app, renamed. Fast, reuses everything

Take `jhipster-sample-app` v7.9.3 and rename it so it no longer matches the
public project or JHipster's templates verbatim:

* package `io.github.jhipster.sample` → e.g. `com.acme.ledger`; app name and
  artifact id changed;
* entities `BankAccount` / `Operation` / `Label` → e.g. `Wallet` / `Entry` /
  `Tag`, with their tables, REST paths (`/api/bank-accounts` → `/api/wallets`),
  DTOs and Liquibase changelogs;
* strip JHipster branding: `GeneratedByJHipster`, `.yo-rc.json`, the
  `generator-jhipster` devDependency, `jhipster`-named comments and config
  keys where the app doesn't need them;
* apply the **same renames** to the hidden tests (38 Java files) and to the
  Cypress suite (54 tests: routes, selectors, entity names).

| Pros | Cons |
|---|---|
| Reuses the proven scorer, hidden tests, Cypress cache and sandbox | The JHipster *structure* is still recognizable to a model that knows JHipster well |
| About 1–2 days to build and validate | It's still a well-documented Boot 2 → 3 migration (the official migration guide applies) |
| Directly comparable with r1b: same work, minus memorization | |

### B. A fresh, never-published app ("r6"): the strongest fix

Write a new, realistic Spring Boot 2.7 / Java 11 application for this
benchmark and never publish it. Memorization is then impossible.

* **Size and shape like r1b:** about 40–60 main classes, JPA + Hibernate 5,
  Spring Security 5 (JWT), a REST API, Liquibase, Ehcache, mail, scheduled
  jobs, `javax.*` throughout. Include the APIs that change in Boot 3: Security
  config, Hibernate types, `spring.factories`, config properties, Jakarta.
* **Hidden tests written with it:** unit and integration (≥100), plus API
  contract tests (exact JSON bodies, status codes, security rules). Optionally
  a small UI with browser tests.
* **A reference migration,** to prove the task is solvable and the tests are
  right (the same `--baseline` idea as r2).
* **Kept private:** in a private repo, never pushed to a public remote. The
  sandbox keeps blocking everything but Maven and npm.

| Pros | Cons |
|---|---|
| No model can have seen it; tests the migration skill only | About 1–2 weeks to build well (app, tests, reference migration) |
| We control the difficulty: we can add traps (deprecated-API removals, behavior changes) | Must be realistic, or the results won't transfer to real projects |
| Can be reused for future models without contamination | Must stay private, and be rotated if it leaks |

### C. Raise the bar on the migration itself

Add requirements on top of A or B, so "builds and tests pass" isn't the whole
job:

* target **Java 21 + Spring Boot 3.3** (not just 3.1), with no deprecated APIs
  (a `-Werror` deprecation check);
* **behavior parity:** API contract tests that compare exact responses with
  the original app's;
* **performance:** a startup-time or request-latency budget;
* **security:** the same rules, plus a check that no endpoint became public by
  accident (Spring Security 6 changes the defaults; GLM and Haiku both hit
  this on r1b).

## Measurement changes (apply to whichever task is chosen)

1. **Repeats on the real projects:** 3 attempts per model and level (today it's
   1), so pass rate and time have a spread and a confidence.
2. **Rank by time to pass:** the Pass@15/30/60-minute columns already exist.
   With repeats, they separate models even when everyone eventually passes.
3. **A memorization probe (cheap, do first):** ask each model single-shot,
   with no project and no tools, to write the Boot 3 version of a few r1b files
   (e.g. `SecurityConfiguration`, `ExceptionTranslator`) and compare with the
   published v8.0.0. High similarity confirms memorization and justifies B.
   Cost: cents to a few dollars.

## Recommendation

| Phase | What | Effort | Model-run cost |
|---|---|---|---|
| 0 | Memorization probe on r1b | ½ day | about $1–3 (Go) plus a little subscription |
| 1 | **A + C-lite:** disguised r1b ("r1c"), target Boot 3.3 / Java 21, with API contract tests | 2–3 days | Claude: 9 rows × 3 repeats × about 30 min ≈ 13–14 h of subscription over several days; GLM-5.3: 3 × about $18 ≈ $55 (or 1 repeat ≈ $18) |
| 2 | **B:** a fresh private app ("r6"), if phase 0 confirms memorization or phase 1 still shows a ceiling | 1–2 weeks | similar to phase 1 |

Keep r1b on the leaderboard for continuity; add the new task to the `real`
suite (`models.yaml`) so it shows as its own table.

**Success criteria for the new task:**

* not every model passes every attempt (pass rate separates them), **or**
* time to pass differs clearly across repeats (Pass@30 min separates them);
* the reference migration passes every hidden test (the task is solvable);
* no attempt can find the answer: nothing public to look up, and
  generator-style blueprints don't match.

## Files that would change (phase 1)

| What | Where |
|---|---|
| Disguised project (a pinned private fork, or a rename script applied to the r1b sources) | `cases/r1c_*/`, `cases/sources.py` |
| Prompt and goal (Boot 3.3 / Java 21) | `cases/r1c_*/prompt.md`, `agentic.py` `CASES` |
| Hidden tests renamed, plus API contract tests | `scorers/fixtures/r1c_hidden_tests/` |
| Scorer (fork of `r1b_scorer.py`: Java 21, deprecation check, contract tests) | `scorers/r1c_scorer.py`, `scorers/dispatch.py` |
| Cypress suite renamed, and its cache | `cases/r1c_*/setup_e2e.sh` |
| Real suite | `models.yaml` `suites.real` |
| Tests | `tests/test_real_suite.py`, `tests/test_agentic.py` |

## Open questions for the owner

1. Is ~2 weeks for option B acceptable later, or should phase 1 (A + C-lite) be
   the target for now?
2. Repeats: 3 per model and level on the real projects means about 13–14 h of
   Claude subscription. Run all 9 Claude rows, or medium only (about 4.5 h)?
3. GLM-5.3 on the new task: 1 or 3 attempts (about $18 each at Go list price)?
4. Should the new app ever be shown outside the team? If so, plan to rotate it.
