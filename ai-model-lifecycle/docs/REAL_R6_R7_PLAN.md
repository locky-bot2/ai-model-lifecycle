# Two new real-project tasks (r6 .NET, r7 Java) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two real-project agentic tasks to the Gate 1 harness, then run one screening attempt each with Haiku 5.5 (medium) and GLM-5.3, to look for a real project Haiku fails and GLM passes.

**Architecture:** Each task follows the r2 pattern: a pinned upstream snapshot fetched by `cases/sources.py`, a `_setup_rN` that fills the sandbox workspace, a scorer that rebuilds the harvested workspace outside the sandbox and runs **private** grading tests, and a reference migration that proves the task is solvable (`--baseline`). Screening runs use `--track` so nothing reaches the main board.

**Tech Stack:** Python harness (agentic.py, scorers/, pytest); Docker agent image (Debian bookworm); .NET 10 SDK, EF Core + SQLite, Playwright; Java 17, Maven, Hibernate 6, Spring 6, JUnit 5.

**Spec:** `docs/PASSDOWN_REAL_R6_R7.md` (findings and the owner's decisions, 2026-11-11), plus the test-visibility rule in `docs/R1B_NEXT_PLAN.md` ("Test visibility: one rule for the new task"; on PR #58's branch until it merges).

**Status:** proposal, awaiting the owner's review (2026-11-11). Nothing built yet.

## Global Constraints

- Case ids: `r6_bonobo_aspnetcore` and `r7_shogun_hibernate6`. (R1B_NEXT_PLAN's hypothetical fresh app "r6" becomes "r8" if it is ever built; update that doc's wording in Task 7.)
- r6 source: `jakubgarfield/Bonobo-Git-Server` @ `6277ecfe1015b4612795bf8bb0f03ae2dd25b1ad` (2021-03-05), MIT.
- r7 source: `terrestris/shogun-core` @ `d1881aa2f2c41d00d308ff7f794c34c76dd5a925` (2024-01-16), Apache-2.0.
- r6 target: ASP.NET Core on **.NET 10** (`net10.0`); .NET 8 support ended 2026-11-10.
- r7 target: Hibernate ORM 6.x, `jakarta.persistence`, JUnit Jupiter 5.x (no JUnit 4, no vintage engine, no PowerMock), Spring Framework 6.x (not Boot), Java 17.
- Test visibility: the agent gets the project's **own** tests in their original form and the spec; our grading tests are **never** in the workspace; the scorer always grades with its own copy.
- Time limit 60 min (default 3600 s), agent not told the limit; network = allowlist sandbox.
- Screening: Haiku 5.5 `--effort medium` and GLM-5.3 (medium), 1 attempt each per case, `--track real-screen`. GLM spend is confirmed with the owner before the run.
- Owner rules: no commit or push before the owner reviews; never read or print `.env`; secret-scan before any commit; forking repos to `abralock/` is outward-facing, so confirm first.

## Review Focus

1. **r7 grading tests that only compile against one migration.** Our private tests call the public API; an agent that renames a class or changes a signature fails on compile, not on behaviour. Pin it: the prompt lists what must stay (every public class and method name, except the pinned `Criterion` replacement), and Task 5's test `test_r7_hidden_tests_use_only_public_api` checks the fixture imports no class the original project lacks, except the pinned replacement.
2. **r6 git smart-HTTP over Kestrel.** Clone and push through the migrated app is the most likely thing to break silently: the page loads but `git push` hangs or 500s. Pin it: Task 4's git suite runs `git clone`, `git commit`, `git push`, then a second `clone` that must contain the pushed commit, with a 60 s timeout per command.
3. **A fresh database on every scorer run.** Leftover SQLite or Git data from the agent's own runs would let a broken migration pass. Pin it: the scorer deletes `App_Data` before starting the app; `test_r6_scorer_starts_from_empty_app_data`.
4. **Tests the agent deleted or skipped (r7).** An agent could "migrate" by deleting hard tests. Pin it: the `own_tests` check needs at least 95% of the original test count run, with none `@Disabled`; `test_r7_own_tests_counts_disabled_as_missing`.
5. **Dependencies the sandbox can't reach.** shogun-core needs three artifacts that aren't on Maven Central; a missing one fails every model equally and looks like a model failure. Pin it: Task 1 seeds them, and the `--baseline` run of the reference in the sandbox must pass before any screening run.

---

