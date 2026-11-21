"""agentic.py — agentic runs: the model migrates the project the way a developer
would, with tools, until it delivers.

A single-shot run (runner.py) hands the model the sources as text and takes one
reply; nothing is compiled or tested. Here the model works inside a copy of the
case's project with a coding agent: it edits files, builds, runs the tests,
reads the errors and fixes them, until the case's goal is met (`/goal`) or the
time limit is reached. Claude models run in Claude Code; open-weight models on
OpenCode Go run in opencode (OpencodeBackend), with the same goal, workspace,
time limit and scoring.

Every attempt runs in a throwaway Docker container (docker/agent/Dockerfile:
Java 17 + Maven, Node 20 + Chromium, PostgreSQL 17), so model-run commands never
touch the host; the workspace is the only thing mounted. The container logs in
with CLAUDE_CODE_OAUTH_TOKEN (`claude setup-token`, the claude.ai subscription),
passed by name from the environment so the token never appears on a command line.
No sub-agents (the Agent tool is disallowed), no web tools, and no MCP servers or
user settings.

The sandbox has no internet access of its own: it sits on an internal Docker
network, and the only way out is an allowlist proxy (docker/egress/: the model
APIs and the package registries a build needs). Each attempt records the hosts
it reached and the ones the proxy refused. Before this (runs up to 2026-11-01)
the sandbox was open, and on r1b two agents downloaded JHipster's own published
Boot 3 version of the app, i.e. the answer.

When the agent stops, the files it delivered (each case's `deliverables`) are
turned into a FILE/DELETE answer and scored by the case's own scorer — the same
acceptance check as single-shot, including hidden tests the agent never sees.
Answer keys are never copied into the workspace; hidden tests neither, except
r1b's, which its prompt promises as the project's (already migrated) test
sources and which the scorer swaps in again from its own copy.

Records go to runs/<pair>/agentic/<run_id>/ (outside the single-shot runs, so
the scorecard never mixes them in) with a REPORT.md.

Usage:
    python agentic.py --pair sonnet-5.5-cc-vs-deepseek-v4-pro --role current \\
        --case r1b_jhipster_boot3 [--repeats 1] [--time-limit 3600] [--effort medium]
"""

from __future__ import annotations

import argparse
import base64
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import common
import pricing
from cases import sources
from common import case_dir, load_config, load_env, new_run_id

IMAGE = os.environ.get("GATE1_AGENT_IMAGE", "gate1-agent:latest")
TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"
# opencode (open-weight models on OpenCode Go): the repo keeps the Go key as
# OPENCODE_GO_API_KEY; opencode reads it as OPENCODE_API_KEY inside the sandbox.
OPENCODE_KEY_SOURCE = "OPENCODE_GO_API_KEY"
OPENCODE_KEY_ENV = "OPENCODE_API_KEY"
OPENCODE_PROVIDER = "opencode-go"
OPENCODE_VERSION_LABEL = "gate1.opencode.version"
DEFAULT_TIME_LIMIT_S = 3600
# Build caches shared across attempts (dependencies only; never model output).
M2_VOLUME = "gate1_agent_m2"
NPM_VOLUME = "gate1_agent_npm"
# Network: the sandbox's only way out is the allowlist proxy (docker/egress/).
NETWORK_ALLOWLIST = "allowlist"         # internal network + allowlist proxy (default)
NETWORK_OPEN = "open"                   # Docker's default bridge: unrestricted (debugging only)
SANDBOX_NETWORK = "gate1-sandbox"       # `docker network create --internal`: no route out
EGRESS_NAME = "gate1-egress"
EGRESS_IMAGE = os.environ.get("GATE1_EGRESS_IMAGE", "gate1-egress:latest")
EGRESS_PORT = 8888
EGRESS_URL = f"http://{EGRESS_NAME}:{EGRESS_PORT}"
NO_PROXY = "localhost,127.0.0.1,::1"
# Probed by check_egress() before a batch: one must pass, the other be refused.
EGRESS_PROBE_ALLOWED = "https://repo.maven.apache.org/maven2/"
EGRESS_PROBE_BLOCKED = "https://github.com/"
# Claude Code's own web tools would bypass nothing (the proxy refuses them too),
# but they are off so the sandbox never even tries.
CLAUDE_DISALLOWED_TOOLS = ("Agent", "WebFetch", "WebSearch")

SYSTEM_NOTE = (
    "You are a senior software engineer doing a real migration. The project is in "
    "the current directory (/work). Work the way you would on a real project: read "
    "the code, make the changes, build, run the tests, read the errors and fix them, "
    "until the goal is met. Do not delete, skip or disable tests to make them pass. "
    "There is no human to ask; make reasonable decisions and keep going.\n\n"
    # Said, not only enforced: the allowlist proxy blocks websites, but npm must
    # stay reachable for builds, and on r1b GLM-5.3 read generator-jhipster's
    # templates from npm when GitHub was refused (2026-11-02). Agents had not
    # been told answer sources were off-limits; now they are (owner's request).
    "Internet access: the sandbox reaches only the model API and the package "
    "registries a build needs (Maven Central, npm); every other site is blocked. Use "
    "the registries only to install the project's dependencies. Do not look up, "
    "download or copy a published solution, a newer version of this project, or the "
    "generator or templates it was made from, from any source, npm included. The "
    "result must be your own migration of the code in /work."
)

# A separate board's runs (leaderboard.py --track): a short name, used in a
# file name (runs/LEADERBOARD_<track>.md).
TRACK_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


def time_note(time_limit_s: int) -> str:
    """Told to the agent only with --tell-time-limit (e.g. the r1b-10min
    track): the main board's prompt never mentions the limit."""
    return (f"Time limit: you have {time_limit_s / 60:g} minutes. The session is then "
            "stopped, and whatever is in /work at that moment is scored as it stands.")


# --------------------------------------------------------------------------- #
# Cases                                                                        #
# --------------------------------------------------------------------------- #
@dataclass
class AgenticCase:
    """How one case is set up for an agent and harvested for scoring."""
    goal: str                               # the `/goal` condition
    deliverables: list[str]                 # workspace globs scored (fnmatch, ** ok)
    setup: Callable[[Path], None]           # fills the empty workspace
    task_note: str                          # replaces the prompt's output-format section
    postgres: bool = False                  # start PostgreSQL in the sandbox
    exclude: list[str] = field(default_factory=list)   # globs never harvested
    image: str | None = None                # sandbox image (None: IMAGE)
    snapshots_s: list[int] = field(default_factory=list)  # harvest + score the work at these times


