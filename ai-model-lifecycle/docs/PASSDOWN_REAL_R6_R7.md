# Passdown: looking for a real project Haiku 5.5 fails and GLM-5.3 passes (2026-11-11)

Written by Claude Code on the owner's home PC, for the owner continuing on the
office PC (or another Claude Code session). Read it top to bottom before
building or running anything.

**Status:** research is done and the owner has chosen two projects. The
implementation plan (`docs/REAL_R6_R7_PLAN.md`) is written but **not yet
reviewed or approved**, and nothing is built.

## The question

The owner asked: "Is there a real project that Haiku 5.5 cannot solve but
GLM-5.3 can?" The answer from existing results was **no**, so the owner chose
to build two new real-project tasks and screen both models on them.

## What the existing results show (checked 2026-11-11 on `main` @ `0dcc784`)

**Agentic (the AI codes, tests and fixes), the primary measure:**

| Board | Haiku 5.5 (low, medium, high) | GLM-5.3 (medium) |
|---|---|---|
| Main, 60 min: r1, r1b, r2, r3, r4, r5 | passes every attempt | passes every attempt |
| r1b in 10 min | fails (E2E) | fails, further behind (build fails, 4/8 checks) |
| r2 in 10 min | passes | passes |

Haiku is also 3–9× faster on the shared tasks (about 1–3.5 min vs GLM's ~9).

**Single-shot (one reply, no tools), the only candidate:**

| Task | Haiku 5.5 via Claude Code | Haiku 5.5 via OpenRouter | GLM-5.3 |
|---|---|---|---|
| r4 schema load + optimize | 0/6 (pairs `haiku-4.5-vs-5.5-cc`, `haiku-5.5-cc-vs-glm-5.3-flash`) | 2/3 (`haiku-4.5-vs-5.5`) | 3/3 (`opus-5.5-cc-vs-glm-5.3`) |
| r3 Oracle → Postgres | 2/6 | 2/3 | 2/3 |

Five of Haiku's six r4 failures are `index_scan, no_seq_scan_orders` (the
planner still scans `orders`). It is **not** a usable finding yet:
- R4's index-scan check is known to be flaky on borderline answers;
- Haiku passes 2/3 through OpenRouter, so it may come from the Claude Code route;
- with tools, Haiku passes r4 every time;
- the samples are small.

`verify_failures.py` on those six (no model cost, needs the Postgres
container) would settle it; this was offered but not run.

The owner then said: "I want real project".

## Research: candidate projects (verified via GitHub API, 2026-11-11)

Two research agents checked the repositories (license, activity, size, tests,
whether a migrated version is already public). Claude re-checked the key facts
for the two picks.

### .NET: .NET Framework MVC 5 → ASP.NET Core

| Project | Facts | Fit |
|---|---|---|
| **Bonobo Git Server** (chosen) | `jakubgarfield/Bonobo-Git-Server`, MIT, 1.8k stars, last commit `6277ecf` 2021-03-05. MVC 5.2.7 on .NET 4.6, EF6 on **SQLite** (System.Data.SQLite.EF6), Unity DI, OWIN cookie auth (+ Windows auth, WS-Federation, Active Directory via System.DirectoryServices), LibGit2Sharp 0.23 with Windows-only natives, git smart-HTTP by running `git`. ~154 .cs files in the web project, 39 views, 7 controllers. ~202 MSTest tests (some need IIS/CodedUI). **No public Core port** (searched). | Right size for 60 min; no SQL Server needed; grading can use real `git clone`/`push` plus browser tests |
| SocialGoal (MarlabsInc) | MIT, 2014. MVC 5, EF6 on SQL Server only, ASP.NET Identity 2, Autofac. 219 .cs, 94 views, 111 NUnit tests. No Core port. | Harder variant (Identity + DB provider switch) |
| MVCForum | MIT, archived 2021. 481 .cs, 44 controllers, Hangfire, plugins; few tests. | Probably too big: every model fails |
| eShopLegacyMVC | Microsoft sample, 23 .cs files. **Ported Core version in the same repo.** | Too small, answer public |
| Contoso University | Ported versions public (jbogard, Microsoft docs). | Answer public |

### Java: JUnit 4 → 5 and Hibernate 5 → 6

Hibernate 6 needs jakarta.persistence, and Spring 5.3's spring-orm only works
with Hibernate 5, so on a Spring project the task also forces Spring 6,
Jakarta and Java 17 (partly overlapping r1b). Only a project without Spring
keeps it to Hibernate and JUnit.