### Task 1: Sources, cache and sandbox prerequisites

**Files:**
- Modify: `cases/sources.lock.json`, `cases/sources.py` (two new entries; same fork and pinned-commit pattern as r1b and r2)
- Create: `cases/r6_bonobo_aspnetcore/setup.sh`, `cases/r7_shogun_hibernate6/setup.sh`
- Modify: `docker/agent/Dockerfile` (add the .NET 10 SDK and `git`, if missing), `docker/egress/allowlist.txt` (add `^api\.nuget\.org$`)
- Test: `tests/test_real_suite.py`

**Interfaces:**
- Produces: `cache_dir()/r6_bonobo_aspnetcore/source/` (the pinned snapshot, the whole solution with the original MSTest project); `cache_dir()/r7_shogun_hibernate6/source/` (the pinned snapshot); `cache_dir()/r7_shogun_hibernate6/m2/` (a Maven local repo with the original build's whole dependency closure, made with `mvn -Dmaven.repo.local=… dependency:go-offline` against `https://nexus.terrestris.de/repository/public/`, which serves `gt-main` 22.2, `deegree-core-commons` 3.4.11 and `structured-content-tools` 1.3.11).

- [ ] **Step 1:** Ask the owner to approve forking both repos to `abralock/`, then fork them.
- [ ] **Step 2:** Write the failing tests `test_r6_sources_locked` and `test_r7_sources_locked`: `cases.sources.problems(case_id) == []` after a fetch.
- [ ] **Step 3:** Add the lock entries, then run `python -m cases.sources`. Expected: both tests pass.
- [ ] **Step 4:** Write `setup.sh` for each case to build the cache above. r7 runs `mvn -q -DskipTests -Dmaven.repo.local=$CACHE/m2 package` once on the original (Java 8: `/opt/java8` in the image) to prove the closure resolves.
- [ ] **Step 5:** Dockerfile and allowlist changes. Verify in Docker: `dotnet --list-sdks` shows 10.x; `dotnet new console && dotnet add package Microsoft.Data.Sqlite` restores through the proxy; `curl https://github.com/` is still refused.
- [ ] **Step 6:** Run `pytest -q`. Expected: everything passes, nothing skipped. Show the owner the diff (no commit).

### Task 2: Register both cases in the harness (before the references, which run through it)

**Files:**
- Modify: `agentic.py`:
  - `_setup_r6`: copy `source/` into the workspace, original tests included;
  - `_setup_r7`: copy `source/`, and copy `m2/` into the workspace's Maven repo the way the entrypoint's settings.xml expects;
  - two `CASES` entries, with `goal`, `deliverables`, `exclude` and `task_note`.
- Create: `cases/r6_bonobo_aspnetcore/prompt.md`, `cases/r7_shogun_hibernate6/prompt.md`
- Modify: `models.yaml` (a `real-screen` suite, not `real`, until the screening is reviewed)
- Test: `tests/test_agentic.py`

**Interfaces:**
- r6 `deliverables`: `["**/*.cs", "**/*.cshtml", "**/*.csproj", "**/*.json", "**/*.config", "Bonobo.Git.Server/wwwroot/**", "Bonobo.Git.Server/Content/**", "Bonobo.Git.Server/Scripts/**"]`. `exclude`: `["**/bin/**", "**/obj/**", "**/App_Data/**"]`.
- r7 `deliverables`: `["pom.xml", "**/pom.xml", "src/**"]`. `exclude`: `["target/**"]`.
- The goals state each scorer's checks in plain words, as r1b's does. Each prompt states the target contract (drafted here from the Interfaces of Tasks 3 and 5, and frozen when those tasks confirm it), what is out of scope, which tests are provided ("the project's own tests, in their original form"), and the off-limits sources (no other version of the project, and no upstream successor such as `terrestris/shogun`).

- [ ] **Step 1:** Write the failing tests:
  - `test_r6_setup_has_solution_and_no_grading_tests`: the workspace has `Bonobo.Git.Server.sln` and no file from `scorers/fixtures/r6_acceptance`;
  - `test_r7_setup_has_original_junit4_tests_and_seeded_m2`;
  - `test_new_cases_in_real_screen_suite`.
- [ ] **Step 2:** Implement; then run `pytest -q`. Expected: all pass, nothing skipped.
- [ ] **Step 3 (after Tasks 4 and 5):** Run a dry run in the sandbox with no model: `_setup_rN` plus a no-op agent, then score. Expected: r6 fails only from `net10` on; r7 fails only from `hibernate6` on. This proves setup, harvest and scorer agree.
- [ ] **Step 4:** Show the owner the diff of Tasks 1–2 for review (no commit until approved); the same review again after Task 5, with the scorers.

### Task 3: r6 reference migration (Bonobo → ASP.NET Core / .NET 10)

**Files:**
- Create: the reference on fork branch `abralock/Bonobo-Git-Server:gate1-reference` (not in this repo). Fetch it into `cache_dir()/r6_bonobo_aspnetcore/reference/` via a third lock entry.

**Interfaces:**
- Produces the target contract every agent must meet, which the prompt states:
  - `Bonobo.Git.Server/Bonobo.Git.Server.csproj` is SDK-style with `net10.0`;
  - it starts with `dotnet run --project Bonobo.Git.Server --urls http://0.0.0.0:5080`;
  - the SQLite database and Git repositories live under `Bonobo.Git.Server/App_Data/`, created on first start;
  - the default admin login is `admin` / `admin` (confirm in the original seed code first);
  - git smart-HTTP is at `/<repo>.git`, using the `git` on PATH;
  - only cookie login with the internal membership store. Active Directory, Windows auth and WS-Federation are removed.

- [ ] **Step 1:** Read the original's seed and auth code; record the admin login and the routes the UI uses.
- [ ] **Step 2:** Produce a first draft with Opus 5.5 high in the sandbox: `agentic.py --case r6_bonobo_aspnetcore --time-limit 10800 --track r6-reference` (subscription, never counted on a board). Then finish it by hand.
- [ ] **Step 3:** Check it by hand: log in; create a user, a team and a repository; clone, push and clone again; browse the tree, the commits and one file.
- [ ] **Step 4:** Push the branch (owner approves first); add the lock entry.

### Task 4: r6 private grading tests and scorer

**Files:**
- Create: `scorers/fixtures/r6_acceptance/ui.spec.ts`, `git.spec.ts`, `playwright.config.ts`
- Create: `scorers/r6_scorer.py`
- Modify: `scorers/dispatch.py` (`SCORER_MAP`)
- Test: `tests/test_r6_scorer.py`

**Interfaces:**
- Consumes: Task 3's target contract.
- Produces: `score(output_text: str, *, model_slug: str = "", workdir: Path | None = None, base: Path | None = None) -> ScoreResult` with checks, in order:
  - `edits_applied`;
  - `net10`: the csproj targets `net10.0` and nothing references `System.Web`;
  - `build`: `dotnet build -c Release`;
  - `starts`: GET `/` or the login page returns 2xx within 120 s, on a fresh `App_Data`;
  - `ui`: at least 10 tests, all pass;
  - `git`: at least 4 tests, all pass.

  Also `baseline() -> int`, as in r2.

- [ ] **Step 1:** Write `ui.spec.ts`: log in as admin; create a user; create a team with that user; create a repository; the repository list shows it; open its tree, commits and a blob page after a push; edit settings; the user can log in; a wrong password shows the error; logging out works. One retry per test, as r2 does.
- [ ] **Step 2:** Write `git.spec.ts`: anonymous clone of a private repo is refused (401); clone with the admin login; commit and push; a second clone contains the commit. Each git command has a 60 s timeout.
- [ ] **Step 3:** Write the failing tests:
  - `test_r6_scorer_original_fails_net10`: scoring the untouched snapshot gives `net10 == False` and `passed == False`;
  - `test_r6_scorer_starts_from_empty_app_data`: an `App_Data` holding a stray `.db` is removed before start;
  - `test_r6_baseline_passes` (slow): the reference passes all 6 checks.
- [ ] **Step 4:** Implement the scorer: copy the workspace to a temp dir; delete `App_Data`; build; start it on a free port; wait for HTTP; run both suites. Playwright runs in the node image the r2 scorer uses.
- [ ] **Step 5:** Run `pytest tests/test_r6_scorer.py -v`, then `python -m scorers.r6_scorer --baseline`. Expected: pass, and 6/6 checks on the reference.

### Task 5: r7 reference migration, private tests and scorer

**Files:**
- Create: the reference on fork branch `abralock/shogun-core:gate1-reference`
- Create: `scorers/fixtures/r7_hidden_tests/` (the reference's migrated `src/test`, JUnit 5)
- Create: `scorers/r7_scorer.py`; modify `scorers/dispatch.py`
- Test: `tests/test_r7_scorer.py`

**Interfaces:**
- Produces the API contract the prompt states:
  - every public class and method keeps its name, package (`de.terrestris.shogun.*`) and parameters, except that each DAO/service method taking `org.hibernate.criterion.Criterion…` instead takes `de.terrestris.shogun.dao.QueryRestriction<E>…`;
  - `QueryRestriction<E>` is a new functional interface with the single method `jakarta.persistence.criteria.Predicate toPredicate(jakarta.persistence.criteria.Root<E> root, jakarta.persistence.criteria.CriteriaQuery<?> query, jakarta.persistence.criteria.CriteriaBuilder cb)`. Confirm the method list against `GenericHibernateDao` before freezing it.
- Produces `score(...) -> ScoreResult` with checks, in order:
  - `edits_applied`;
  - `hibernate6`: `hibernate-core` 6.x in the effective pom;
  - `jakarta`: no `javax.persistence` or `javax.servlet` imports in `src/main`;
  - `junit5`: no `org.junit.Test`, `org.junit.runner`, `org.powermock` or `junit-vintage` in the agent's `src/test` or pom;
  - `java17`;
  - `build`;
  - `own_tests`: the agent's own migrated tests run at least 95% of the original count (record the exact number in Step 1), none skipped or `@Disabled`, all pass;
  - `hidden_tests`: our fixture swapped in for `src/test`; at least N tests, all pass.

- [ ] **Step 1:** On the original, count the tests (`mvn test` with Java 8, from the m2 cache). Record N_orig and the H2 settings.
- [ ] **Step 2:** Produce a first draft with Opus 5.5 high in the sandbox (3 h, `--track r7-reference`). Finish it by hand to the API contract, then push the branch (owner approves first).
- [ ] **Step 3:** Copy the reference's `src/test` into the fixture. Write the failing tests:
  - `test_r7_hidden_tests_use_only_public_api`: every `de.terrestris.shogun` import in the fixture exists in the original, or is `QueryRestriction`;
  - `test_r7_own_tests_counts_disabled_as_missing`: a workspace with one `@Disabled` gives `own_tests == False`;
  - `test_r7_scorer_original_fails`: scoring the untouched snapshot gives `hibernate6 == False`;
  - `test_r7_baseline_passes` (slow): the reference passes all 8 checks.
- [ ] **Step 4:** Implement the scorer, forked from `r1b_scorer.py`: Maven with `-Dmaven.repo.local` pointing at a copy of the m2 cache, Java 17.
- [ ] **Step 5:** Run `pytest tests/test_r7_scorer.py -v` and `python -m scorers.r7_scorer --baseline`. Expected: pass, 8/8.

### Task 6: Screening runs (after the owner confirms GLM spend)

- [ ] **Step 1:** Ask the owner to confirm GLM-5.3 spend: about $2–18 per attempt × 2 cases.
- [ ] **Step 2:** Run:
  ```
  python agentic.py --pair haiku-5.5-cc-vs-glm-5.3-flash --role current --effort medium --case r6_bonobo_aspnetcore --track real-screen
  python agentic.py --pair haiku-5.5-cc-vs-glm-5.3-flash --role current --effort medium --case r7_shogun_hibernate6 --track real-screen
  python agentic.py --pair opus-5.5-cc-vs-glm-5.3 --role target --case r6_bonobo_aspnetcore --track real-screen
  python agentic.py --pair opus-5.5-cc-vs-glm-5.3 --role target --case r7_shogun_hibernate6 --track real-screen
  python leaderboard.py --track real-screen
  ```
- [ ] **Step 3:** Read every failure's scorer details and session log (the rule: never trust a failure until you've seen why). Classify each as model, harness or sandbox.
- [ ] **Step 4:** Report to the owner: per case, Haiku vs GLM, checks, time, cost. If Haiku fails and GLM passes on a case, propose 3 confirmation attempts each, with the cost.

### Task 7: Docs

- [ ] **Step 1:** In `docs/R1B_NEXT_PLAN.md`, rename the hypothetical fresh app to "r8" and link this work.
- [ ] **Step 2:** Add `docs/REAL_R6_R7.md`: sources, target contracts, checks, how to rebuild the caches, the screening results. Show the owner, then commit and open a PR only on approval.