def _copy(src: Path, dest: Path) -> None:
    """Copy a file or tree; on macOS a copy-on-write clone (cheap for node_modules)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        rc = subprocess.run(["cp", "-cR", str(src), str(dest)], capture_output=True).returncode
        if rc == 0:
            return
    if src.is_dir():
        shutil.copytree(src, dest, symlinks=True, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dest)


def _setup_r1(ws: Path) -> None:
    cd = case_dir("r1_springboot2to3")
    for name in ("pom.xml", "src"):
        _copy(cd / name, ws / name)


def _setup_r1b(ws: Path) -> None:
    # The full app at the pinned commit (frontend + Cypress included, so the
    # agent can run the e2e suite), from the cache setup_e2e.sh builds.
    from scorers.base import cache_dir
    from scorers.r1b_scorer import HIDDEN_TESTS
    frontend = cache_dir() / "r1b_jhipster_boot3" / "frontend"
    if not (frontend / "node_modules" / ".bin" / "cypress").exists():
        raise RuntimeError("r1b needs the e2e cache: run cases/r1b_jhipster_boot3/setup_e2e.sh")
    for entry in frontend.iterdir():
        if entry.name != "target":
            _copy(entry, ws / entry.name)
    # The prompt says src/test is "maintained separately and already migrated
    # to Boot 3", so the agent gets exactly that: the suite the scorer runs.
    # Until 2026-11-02 it got the original Boot 2 tests instead, and every
    # agent had to migrate them itself just to check its work (all ten r1b
    # sessions did). src/test is not a deliverable, and the scorer swaps in its
    # own copy, so edits there still change nothing.
    # Only the parts the suite holds (java/, resources/) are replaced: the
    # Cypress suite in src/test/javascript needs no migration and stays. On
    # 2026-11-02 the whole of src/test was replaced, which deleted it; both r1b
    # re-runs restored it with `git checkout`.
    for part in HIDDEN_TESTS.iterdir():
        dest = ws / "src" / "test" / part.name
        if dest.is_dir() and not dest.is_symlink():
            shutil.rmtree(dest)
        elif dest.exists() or dest.is_symlink():
            dest.unlink()
        _copy(part, dest)


_R2_BACKEND = """#!/bin/sh
# Start the original GWT app (its REST API at /api) on http://localhost:8888,
# serving the current Angular build (dist/carstore/browser) at /ng/.
# Each start is a fresh copy, so the datastore is re-seeded.
set -e
rm -rf /tmp/war && cp -R /work/backend/carstore-war /tmp/war
[ -d /work/dist/carstore/browser ] && cp -R /work/dist/carstore/browser /tmp/war/ng
export JAVA_HOME=/opt/java8 PATH=/opt/java8/bin:$PATH
exec sh /work/backend/gae-sdk/appengine-java-sdk-1.9.17/bin/dev_appserver.sh --address=0.0.0.0 --port=8888 /tmp/war
"""


def _setup_r2(ws: Path) -> None:
    from scorers.base import cache_dir
    cd = case_dir("r2_gwt_to_angular")
    cache = cache_dir() / "r2_gwt_to_angular"
    if not (cache / "deps" / "node_modules").is_dir() or not (cache / "carstore-war").is_dir():
        raise RuntimeError("r2 needs its cache: run cases/r2_gwt_to_angular/setup.sh")
    for entry in (cd / "workspace").iterdir():
        _copy(entry, ws / entry.name)
    _copy(cd / "gwt", ws / "gwt")
    _copy(cd / "e2e", ws / "e2e")
    _copy(cache / "deps" / "node_modules", ws / "node_modules")
    _copy(cache / "carstore-war", ws / "backend" / "carstore-war")
    _copy(cache / "gae-sdk", ws / "backend" / "gae-sdk")
    (ws / "backend" / "run.sh").write_text(_R2_BACKEND, encoding="utf-8")


def _setup_r3(ws: Path) -> None:
    # The Oracle sources, the seed data and the Oracle results on that data
    # (what a real migration compares against). Never golden_postgres.sql.
    cd = case_dir("r3_oracle_to_postgres")
    _copy(cd / "procedures", ws / "oracle")
    _copy(cd / "seed.sql", ws / "seed.sql")
    for name in ("golden_output.csv", "golden_output_monthly.csv"):
        _copy(cd / name, ws / "expected" / name.replace("golden_", ""))


def _setup_r4(ws: Path) -> None:
    cd = case_dir("r4_schema_load_optimize")
    for name in ("schema.sql", "target_query.sql"):
        _copy(cd / name, ws / name)


def _setup_r5(ws: Path) -> None:
    cd = case_dir("r5_etl_dashboard")
    for name in ("etl_spec.md", "dashboard_schema.sql"):
        _copy(cd / name, ws / name)
    # sample source data: R4's schema and its deterministic seeder
    r4 = case_dir("r4_schema_load_optimize")
    _copy(r4 / "schema.sql", ws / "source" / "schema.sql")
    _copy(r4 / "seed.py", ws / "source" / "seed.py")


R7_CASE = "r7_shogun_hibernate6"


def r7_m2_cache() -> Path:
    """The Maven repository of the original r7 build (cases/r7_shogun_hibernate6/setup.sh).

    shogun-core resolves through terrestris's own Nexus (its pom lists it before
    Central), which the sandbox does not reach; three of its libraries are only
    there (gt-main 22.2, deegree-core-commons 3.4.11, structured-content-tools
    1.3.11). The original build's whole repository is seeded into the sandbox's
    Maven volume, so those resolve locally and anything new comes from Central."""
    from scorers.base import cache_dir
    return cache_dir() / R7_CASE / "m2"


def _seed_m2(m2: Path, label: str = "r7") -> None:
    # copy, never overwrite (-n): the volume is shared with other cases' runs;
    # as the agent user, so the sandbox can still write its own artifacts there
    r = subprocess.run(["docker", "run", "--rm", "--user", "agent", "--entrypoint", "sh",
                        "-v", f"{M2_VOLUME}:/home/agent/.m2", "-v", f"{m2}:/seed:ro", IMAGE,
                        "-c", "mkdir -p /home/agent/.m2/repository && "
                              "cp -Rn /seed/. /home/agent/.m2/repository/"],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{label}: seeding the sandbox Maven volume failed: {r.stderr.strip()[:300]}")


def _setup_r7(ws: Path) -> None:
    m2 = r7_m2_cache()
    if not (m2 / "org" / "geotools" / "gt-main" / "22.2").is_dir():
        raise RuntimeError("r7 needs its Maven cache: run cases/r7_shogun_hibernate6/setup.sh")
    # the whole project at the pinned commit, its own JUnit 4 tests included:
    # migrating them is part of the task (the grading tests stay with the scorer)
    for entry in (case_dir(R7_CASE) / "project").iterdir():
        _copy(entry, ws / entry.name)
    _seed_m2(m2)


R8_CASE = "r8_shogun_rust"
R8_IMAGE = os.environ.get("GATE1_AGENT_RUST_IMAGE", "gate1-agent-rust:1.100.0")


def _setup_r8(ws: Path) -> None:
    """r8: the original shogun-core (r7's pinned snapshot) and the reference
    webapp built on it, read-only references the agent may run; the pinned
    schema; and the Maven repository the reference app runs from offline
    (cases/r8_shogun_rust/setup.sh). The agent writes rust/."""
    from scorers.base import cache_dir
    m2 = cache_dir() / R8_CASE / "m2"
    if not (m2.parent / "ready").is_file():
        raise RuntimeError("r8 needs its Maven cache: run cases/r8_shogun_rust/setup.sh")
    if subprocess.run(["docker", "image", "inspect", R8_IMAGE], capture_output=True).returncode:
        raise RuntimeError(f"r8 needs the Rust sandbox image: docker build -t {R8_IMAGE} docker/agent-rust")
    sources.ensure(R7_CASE)
    for entry in (case_dir(R7_CASE) / "project").iterdir():
        _copy(entry, ws / "reference" / "shogun-core" / entry.name)
    _copy(case_dir(R8_CASE) / "reference-app", ws / "reference" / "reference-app")
    _copy(case_dir(R8_CASE) / "schema.sql", ws / "schema.sql")
    _seed_m2(m2, "r8")


R8_SNAPSHOTS_S = [3600, 7200, 14400]      # r8 runs up to 8 h: progress at 1, 2 and 4 h

_PG_NOTE = ("A PostgreSQL 17 server is running in this sandbox: `psql` connects to "
            "database aidb as user ai (PGHOST/PGUSER/PGPASSWORD/PGDATABASE are set).")

CASES: dict[str, AgenticCase] = {
    "r1_springboot2to3": AgenticCase(
        goal=("pom.xml uses Spring Boot 3.x and Java 17; nothing under src uses the "
              "javax.persistence, javax.validation, javax.annotation or javax.servlet "
              "packages; no spring.factories file is left; and `mvn -B test` passes with "
              "every existing test migrated to JUnit 5 and actually run (none deleted, "
              "skipped or disabled)."),
        deliverables=["pom.xml", "src/**"],
        setup=_setup_r1,
        task_note="Edit the project in place. Maven and Java 17 are installed.",
    ),
    "r1b_jhipster_boot3": AgenticCase(
        goal=("pom.xml uses Spring Boot 3.x and Java 17; no javax.persistence, "
              "javax.validation or javax.servlet imports remain in src/main; "
              "`./mvnw -P-webapp verify` passes with at least 52 unit tests and 140 "
              "integration tests run and none skipped or deleted; and with the app "
              "running (`./mvnw`), `npm run e2e:headless` passes all 54 Cypress tests."),
        deliverables=["pom.xml", "src/main/java/**", "src/main/resources/**"],
        exclude=["src/main/webapp/**"],
        setup=_setup_r1b,
        task_note=("The whole application is checked out here (backend and Angular "
                   "frontend, with node_modules installed). Change the backend only; "
                   "leave the frontend under src/main/webapp unchanged. Java 17, Maven "
                   "(./mvnw), Node and Chromium are installed (CHROME_BIN is set; Cypress "
                   "can use `--browser chromium` or electron). Off-limits: "
                   "jhipster-sample-app in any version other than the one here, and "
                   "generator-jhipster (its templates describe the answer)."),
    ),
    "r2_gwt_to_angular": AgenticCase(
        goal=("`npx ng build` succeeds; and served at http://localhost:8888/ng/ by "
              "`sh backend/run.sh`, the Angular app implements the Manufacturers, Ratings and "
              "Reports screens, the header menubar and the success/error messages so that "
              "every scenario in e2e/ (Manufacturers, Ratings and Reports features) works "
              "against the real REST API, with the element ids, table layout, hash routing "
              "and delete confirmation the task's acceptance criteria require."),
        # everything under src/: the scorer restores the fixed files (main.ts,
        # index.html) itself, and an app may keep assets beside src/app (Opus
        # put the original PNGs in src/images, used from styles.css)
        deliverables=["src/**"],
        setup=_setup_r2,
        task_note=("The Angular workspace (the task's `workspace/`) is the current "
                   "directory, with node_modules installed; `gwt/` and `e2e/` are here too. "
                   "Write the app under src/app/: the fixed src/main.ts bootstraps "
                   "AppComponent from src/app/app.component.ts and appConfig from "
                   "src/app/app.config.ts, so both must exist. package.json, angular.json, "
                   "tsconfig*.json, src/main.ts and src/index.html are fixed (changes are "
                   "discarded); you may add global CSS to src/styles.css. `sh backend/run.sh` "
                   "starts the original GWT app with its REST API on http://localhost:8888 "
                   "and serves your latest `npx ng build` at http://localhost:8888/ng/. "
                   "Chromium is installed (CHROME_BIN) for browser checks."),
    ),
    "r3_oracle_to_postgres": AgenticCase(
        goal=("postgres/schema.sql and postgres/procedures.sql exist; applied in that order "
              "to an empty database and loaded with seed.sql, sp_customer_tier() returns "
              "exactly the rows in expected/output.csv and sp_monthly_report('2026-09') "
              "exactly the rows in expected/output_monthly.csv; and neither file uses DUAL, "
              "NVL(, ROWNUM, (+), VARCHAR2 or sysdate."),
        # in the order they are applied
        deliverables=["postgres/schema.sql", "postgres/procedures.sql", "postgres/**"],
        setup=_setup_r3,
        postgres=True,
        task_note=("The Oracle sources are in oracle/. Write the PostgreSQL version as "
                   "postgres/schema.sql and postgres/procedures.sql. seed.sql loads the "
                   "test data, and expected/ holds the result sets the Oracle procedures "
                   "return on that data. " + _PG_NOTE),
    ),
    "r4_schema_load_optimize": AgenticCase(
        goal=("solution.sql, run top to bottom with `psql -v ON_ERROR_STOP=1` on a fresh "
              "empty schema, creates the four tables, loads about 100,000 orders with "
              "their order_items, and creates the index(es); after ANALYZE, EXPLAIN "
              "ANALYZE of target_query.sql uses an index or bitmap index scan on orders, "
              "no sequential scan on orders, and runs in under 1 second."),
        deliverables=["solution.sql"],
        setup=_setup_r4,
        postgres=True,
        task_note="Write the deliverable as solution.sql. " + _PG_NOTE,
    ),
    "r5_etl_dashboard": AgenticCase(
        goal=("etl.sql runs top to bottom with `psql -v ON_ERROR_STOP=1` on source tables "
              "built from source/schema.sql and source/seed.py plus dashboard_schema.sql; "
              "it reconciles exactly as etl_spec.md defines (source order count minus "
              "loaded order count is 0, recorded in etl_run_log); running it twice gives "
              "the same dashboard row counts; both dashboard tables are non-empty; and it "
              "handles the cases etl_spec.md §5 describes (multi-category orders and "
              "completed orders without lines)."),
        deliverables=["etl.sql"],
        setup=_setup_r5,
        postgres=True,
        task_note=("Write the deliverable as etl.sql. Sample source data: source/schema.sql "
                   "creates the tables and `python3 source/seed.py --help` shows how to "
                   "generate rows. " + _PG_NOTE),
    ),
    "r7_shogun_hibernate6": AgenticCase(
        goal=("In shogun-core-main and the parent pom.xml: Hibernate ORM 6.x with "
              "jakarta.persistence, Spring Framework 6.x and Spring Security 6.x, Java 17; "
              "no javax.persistence, javax.servlet, javax.transaction, javax.annotation.Resource "
              "or javax.mail imports remain; the project's tests use JUnit 5 only (no JUnit 4, "
              "no PowerMock); the legacy Criteria API is replaced by the prompt's QueryRestriction "
              "and SortOrder types with every other public signature unchanged; and "
              "`mvn -B -pl shogun-core-main -am verify` passes with at least 776 tests run "
              "and none failed, skipped or disabled."),
        deliverables=["pom.xml", "shogun-core-main/pom.xml", "shogun-core-main/src/**"],
        exclude=["**/target/**"],
        setup=_setup_r7,
        task_note=("The whole project is checked out here: the parent pom.xml, "
                   "shogun-core-main (the module to upgrade) and shogun-core-webapp-archetype "
                   "(out of scope: leave it unchanged). Java 17 and Maven are installed "
                   "(`mvn`; the project has no wrapper), and the original build's "
                   "dependencies are already in the local Maven repository, including "
                   "three that are not on Maven Central (gt-main, deegree-core-commons, "
                   "structured-content-tools); terrestris's own Maven repository is not "
                   "reachable from here, Maven Central is. Java 8 is at /opt/java8 if you "
                   "want to run the original build. Off-limits: shogun-core in any version "
                   "other than the one here (including its migrate-spring branch) and "
                   "terrestris/shogun, its successor."),
    ),
    "r8_shogun_rust": AgenticCase(
        goal=("rust/ is a Cargo project whose `cargo build --release --locked` and `cargo test "
              "--release --locked` pass; started with DATABASE_URL (a PostgreSQL database with "
              "schema.sql loaded, unchanged) and PORT, its binary serves /rest/users, /rest/groups, "
              "/rest/roles, /rest/layers, /rest/layerdatasources and /rest/layerappearances with "
              "the same HTTP Basic login, permissions, status codes, JSON, field restriction "
              "(output:only), filters and database writes as the original Java reference app in "
              "reference/reference-app, without any Java involved."),
        deliverables=["rust/**"],
        exclude=["rust/target/**", "**/target/**"],
        setup=_setup_r8,
        postgres=True,
        image=R8_IMAGE,
        snapshots_s=R8_SNAPSHOTS_S,
        task_note=("Write the Rust service in rust/ (create it). Rust 1.100.0 (cargo, rustc) is "
                   "installed, and crates.io is reachable; nothing else on the internet is. "
                   "reference/shogun-core/ is the original library (the module shogun-core-main) "
                   "and reference/reference-app/ the webapp built on it (see its R8_PATCHES.md); "
                   "schema.sql, in the current directory, is the database schema. You may run the "
                   "original to compare: `createdb ref`, then in reference/reference-app "
                   "`JAVA_HOME=/opt/java8 R8_JDBC_URL=jdbc:postgresql://localhost:5432/ref "
                   "mvn -q -DskipTests jetty:run` (a minute or two to start; port 8081; its "
                   "dependencies are in the local Maven repository, a few POMs come from Maven "
                   "Central on the first start). On every start it "
                   "recreates its schema in that database and loads demo data (users admin/shogun "
                   "and user/shogun). Give your own service a separate database, for example "
                   "`createdb port && psql -d port -f schema.sql`. " + _PG_NOTE),
    ),
}


def task_prompt(case_id: str) -> str:
    """The case's prompt.md with its output-format section replaced by
    workspace instructions (the agent edits files instead of replying)."""
    text = (case_dir(case_id) / "prompt.md").read_text(encoding="utf-8")
    lines, out, skipping = text.splitlines(), [], False
    for line in lines:
        heading = line.startswith("## ")
        if heading:
            low = line.lower()
            skipping = "output" in low or "deliverable" in low
            if skipping:
                out += ["## Workspace", "", CASES[case_id].task_note, ""]
                continue
        if not skipping:
            out.append(line)
    if not any(line == "## Workspace" for line in out):
        out += ["", "## Workspace", "", CASES[case_id].task_note]
    return "\n".join(out).strip() + "\n"


# --------------------------------------------------------------------------- #
# Harvest: the delivered files as an answer the case's scorer reads            #
# --------------------------------------------------------------------------- #
def _match(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel, p) or (p.endswith("/**") and rel.startswith(p[:-2]))
               for p in patterns)


def snapshot(ws: Path, spec: AgenticCase) -> dict[str, bytes]:
    """{relative path: content} of every deliverable file in the workspace."""
    out = {}
    for f in ws.rglob("*"):
        if f.is_file() and not f.is_symlink():
            rel = f.relative_to(ws).as_posix()
            if _match(rel, spec.deliverables) and not _match(rel, spec.exclude):
                out[rel] = f.read_bytes()
    return out


def answer_from(before: dict[str, bytes], after: dict[str, bytes],
                order: list[str] | None = None) -> str:
    """FILE blocks for every new or changed deliverable, DELETE for removed ones.

    Files come in `order` (a case's deliverable patterns, first match wins),
    then by path: SQL scorers run the files in answer order, so r3's schema
    must come before the procedures that use its row types (alphabetical order
    put procedures.sql first and failed two correct answers, 2026-10-31)."""
    def rank(rel: str) -> tuple[int, str]:
        hits = [i for i, p in enumerate(order or []) if _match(rel, [p])]
        return (hits[0] if hits else len(order or []), rel)

    parts = []
    for rel in sorted(set(before) - set(after)):
        parts.append(f"### DELETE: {rel}\n")
    for rel in sorted(after, key=rank):
        if before.get(rel) == after[rel]:
            continue
        try:
            body = after[rel].decode("utf-8")
        except UnicodeDecodeError:
            # images and other binaries travel base64-encoded (scorers.base
            # parse_binaries); dropping them failed a correct r2 build whose
            # CSS used the original app's PNGs (2026-10-31)
            data = base64.encodebytes(after[rel]).decode("ascii").rstrip("\n")
            parts.append(f"### BINARY: {rel}\n```base64\n{data}\n```\n")
            continue
        # scorers.base.parse_files ends a block at any fence line, so a
        # deliverable that itself contains one (rare: code, SQL and config
        # files don't) would arrive cut short
        parts.append(f"### FILE: {rel}\n```\n{body.rstrip(chr(10))}\n```\n")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# One attempt                                                                  #
# --------------------------------------------------------------------------- #
@dataclass
class AgenticResult:
    pair_id: str
    case_id: str
    model_slug: str
    model_name: str
    role: str
    rep: int
    run_id: str
    mode: str = "agentic"
    effort_override: str | None = None
    reasoning_requested: dict[str, Any] | None = None
    time_limit_s: int = DEFAULT_TIME_LIMIT_S
    time_limit_told: bool = False       # the prompt stated the limit (--tell-time-limit)
    track: str | None = None            # a separate board (--track); None: the main board
    goal: str = ""
    provider: str = "claude-code"       # the route: claude-code | opencode-go
    agent: str = "claude-code"          # the agent CLI: claude-code | opencode
    agent_version: str | None = None
    goal_mode: str | None = None        # how the goal keeps the agent going (native /goal)
    ok: bool = False                    # the agent ran and finished (not an infra error)
    error: str | None = None
    timed_out: bool = False
    latency_s: float = 0.0              # wall time of the agent session
    num_turns: int | None = None
    tool_calls: int = 0
    duration_api_ms: int | None = None  # model time: the session's time in API requests
    tool_time_s: float | None = None    # tools running (builds, tests), overlaps merged
    thinking_time_s: float | None = None  # the model's reported thinking time
    input_tokens: int = 0
    output_tokens: int = 0
    output_tokens_known: bool = True    # False: a Claude session stopped at the limit
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_estimate_usd: float | None = None
    cost_reported_usd: float | None = None   # opencode's own per-step cost sum
    cost_from_prices_usd: float | None = None  # a stopped Claude session, priced from its record
    reasoning_tokens: int = 0                # opencode: reported separately (also in output_tokens)
    model_time_source: str | None = None     # "reported" (Claude Code) | "derived" (opencode)
    agent_error: str | None = None           # an agent error that ended the session (scored)
    network: str = NETWORK_ALLOWLIST         # allowlist | open (see NETWORK_*)
    image: str | None = None                 # the sandbox image the attempt ran in
    snapshots: list[dict] = field(default_factory=list)   # {at_s, passed, score, checks, reason}
    egress_hosts: list[str] = field(default_factory=list)    # hosts the proxy let through
    blocked_hosts: list[str] = field(default_factory=list)   # hosts the proxy refused
    final_message: str = ""
    files_changed: int = 0
    output_text: str = ""               # the harvested answer the scorer reads
    passed: bool | None = None
    reason: str = ""
    checks: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0


def agentic_dir(pair_id: str, run_id: str) -> Path:
    return Path(common.RUNS_DIR) / pair_id / "agentic" / run_id


def record_path(pair_id: str, run_id: str, slug: str, case_id: str, rep: int) -> Path:
    suffix = f".r{rep}" if rep else ""
    return agentic_dir(pair_id, run_id) / f"{slug.replace('/', '__')}.{case_id}.{run_id}{suffix}.json"


def write_control(control: Path, goal: str, system: str) -> None:
    """The goal and task go to files the sandbox reads, never onto a command
    line: there they show in `ps`, and an agent that stops its own servers by
    pattern (`kill` every process mentioning "java") killed its own session
    on r2 (2026-10-31)."""
    control.mkdir(parents=True, exist_ok=True)
    (control / "prompt.txt").write_text(f"/goal {goal}", encoding="utf-8")
    (control / "system.md").write_text(system, encoding="utf-8")


def _network_args(network: str) -> list[str]:
    """The sandbox's network: on the allowlist (the default) it joins the
    internal network, whose only way out is the egress proxy, and every client
    is pointed at that proxy (curl, git, npm, Node, Claude Code, opencode read
    the *_PROXY variables; the entrypoint writes Maven's settings.xml from
    GATE1_PROXY_*). Loopback stays direct: builds and tests talk to their own
    servers on localhost."""
    if network == NETWORK_OPEN:
        return []
    if network != NETWORK_ALLOWLIST:
        raise ValueError(f"unknown sandbox network {network!r}")
    args = ["--network", SANDBOX_NETWORK]
    for k in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"):
        args += ["-e", f"{k}={EGRESS_URL}"]
    for k in ("NO_PROXY", "no_proxy"):
        args += ["-e", f"{k}={NO_PROXY}"]
    return args + ["-e", f"GATE1_PROXY_HOST={EGRESS_NAME}", "-e", f"GATE1_PROXY_PORT={EGRESS_PORT}"]


def _docker_prefix(name: str, ws: Path, control: Path, postgres: bool,
                   env_args: list[str], network: str = NETWORK_ALLOWLIST,
                   image: str = IMAGE) -> list[str]:
    """`docker run` up to the image: the workspace and the read-only control
    dir are the first two mounts, then the dependency caches. `env_args` pass
    secrets by name only (`-e NAME`), so no value reaches a command line."""
    return ["docker", "run", "--rm", "--name", name,
            "-v", f"{ws}:/work", "-v", f"{control}:/gate1:ro",
            "-v", f"{M2_VOLUME}:/home/agent/.m2", "-v", f"{NPM_VOLUME}:/home/agent/.npm",
            *env_args,
            *_network_args(network),
            "-e", f"GATE1_POSTGRES={1 if postgres else 0}",
            "--shm-size", "1g", image]


def docker_command(name: str, ws: Path, control: Path, model: str,
                   effort: str | None, postgres: bool,
                   network: str = NETWORK_ALLOWLIST, image: str = IMAGE) -> list[str]:
    cmd = _docker_prefix(name, ws, control, postgres,
                         ["-e", TOKEN_ENV,     # by name: the value comes from our env
                          # no telemetry or update checks: the proxy would refuse them
                          "-e", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1"],
                         network, image) + [
           # the prompt (`/goal ...`) arrives on stdin, the task in a file
           "sh", "-c", 'exec claude -p "$@" < /gate1/prompt.txt', "claude",
           "--model", model,
           "--append-system-prompt-file", "/gate1/system.md",
           "--dangerously-skip-permissions",
           "--disallowedTools", *CLAUDE_DISALLOWED_TOOLS,
           "--setting-sources", "", "--strict-mcp-config",
           # the session is saved (the container is removed after each attempt
           # anyway) so that, when the time limit stops it, its record can be
           # read for the final output token counts (ClaudeCodeBackend.save_session)
           "--output-format", "stream-json", "--verbose"]
    if effort:
        cmd += ["--effort", effort]
    return cmd


def _container_env() -> dict[str, str]:
    """Only what docker needs plus the subscription token: never an API key
    (that would bill the API instead of the subscription)."""
    keep = ("PATH", "HOME", "DOCKER_HOST", "DOCKER_CONFIG", "DOCKER_CONTEXT", TOKEN_ENV)
    return {k: v for k, v in os.environ.items() if k in keep}


def _ts(value: Any) -> float | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _content_blocks(ev: dict) -> list:
    """The content blocks of a stream event's `message`, or [] when there are
    none. Some events (e.g. system/permission_denied) carry `message` as plain
    text, not an object."""
    message = ev.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return content if isinstance(content, list) else []


def _merge_spans(spans: list[tuple[float, float]]) -> float | None:
    """Total seconds covered by (start, end) spans, overlaps counted once;
    None when there are no spans."""
    if not spans:
        return None
    total, end = 0.0, float("-inf")
    for a, b in sorted(spans):
        if b > end:
            total += b - max(a, end)
            end = b
    return total


def stream_timing(lines: list[str]) -> tuple[float | None, float | None]:
    """(tool time, thinking time) in seconds from a Claude Code session stream.

    Tool time runs from each tool_use message to its tool_result, by the
    events' own timestamps, with overlapping (parallel) calls merged so no
    second counts twice. Thinking time sums the model's reported
    thinking_duration_ms. None when the stream carries no such data: a
    missing measurement is never zero (docs/METRICS_PLAN.md)."""
    started: dict[str, float] = {}
    spans: list[tuple[float, float]] = []
    thinking_ms, saw_thinking = 0.0, False
    for line in lines:
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        if isinstance(ev.get("thinking_duration_ms"), (int, float)):
            thinking_ms += float(ev["thinking_duration_ms"])
            saw_thinking = True
        at = _ts(ev.get("timestamp"))
        for block in _content_blocks(ev):
            if not isinstance(block, dict) or at is None:
                continue
            if block.get("type") == "tool_use" and block.get("id"):
                started[block["id"]] = at
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in started:
                spans.append((started.pop(block["tool_use_id"]), at))
    tool = _merge_spans(spans)
    return (round(tool, 2) if tool is not None else None,
            round(thinking_ms / 1000, 2) if saw_thinking else None)


def _summarize_stream(lines: list[str], res: AgenticResult) -> None:
    """Fold the stream into the result.

    A session that uses background tools (Monitor, ScheduleWakeup) emits one
    `result` event per wake-up segment. In each, num_turns and usage cover that
    segment only, while total_cost_usd and duration_api_ms are running totals.
    So turns and tokens are summed and cost/API time come from the last event.
    """
    res.tool_time_s, res.thinking_time_s = stream_timing(lines)
    turns = None
    last_error = None
    tokens = {"input_tokens": 0, "output_tokens": 0,
              "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    for line in lines:
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        if ev.get("type") == "assistant":
            for block in _content_blocks(ev):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    res.tool_calls += 1
        elif ev.get("type") == "result":
            usage = ev.get("usage") or {}
            if ev.get("num_turns") is not None:
                turns = (turns or 0) + int(ev["num_turns"])
            for k in tokens:
                tokens[k] += int(usage.get(k) or 0)
            res.duration_api_ms = ev.get("duration_api_ms")
            res.cost_estimate_usd = ev.get("total_cost_usd")
            message = str(ev.get("result") or "")[:4000]
            if message:
                res.final_message = message
            last_error = (f"claude error: {message[:300] or ev.get('subtype')}"
                          if ev.get("is_error") else None)
    if last_error:
        res.error = last_error
    if res.timed_out:
        # Stopped at the time limit. If the model replied after the last
        # result event (or there was none), Claude Code never reported that
        # stretch. Count the model's replies instead (one id per API reply,
        # repeated per content block) and take each reply's input and cache
        # tokens, which match the result events exactly. Its output tokens do
        # not: the stream shows them before the reply is finished, so they
        # stay unknown, like cost and API time, which the result event alone
        # reports (a partial running total would understate them).
        per: dict[str, dict[str, int]] = {}
        unreported = False
        for line in lines:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(ev, dict):
                continue
            if ev.get("type") == "result":
                unreported = False
                continue
            msg = ev.get("message") if ev.get("type") == "assistant" else None
            if isinstance(msg, dict) and msg.get("id") and msg.get("model") != "<synthetic>":
                usage, seen = msg.get("usage") or {}, per.setdefault(msg["id"], {})
                unreported = True
                for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
                    seen[k] = max(seen.get(k, 0), int(usage.get(k) or 0))
        if unreported:
            turns = len(per) or None
            for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
                tokens[k] = sum(seen.get(k, 0) for seen in per.values())
            res.output_tokens_known = False
            res.cost_estimate_usd = res.duration_api_ms = None
    res.num_turns = turns
    res.input_tokens = tokens["input_tokens"]
    res.output_tokens = tokens["output_tokens"]
    res.cache_read_tokens = tokens["cache_read_input_tokens"]
    res.cache_write_tokens = tokens["cache_creation_input_tokens"]


# --------------------------------------------------------------------------- #
# opencode backend (open-weight models on OpenCode Go)                         #
# --------------------------------------------------------------------------- #
# Set as literal `-e NAME=VALUE` (no secrets): keep the sandbox's opencode to
# the config we write, with no project config, Claude Code files, external
# skills or self-updates.
OPENCODE_ENV_FLAGS = {
    "OPENCODE_CONFIG": "/gate1/opencode.json",
    "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
    "OPENCODE_DISABLE_CLAUDE_CODE": "1",
    "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
    "OPENCODE_DISABLE_AUTOUPDATE": "1",
    "OPENCODE_DISABLE_LSP_DOWNLOAD": "1",
}


# opencode tool permissions denied in every attempt: the counterpart of
# CLAUDE_DISALLOWED_TOOLS. Action names are opencode's tool ids (the stream
# logs `webfetch` and `websearch`; v2 renamed v1's `task` to `subagent`).
OPENCODE_DENIED_ACTIONS = ("subagent", "webfetch", "websearch")


def opencode_config(model_id: str, effort: str | None) -> dict[str, Any]:
    """The per-attempt opencode config (opencode v2 schema, checked against
    v2.2.5's `debug config` / `debug agents`). No secrets: the key arrives by
    environment variable name.

    - only the OpenCode Go provider may be used, so a wrong model id can never
      fall through to opencode's pay-as-you-go provider;
    - every tool is allowed except sub-agents and the web tools, as Claude
      Code runs with Agent, WebFetch and WebSearch disallowed (the proxy
      refuses webfetch anyway; websearch may run through opencode's servers);
    - no MCP servers, plugins, LSP, formatter (it would rewrite the model's
      files), snapshots or sharing;
    - the thinking level goes in the build agent's request body as
      `reasoning_effort`: Go models expose no low/medium/high variants
      ("Variant unavailable", probed 2026-11-01).
    """
    model = {"providerID": OPENCODE_PROVIDER, "model": model_id}
    agents: dict[str, Any] = {"title": {"model": model}}
    if effort:
        agents["build"] = {"request": {"body": {"reasoning_effort": effort}}}
    return {
        "$schema": "https://opencode.ai/config.json",
        "model": model,
        "agents": agents,
        "policies": [
            {"action": "provider.use", "resource": "*", "effect": "deny"},
            {"action": "provider.use", "resource": OPENCODE_PROVIDER, "effect": "allow"},
        ],
        "permissions": [
            {"action": "*", "resource": "*", "effect": "allow"},
            *({"action": action, "resource": "*", "effect": "deny"}
              for action in OPENCODE_DENIED_ACTIONS),
        ],
        "instructions": ["/gate1/system.md"],
        "mcp": {}, "plugins": [], "lsp": False, "formatter": False,
        "snapshots": False, "share": "disabled", "update": "disable",
    }


def write_opencode_control(control: Path, goal: str, system: str, model_id: str,
                           effort: str | None) -> None:
    """Same goal and task files as Claude Code (`/goal ...` on stdin, the task
    as instructions), plus the opencode config."""
    write_control(control, goal, system)
    (control / "opencode.json").write_text(
        json.dumps(opencode_config(model_id, effort), indent=2), encoding="utf-8")


def opencode_command(name: str, ws: Path, control: Path, model_id: str,
                     postgres: bool, network: str = NETWORK_ALLOWLIST,
                     image: str = IMAGE) -> list[str]:
    env_args = ["-e", OPENCODE_KEY_ENV]          # by name: the value comes from our env
    for k, v in OPENCODE_ENV_FLAGS.items():
        env_args += ["-e", f"{k}={v}"]
    return _docker_prefix(name, ws, control, postgres, env_args, network, image) + [
        "sh", "-c", 'exec opencode run "$@" < /gate1/prompt.txt', "opencode",
        "--standalone", "--format", "json", "--auto", "--thinking",
        "--title", "gate1", "--model", f"{OPENCODE_PROVIDER}/{model_id}"]


def _opencode_env() -> dict[str, str]:
    """What docker needs plus the Go key, renamed to what opencode reads. No
    Claude token and no other provider's key."""
    keep = ("PATH", "HOME", "DOCKER_HOST", "DOCKER_CONFIG", "DOCKER_CONTEXT")
    env = {k: v for k, v in os.environ.items() if k in keep}
    if os.environ.get(OPENCODE_KEY_SOURCE):
        env[OPENCODE_KEY_ENV] = os.environ[OPENCODE_KEY_SOURCE]
    return env


def _ms(value: Any) -> float | None:
    return float(value) / 1000 if isinstance(value, (int, float)) else None


def _opencode_infra(err: dict) -> bool:
    """A provider-side failure (auth, quota, rate limit, routing, outage) says
    nothing about the model: an infra error, not scored."""
    status = err.get("status")
    return (str(err.get("type") or "").startswith("provider.")
            or status in (401, 402, 403, 408, 429)
            or (isinstance(status, int) and status >= 500))


def summarize_opencode(lines: list[str], res: AgenticResult, model_id: str) -> None:
    """Fold `opencode run --format json` events into the result.

    Each step_finish closes one model call and carries that step's tokens and
    cost (deltas, so summed). Tool time is the merged span of each tool call's
    own start/end. opencode reports no API time, so model time is derived:
    the steps' wall time minus the tool time inside them.
    """
    tokens = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
    steps, reported, saw_cost = 0, 0.0, False
    tool_spans: list[tuple[float, float]] = []
    step_spans: list[tuple[float, float]] = []
    step_open: float | None = None
    thinking_s, saw_thinking = 0.0, False
    error: dict | None = None
    for line in lines:
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        kind = ev.get("type")
        part = ev.get("part") if isinstance(ev.get("part"), dict) else {}
        at = _ms(ev.get("timestamp"))
        if kind == "step_start":
            step_open = at
        elif kind == "step_finish":
            steps += 1
            tk = part.get("tokens") if isinstance(part.get("tokens"), dict) else {}
            cache = tk.get("cache") if isinstance(tk.get("cache"), dict) else {}
            for key, val in (("input", tk.get("input")), ("output", tk.get("output")),
                             ("reasoning", tk.get("reasoning")),
                             ("cache_read", cache.get("read")), ("cache_write", cache.get("write"))):
                tokens[key] += int(val or 0)
            if isinstance(part.get("cost"), (int, float)):
                reported += float(part["cost"])
                saw_cost = True
            if step_open is not None and at is not None and at >= step_open:
                step_spans.append((step_open, at))
            step_open = None
        elif kind == "tool_use":
            res.tool_calls += 1
            state = part.get("state") if isinstance(part.get("state"), dict) else {}
            t = state.get("time") if isinstance(state.get("time"), dict) else {}
            a, b = _ms(t.get("start")), _ms(t.get("end"))
            if a is not None and b is not None and b >= a:
                tool_spans.append((a, b))
        elif kind == "reasoning":
            t = part.get("time") if isinstance(part.get("time"), dict) else {}
            a, b = _ms(t.get("start")), _ms(t.get("end"))
            if a is not None and b is not None and b >= a:
                thinking_s += b - a
                saw_thinking = True
        elif kind == "text":
            if part.get("text"):
                res.final_message = str(part["text"])[:4000]
        elif kind == "error" and isinstance(ev.get("error"), dict):
            error = ev["error"]
    res.num_turns = steps or None
    res.input_tokens, res.output_tokens = tokens["input"], tokens["output"] + tokens["reasoning"]
    res.reasoning_tokens = tokens["reasoning"]
    res.cache_read_tokens, res.cache_write_tokens = tokens["cache_read"], tokens["cache_write"]
    res.cost_reported_usd = round(reported, 6) if saw_cost else None
    if steps:
        res.cost_estimate_usd = round(pricing.cost_usd(
            model_id, res.input_tokens, res.output_tokens,
            res.cache_read_tokens, res.cache_write_tokens), 6)
    tool = _merge_spans(tool_spans)
    res.tool_time_s = round(tool, 2) if tool is not None else None
    if step_spans:
        step_total = sum(b - a for a, b in step_spans)
        res.duration_api_ms = int(max(0.0, step_total - (tool or 0.0)) * 1000)
        res.model_time_source = "derived"
    res.thinking_time_s = round(thinking_s, 2) if saw_thinking else None
    if error is not None:
        status = error.get("status")
        message = error.get("message") or (error.get("data") or {}).get("message") or ""
        detail = (f"opencode error: {error.get('type') or error.get('name') or 'error'}: "
                  f"{message}{f' (status {status})' if status else ''}")
        if _opencode_infra(error):
            res.error = detail[:600]
        else:
            res.agent_error = detail[:600]
    elif not steps and not res.timed_out:
        tail = " ".join(ln.strip() for ln in lines[-3:] if ln.strip())
        res.error = f"agent did not run: opencode made no model call: {tail[-400:]}"


_OPENCODE_LIMIT_RE = re.compile(
    r"usage limit|rate limit|limit (?:reached|exceeded)|quota|weekly limit|monthly limit|"
    r"5-hour|insufficient (?:balance|credit)|payment required|invalid credential|"
    r"unauthori[sz]ed|provider\.auth|provider\.no-route|status 40[123]|status 429|"
    # not a quota, but every later attempt would fail the same way
    r"made no model call", re.I)


# Claude Code's own session record inside the sandbox (the agent user's
# home; the project is /work). It holds every reply with its final usage.
CLAUDE_SESSION_GLOB = "/home/agent/.claude/projects/*/*.jsonl /root/.claude/projects/*/*.jsonl"


def _session_replies(lines: list[str]) -> dict[str, tuple[str, dict]]:
    """Each model reply in Claude Code's session record: id -> (model, usage).
    A reply repeats per content block; its usage grows to the final counts, so
    the largest output count is kept (input and cache counts do not change)."""
    per: dict[str, tuple[str, dict]] = {}
    for line in lines:
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = ev.get("message") if isinstance(ev, dict) and ev.get("type") == "assistant" else None
        if isinstance(msg, dict) and msg.get("id") and msg.get("model") != "<synthetic>":
            usage = msg.get("usage") or {}
            seen = per.get(msg["id"])
            if seen is None or int(usage.get("output_tokens") or 0) >= int(seen[1].get("output_tokens") or 0):
                per[msg["id"]] = (str(msg.get("model") or ""), usage)
    return per


def session_output_tokens(lines: list[str]) -> int | None:
    """Output tokens from Claude Code's session record: each reply's final
    count, summed. None if the record holds no reply."""
    per = _session_replies(lines)
    return sum(int(u.get("output_tokens") or 0) for _, u in per.values()) if per else None


def session_cost_usd(lines: list[str]) -> float | None:
    """API list-price cost of a Claude Code session from its session record,
    priced per request (pricing.usage_cost_usd: 1-hour cache writes, Haiku's
    long-context tier). For a session stopped at the time limit, which Claude
    Code never prices. Leaves out Claude Code's own background calls, which
    the record does not hold (about 1% of a session's cost). None if the record
    holds no reply or a model the price table does not know."""
    per = _session_replies(lines)
    if not per or any(m not in pricing.PRICES for m, _ in per.values()):
        return None
    return round(sum(pricing.usage_cost_usd(m, u) for m, u in per.values()), 6)


# --------------------------------------------------------------------------- #
# Backends                                                                     #
# --------------------------------------------------------------------------- #
class ClaudeCodeBackend:
    """Claude models through the Claude Code CLI on the subscription."""
    name = "claude-code"
    route = "claude-code"
    goal_mode = "native"
    efforts = common.EFFORT_LEVELS
    secret_envs = (TOKEN_ENV,)
    version: str | None = None

    def limit_re(self) -> re.Pattern:
        return _LIMIT_RE

    def write_control(self, control: Path, goal: str, system: str, model_id: str,
                      effort: str | None) -> None:
        write_control(control, goal, system)

    def command(self, name: str, ws: Path, control: Path, model_id: str,
                effort: str | None, postgres: bool,
                network: str = NETWORK_ALLOWLIST, image: str = IMAGE) -> list[str]:
        return docker_command(name, ws, control, model_id, effort, postgres, network, image)

    def env(self) -> dict[str, str]:
        return _container_env()

    def summarize(self, lines: list[str], res: AgenticResult, model_id: str) -> None:
        _summarize_stream(lines, res)
        if res.duration_api_ms is not None:
            res.model_time_source = "reported"

    def save_session(self, name: str) -> list[str]:
        """Claude Code's session record, read from the still-running
        container just before the time limit stops it: the stream shows each
        reply's output tokens before the reply is finished, the record its
        final count (agentic.session_output_tokens)."""
        proc = subprocess.run(["docker", "exec", name, "sh", "-c",
                               f"cat {CLAUDE_SESSION_GLOB} 2>/dev/null"],
                              capture_output=True, text=True, timeout=60)
        return proc.stdout.splitlines(keepends=True)

    def preflight(self) -> None:
        preflight()


class OpencodeBackend:
    """Open-weight models through opencode on the OpenCode Go subscription."""
    name = "opencode"
    route = OPENCODE_PROVIDER
    goal_mode = "native"
    efforts = common.GO_EFFORT_LEVELS
    secret_envs = (OPENCODE_KEY_ENV,)
    version: str | None = None

    def limit_re(self) -> re.Pattern:
        return _OPENCODE_LIMIT_RE

    def write_control(self, control: Path, goal: str, system: str, model_id: str,
                      effort: str | None) -> None:
        write_opencode_control(control, goal, system, model_id, effort)

    def command(self, name: str, ws: Path, control: Path, model_id: str,
                effort: str | None, postgres: bool,
                network: str = NETWORK_ALLOWLIST, image: str = IMAGE) -> list[str]:
        return opencode_command(name, ws, control, model_id, postgres, network, image)

    def env(self) -> dict[str, str]:
        return _opencode_env()

    def summarize(self, lines: list[str], res: AgenticResult, model_id: str) -> None:
        summarize_opencode(lines, res, model_id)

    def preflight(self) -> None:
        if not os.environ.get(OPENCODE_KEY_SOURCE):
            raise NotReady(f"{OPENCODE_KEY_SOURCE} is not set: add the OpenCode Go key to .env")
        _docker_ready()
        label = subprocess.run(
            ["docker", "image", "inspect", "--format",
             f'{{{{index .Config.Labels "{OPENCODE_VERSION_LABEL}"}}}}', IMAGE],
            capture_output=True, text=True).stdout.strip()
        if not label or label == "<no value>":
            raise NotReady(f"sandbox image {IMAGE} has no opencode: rebuild it "
                           f"(docker build -t {IMAGE} docker/agent)")
        self.version = label


def backend_for(cfg, model) -> ClaudeCodeBackend | OpencodeBackend:
    """Claude models run in Claude Code, OpenCode Go models in opencode."""
    api = cfg.api_for(model)
    if api is not None and api.family == "claude-code":
        return ClaudeCodeBackend()
    if model.api == OPENCODE_PROVIDER:
        return OpencodeBackend()
    raise ValueError(f"agentic runs use Claude Code or opencode: {model.name} is on neither "
                     "the Claude Code nor the OpenCode Go route")


# --------------------------------------------------------------------------- #
# Egress: the allowlist proxy that is the sandbox's only way out               #
# --------------------------------------------------------------------------- #
_EGRESS_OK_RE = re.compile(r'Established connection to host "([^"]+)"')
_EGRESS_REFUSED_RE = re.compile(r'refused on filtered \w+ "([^"]+)"')


def _docker_out(*args: str) -> tuple[int, str]:
    p = subprocess.run(["docker", *args], capture_output=True, text=True)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def start_egress() -> None:
    """The internal network and the proxy on it, created if missing. A proxy
    already running is kept, so two batches can share it (their hosts then mix
    in each other's records); `docker rm -f gate1-egress` restarts it."""
    if _docker_out("image", "inspect", EGRESS_IMAGE)[0]:
        raise NotReady(f"egress proxy image {EGRESS_IMAGE} not built: "
                       f"docker build -t {EGRESS_IMAGE} docker/egress")
    rc, internal = _docker_out("network", "inspect", "--format", "{{.Internal}}", SANDBOX_NETWORK)
    if rc:
        rc, out = _docker_out("network", "create", "--internal", SANDBOX_NETWORK)
        if rc:
            raise NotReady(f"could not create the sandbox network {SANDBOX_NETWORK}: {out[-300:]}")
    elif internal != "true":
        raise NotReady(f"docker network {SANDBOX_NETWORK} exists but is not internal (it would "
                       f"let the sandbox out): docker network rm {SANDBOX_NETWORK}")
    if _docker_out("inspect", "--format", "{{.State.Running}}", EGRESS_NAME)[1] == "true":
        return
    _docker_out("rm", "-f", EGRESS_NAME)
    rc, out = _docker_out("run", "-d", "--rm", "--name", EGRESS_NAME, EGRESS_IMAGE)
    if not rc:
        rc, out = _docker_out("network", "connect", SANDBOX_NETWORK, EGRESS_NAME)
    if rc:
        _docker_out("rm", "-f", EGRESS_NAME)
        raise NotReady(f"could not start the egress proxy: {out[-300:]}")


def check_egress() -> None:
    """Prove the lock before spending anything: from a sandbox container, an
    allowed host answers through the proxy, a refused one does not, and nothing
    gets out without the proxy."""
    probe = (f'a=$(curl -s -o /dev/null -w "%{{http_code}}" --max-time 20 {EGRESS_PROBE_ALLOWED}); '
             f'b=$(curl -s -o /dev/null -w "%{{http_code}}" --max-time 20 {EGRESS_PROBE_BLOCKED}); '
             f'c=$(curl -s -o /dev/null -w "%{{http_code}}" --max-time 10 --noproxy "*" '
             f'{EGRESS_PROBE_ALLOWED}); echo "allowed=$a blocked=$b direct=$c"')
    cmd = ["run", "--rm", *_network_args(NETWORK_ALLOWLIST), "--entrypoint", "sh", IMAGE, "-c", probe]
    rc, out = _docker_out(*cmd)
    got = dict(kv.split("=", 1) for kv in re.findall(r"\b(?:allowed|blocked|direct)=\d+", out))
    ok = (got.get("allowed", "000")[:1] in ("2", "3")
          and got.get("blocked") == "000" and got.get("direct") == "000")
    if not ok:
        raise NotReady(f"sandbox network check failed (want allowed=2xx/3xx, blocked=000, "
                       f"direct=000): {out[-300:] or f'exit {rc}'}")


def egress_since(since: float) -> tuple[list[str], list[str]]:
    """(hosts let through, hosts refused) in the proxy's log since `since`."""
    _, log = _docker_out("logs", "--since", f"{since:.3f}", EGRESS_NAME)
    return (sorted(set(_EGRESS_OK_RE.findall(log))), sorted(set(_EGRESS_REFUSED_RE.findall(log))))


def prepare_network(network: str) -> None:
    if network == NETWORK_ALLOWLIST:
        start_egress()
        check_egress()


def _redact(line: str, secrets: list[str]) -> str:
    for value in secrets:
        line = line.replace(value, "[REDACTED]")
    return line


def run_attempt(cfg, pair_id: str, role: str, model, case_id: str, rep: int, run_id: str,
                *, time_limit_s: int = DEFAULT_TIME_LIMIT_S, effort: str | None = None,
                workroot: Path | None = None, score: bool = True,
                scorer: Callable | None = None, backend=None,
                network: str = NETWORK_ALLOWLIST, track: str | None = None,
                tell_time_limit: bool = False) -> AgenticResult:
    spec = CASES[case_id]
    backend = backend or backend_for(cfg, model)
    sources.ensure(case_id)
    res = AgenticResult(pair_id=pair_id, case_id=case_id, model_slug=model.id,
                        model_name=model.name, role=role, rep=rep, run_id=run_id,
                        effort_override=effort,
                        reasoning_requested={"effort": effort} if effort else None,
                        time_limit_s=time_limit_s, time_limit_told=tell_time_limit,
                        track=track, goal=spec.goal, created_at=time.time(),
                        provider=backend.route, agent=backend.name,
                        agent_version=backend.version, goal_mode=backend.goal_mode,
                        network=network)
    out = record_path(pair_id, run_id, model.id, case_id, rep)
    out.parent.mkdir(parents=True, exist_ok=True)
    root = workroot or Path(common.RUNS_DIR).parent / ".agentic-work"
    ws = root / f"{case_id}-{run_id}-{model.id.replace('/', '__')}-r{rep}"
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True)
    try:
        spec.setup(ws)
        before = snapshot(ws, spec)
        name = f"gate1-agent-{uuid.uuid4().hex[:10]}"
        control = ws.with_name(ws.name + ".control")
        system = SYSTEM_NOTE + (f"\n\n{time_note(time_limit_s)}" if tell_time_limit else "")
        backend.write_control(control, spec.goal,
                              system + "\n\n# The task\n\n" + task_prompt(case_id),
                              model.id, effort)
        res.image = spec.image or IMAGE
        cmd = backend.command(name, ws, control, model.id, effort, spec.postgres, network,
                              image=res.image)
        env = backend.env()
        started_at = time.time()
        # a key the agent prints (e.g. by running `env`) never reaches runs/
        secrets = [env[k] for k in backend.secret_envs if len(env.get(k) or "") >= 8]
        lines: list[str] = []
        stream_log = out.with_suffix(".stream.jsonl")
        t0 = time.monotonic()
        with open(stream_log, "w", encoding="utf-8") as log:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, text=True, env=env)

            def pump() -> None:
                for line in proc.stdout:            # type: ignore[union-attr]
                    line = _redact(line, secrets)
                    log.write(line)
                    lines.append(line)

            reader = threading.Thread(target=pump, daemon=True)
            reader.start()
            # long cases: harvest the work in progress at fixed times, to score
            # it after the session (a progress curve, not only the end state)
            snaps: list[tuple[int, str]] = []

            def take(at_s: int) -> None:
                try:
                    snaps.append((at_s, answer_from(before, snapshot(ws, spec), spec.deliverables)))
                except Exception:                   # noqa: BLE001 — a snapshot never stops a run
                    pass
            timers = [threading.Timer(t, take, args=(t,)) for t in spec.snapshots_s if t < time_limit_s]
            for tm in timers:
                tm.daemon = True
                tm.start()
            session: list[str] = []
            try:
                proc.wait(timeout=time_limit_s)
            except subprocess.TimeoutExpired:
                res.timed_out = True
                if hasattr(backend, "save_session"):
                    try:
                        session = [_redact(line, secrets) for line in backend.save_session(name)]
                    except Exception:               # noqa: BLE001 — output tokens stay unknown
                        session = []
                subprocess.run(["docker", "kill", name], capture_output=True)
                proc.wait(timeout=60)
            finally:
                for tm in timers:
                    tm.cancel()
            reader.join(timeout=30)
        res.latency_s = round(time.monotonic() - t0, 2)
        if network == NETWORK_ALLOWLIST:
            res.egress_hosts, res.blocked_hosts = egress_since(started_at)
        backend.summarize(lines, res, model.id)
        if session:
            out.with_suffix(".session.jsonl").write_text("".join(session), encoding="utf-8")
            if not res.output_tokens_known and (n := session_output_tokens(session)) is not None:
                res.output_tokens, res.output_tokens_known = n, True
            if res.cost_estimate_usd is None:
                res.cost_from_prices_usd = session_cost_usd(session)
        if proc.returncode not in (0, None) and not res.timed_out and res.num_turns is None:
            tail = "".join(lines[-5:]).strip()
            res.error = res.error or f"agent did not run (exit {proc.returncode}): {tail[-400:]}"
        after = snapshot(ws, spec)
        res.output_text = answer_from(before, after, spec.deliverables)
        res.files_changed = sum(res.output_text.count(h)
                                for h in ("### FILE:", "### DELETE:", "### BINARY:"))
        # A session that ran to its end or to the time limit delivered whatever
        # it left behind. One that never started, or that Claude Code ended
        # with an error (login, usage limit, API), says nothing about the
        # model: an infra error, never scored.
        res.ok = res.error is None
        if score and res.ok:
            from scorers.dispatch import score_case
            scored = (scorer or score_case)(case_id, res.output_text, model.id)
            res.passed, res.reason, res.checks = bool(scored.passed), scored.reason, dict(scored.checks)
            for at_s, text in sorted(snaps):
                if not text.strip():
                    res.snapshots.append({"at_s": at_s, "passed": False, "score": 0.0,
                                          "checks": {}, "reason": "nothing delivered yet"})
                    continue
                s = (scorer or score_case)(case_id, text, model.id)
                res.snapshots.append({"at_s": at_s, "passed": bool(s.passed), "score": s.score,
                                      "checks": dict(s.checks), "reason": s.reason})
    except Exception as exc:                        # noqa: BLE001 — recorded, never crashes a batch
        res.error = res.error or f"{type(exc).__name__}: {exc}"
        res.ok = False
    finally:
        out.write_text(json.dumps(asdict(res), indent=2), encoding="utf-8")
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(ws.with_name(ws.name + ".control"), ignore_errors=True)
    return res


# --------------------------------------------------------------------------- #
# Report                                                                       #
# --------------------------------------------------------------------------- #
def load_records(pair_id: str, run_id: str) -> list[dict]:
    return [json.loads(f.read_text()) for f in sorted(agentic_dir(pair_id, run_id).glob("*.json"))]


def display_name(rec: dict) -> str:
    """The model's name, marked with its agent when that isn't Claude Code."""
    agent = rec.get("agent") or "claude-code"
    name = rec.get("model_name") or rec.get("model_slug") or "?"
    return name if agent == "claude-code" else f"{name} · {agent}"


def render_report(pair_id: str, run_id: str, recs: list[dict]) -> str:
    lines = [f"# Agentic runs — {pair_id} · run {run_id}", "",
             "The model works on a copy of the project inside a sandbox with an agent "
             "(Claude Code for Claude models, opencode for open-weight models): edit, build, "
             "test, fix, until its `/goal` is met or the time limit is hit; "
             "what it delivered is then scored by the case's acceptance check, including "
             "hidden tests it never saw. Infra errors (the session never ran) are left out.",
             "", "## Summary", "",
             "| Case | Model | Effort | Passed | Mean time (min) | Mean cost (USD) | Mean turns |",
             "|---|---|---|---:|---:|---:|---:|"]
    groups: dict[tuple, list[dict]] = {}
    for r in recs:
        groups.setdefault((r["case_id"], display_name(r), r.get("effort_override") or "default"),
                          []).append(r)
    for (case, name, effort), rs in sorted(groups.items()):
        ran = [r for r in rs if r.get("ok")]
        passed = sum(1 for r in ran if r.get("passed"))
        infra = len(rs) - len(ran)
        mean = lambda key: (sum(float(r.get(key) or 0) for r in ran) / len(ran)) if ran else None  # noqa: E731
        t, c, n = mean("latency_s"), mean("cost_estimate_usd"), mean("num_turns")
        lines.append(f"| {case} | {name} | {effort} | {passed}/{len(ran)}"
                     f"{f' (+{infra} infra)' if infra else ''} | "
                     f"{'n/a' if t is None else f'{t / 60:.1f}'} | "
                     f"{'n/a' if c is None else f'${c:.2f}'} | {'n/a' if n is None else f'{n:.0f}'} |")
    lines += ["", "## Per attempt", "",
              "| Case | Rep | Model | Result | Time (min) | Cost (USD) | Turns | Tool calls | Files | Reason |",
              "|---|---:|---|---|---:|---:|---:|---:|---:|---|"]
    for r in recs:
        result = ("infra error" if not r.get("ok") else "✅" if r.get("passed") else "❌")
        if r.get("timed_out"):
            result += " (time limit)"
        reason = (r.get("error") if not r.get("ok") else r.get("reason") or "").replace("|", "\\|")
        cost = r.get("cost_estimate_usd")
        lines.append(f"| {r['case_id']} | {r['rep'] + 1} | {display_name(r)} | {result} | "
                     f"{float(r.get('latency_s') or 0) / 60:.1f} | "
                     f"{'n/a' if cost is None else f'${cost:.2f}'} | {r.get('num_turns') or 'n/a'} | "
                     f"{r.get('tool_calls', 0)} | {r.get('files_changed', 0)} | {reason[:160]} |")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
_LIMIT_RE = re.compile(r"usage limit|rate limit|hit your (?:[\w-]+ )?limit|Not logged in|"
                       r"credit balance", re.I)


class NotReady(RuntimeError):
    pass


def preflight() -> None:
    if not os.environ.get(TOKEN_ENV):
        raise NotReady(f"{TOKEN_ENV} is not set: run `claude setup-token` and add the token "
                       "to .env (agentic runs log in with it inside the sandbox)")
    _docker_ready()


def _docker_ready() -> None:
    if shutil.which("docker") is None:
        raise NotReady("docker not found on PATH")
    if subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True).returncode:
        raise NotReady(f"sandbox image {IMAGE} not built: docker build -t {IMAGE} docker/agent")


def run(cfg, pair_id: str, *, role: str = "current", case: str | None = None,
        repeats: int = 1, time_limit_s: int = DEFAULT_TIME_LIMIT_S,
        effort: str | None = None, backend=None,
        max_spend_usd: float | None = None,
        network: str = NETWORK_ALLOWLIST, track: str | None = None,
        tell_time_limit: bool = False) -> tuple[str, list[AgenticResult]]:
    pair = cfg.get_pair(pair_id)
    model = pair.current if role == "current" else pair.target
    backend = backend or backend_for(cfg, model)
    # a comma-separated list, a suite name from models.yaml, or every case
    screening_suite = load_config(suite="real-screen").cases
    if case in (None, "all"):
        # every case except those still being screened (they need --track)
        cases = [c for c in CASES if c not in screening_suite]
    elif case in cfg.suites:
        cases = list(load_config(suite=None if case == "sanity" else case).cases)
    else:
        cases = [c.strip() for c in case.split(",") if c.strip()]
    unknown = [c for c in cases if c not in CASES]
    if unknown:
        raise ValueError(f"no agentic setup for case(s): {', '.join(unknown)}")
    # cases still being screened (models.yaml `real-screen`) never reach the
    # main board: they run only on a separate track
    screening = [c for c in cases if c in screening_suite]
    if screening and track is None:
        raise ValueError(f"{', '.join(screening)} is still being screened: run it with --track "
                         "(e.g. --track real-screen), never on the main board")
    if track is not None and not TRACK_RE.match(track):
        raise ValueError(f"--track must be lowercase letters, digits and dashes; got {track!r}")
    effort = effort or cfg.effort
    if effort and effort not in backend.efforts:
        raise ValueError(f"{backend.name} takes effort {', '.join(backend.efforts)}; got {effort!r}")
    prepare_network(network)
    run_id = new_run_id()
    results = []
    stop = False
    spent = 0.0
    print(f"agentic run id: {run_id}  model: {model.name}  agent: {backend.name}  "
          f"effort: {effort or 'default'}  network: {network}"
          + (f"  track: {track}" if track else "")
          + (f"  time limit told: {time_limit_s / 60:g} min" if tell_time_limit else ""))
    if network == NETWORK_OPEN:
        print("warning: --network open: the sandbox can reach the whole internet, "
              "including published answers; not for scored runs", flush=True)
    for case_id in cases:
        for rep in range(repeats):
            if stop:
                break
            r = run_attempt(cfg, pair_id, role, model, case_id, rep, run_id,
                            time_limit_s=time_limit_s, effort=effort, backend=backend,
                            network=network, track=track, tell_time_limit=tell_time_limit)
            results.append(r)
            status = ("INFRA " + (r.error or "")[:120] if not r.ok else
                      ("PASS" if r.passed else f"FAIL ({r.reason[:120]})"))
            print(f"  {case_id} rep {rep + 1}/{repeats}: {r.latency_s / 60:.1f} min, "
                  f"{r.num_turns or 0} turns, ${r.cost_estimate_usd or 0:.2f}"
                  f"{' [time limit]' if r.timed_out else ''}  {status}", flush=True)
            if r.blocked_hosts:
                print(f"    proxy refused: {', '.join(r.blocked_hosts)}", flush=True)
            if not r.ok and r.error and backend.limit_re().search(r.error):
                # every later attempt would fail the same way
                print(f"stopping: {r.error[:120]}", flush=True)
                stop = True
            spent += r.cost_estimate_usd or 0.0
            if max_spend_usd is not None and spent >= max_spend_usd and not stop:
                print(f"stopping: estimated spend ${spent:.2f} reached the "
                      f"--max-spend-usd cap ${max_spend_usd:.2f}", flush=True)
                stop = True
    report = agentic_dir(pair_id, run_id) / "REPORT.md"
    report.write_text(render_report(pair_id, run_id, load_records(pair_id, run_id)), encoding="utf-8")
    print(f"wrote {report}")
    return run_id, results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pair", required=True)
    ap.add_argument("--role", choices=("current", "target"), default="current")
    ap.add_argument("--case", help="case id(s), comma-separated, or a suite (sanity, real); "
                                   "default: every case with an agentic setup")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--time-limit", type=int, default=DEFAULT_TIME_LIMIT_S,
                    help="seconds per attempt (default 3600)")
    ap.add_argument("--effort", help="thinking level: Claude Code --effort, or opencode's "
                                     "reasoning_effort (default: models.yaml defaults.effort)")
    ap.add_argument("--max-spend-usd", type=float,
                    help="stop the batch once the estimated spend reaches this (list prices)")
    ap.add_argument("--network", choices=(NETWORK_ALLOWLIST, NETWORK_OPEN),
                    default=NETWORK_ALLOWLIST,
                    help="allowlist (default): the sandbox reaches only the model APIs and "
                         "package registries, through docker/egress; open: the whole "
                         "internet (debugging only, never for scored runs)")
    ap.add_argument("--track", help="record the attempts for a separate board "
                                    "(leaderboard.py --track NAME), never the main one; "
                                    "e.g. r1b-10min")
    ap.add_argument("--tell-time-limit", action="store_true",
                    help="state the time limit in the agent's prompt (default: not mentioned)")
    args = ap.parse_args(argv)
    load_env()
    cfg = load_config()
    try:
        pair = cfg.get_pair(args.pair)
        backend = backend_for(cfg, pair.current if args.role == "current" else pair.target)
        backend.preflight()
        run(cfg, args.pair, role=args.role, case=args.case, repeats=args.repeats,
            time_limit_s=args.time_limit, effort=args.effort, backend=backend,
            max_spend_usd=args.max_spend_usd, network=args.network, track=args.track,
            tell_time_limit=args.tell_time_limit)
    except (NotReady, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