| Project | Facts | Fit |
|---|---|---|
| **shogun-core** (chosen) | `terrestris/shogun-core`, Apache-2.0, 33 stars, last commit `d1881aa` 2024-01-16. Java 8, Spring 5.3.26 (no Boot), Spring Security 5.5, Hibernate 5.4.24, JUnit 4.13 + PowerMock 2. 285 main files, 60 test files, **480 tests on in-memory H2**. Hibernate-6 breakage: legacy Criteria API (31 uses, and `Criterion` is in the public DAO API), `ResultTransformer`, custom `UserType`, Jadira `@Type`, hibernate-spatial dialect, PowerMock. No Hibernate 6 version anywhere (branch `migrate-spring` has a partial Spring 6 attempt, still Hibernate 5.6 and JUnit 4). | Hardest; likely to separate models |
| OpenRoberta server | Apache-2.0, active. Guice + Jersey + plain Hibernate 5.4, no Spring, HSQLDB. Repo 473 MB. | Medium; pure Hibernate + JUnit work |
| eionet.webq (EEA) | MPL-2.0. Spring 5.3, Hibernate 5.6, ~400 tests on H2; Tiles/JSP. Being modernised actively. | Hard, but mostly Spring web-layer churn |

Rejected: spring-framework-petclinic (already Hibernate 7), dddsample (Boot),
cargotracker (Arquillian only), geostore (non-Central fork, already Hibernate 7),
openmrs and Kitodo (too large, already migrated), eHour (no license).

**shogun-core's three non-Central libraries** (404 on Maven Central, checked):
`org.geotools:gt-main:22.2`, `org.deegree:deegree-core-commons:3.4.11`,
`org.jboss.elasticsearch:structured-content-tools:1.3.11`. All three are served
by `https://nexus.terrestris.de/repository/public/` (HTTP 200, checked), which
the project's own pom lists. The plan pre-loads them into a Maven cache rather
than opening that host in the sandbox allowlist.

## Decisions taken (owner, 2026-11-11)

1. Build **two** new real tasks: **Bonobo Git Server** (.NET) and **shogun-core** (Java).
2. Research first, then decide (done).
3. Target **.NET 10**, not .NET 8: .NET 8's support ended on 2026-11-10; .NET 10 is the current LTS.

## Sandbox facts found

* The agent image (`docker/agent/Dockerfile`) has Java 17, Java 8, Maven, Node 20, Chromium and PostgreSQL 17, **no .NET SDK**.
* The allowlist (`docker/egress/allowlist.txt`) has Maven Central and npm, **no NuGet**; r6 needs `^api\.nuget\.org$`.
* The home Mac has the .NET 9 and 10 SDKs; Docker was not running when this was written.

## Next steps (in `docs/REAL_R6_R7_PLAN.md`)

1. **Owner reviews the plan** and picks how to run it (recommended: one Claude session builds it, then one fresh reviewer checks the whole branch).
2. Then, by the plan's tasks: sources and sandbox prerequisites → register both cases → r6 reference + scorer → r7 reference + scorer → screening runs → docs.

**Needs the owner's approval on the way:**
- forking both repos to `abralock/`;
- every commit or push (review first);
- GLM-5.3 spend before screening: about $2–18 per attempt, 2 attempts.

Expected effort: about 3–4 working days, plus about 6 h of Opus subscription
for drafting the two reference migrations (3 h each, never counted on a board).

**One caution to keep:** a single Haiku-fails/GLM-passes result can be luck;
confirm any difference with 3 attempts each before reporting it.

## Other open items from this session

| Item | State |
|---|---|
| PR #58 (`docs/r1b-next-plan`): r1b successor plan + the test-visibility rule | open, pushed |
| Deck https://claude.ai/artifact/NDs6WhZJx789q2iVzfDrVU | version 64, private. New this session: slide 46, a backup on r1b's tests before and after 2 Nov plus the 60/10-minute run modes; r2 slides renumbered to 47–51 |
| Slide 39 footer | offered (not answered): say why Opus high has no ≈ (it finished by itself, so Claude Code reported its cost; the stopped sessions are priced from their session record) |
| Slide 39 costs | verified: all 9 Claude rows recomputed from the session records at PR #60's prices match the slide |
| Research downloads | only on the home PC (scratchpad), not committed; everything needed is in this file |
