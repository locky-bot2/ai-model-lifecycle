"""scorers/r8_scorer.py — real-project Java → Rust port of a REST API slice (shogun-core).

The agent delivers a Cargo project in rust/ (agentic runs harvest rust/**,
never rust/target/). The scorer, in Docker, with a fresh PostgreSQL 17 on a
private network:

  1. build      `cargo build --release --locked` (Rust 1.100.0, image
                gate1-r8-rust: no JVM in it), with DATABASE_URL set to a
                database holding the pinned schema (for compile-time checked
                queries);
  2. rust_only  no Java, jar, class or war file in rust/, no JVM-bridge crate
                (jni, j4rs, ...) in Cargo.lock; and the service only ever runs
                in the JVM-free image;
  3. own_tests  `cargo test --release --locked` passes (DATABASE_URL: a
                second database with the schema);
  4. starts     the only binary, started with DATABASE_URL (the seeded test
                database) and PORT, answers on /rest within 60 s;
  5-9.          the hidden tests (scorers/fixtures/r8_hidden_tests: scenarios
                recorded from the original Java app, which passes all of them
                after a restart, in reverse order: record.sh): every scenario of
                a category must give the original's answer —
                auth, crud, permissions, queries — and `database`: the rows
                read after every write scenario match.

score = the share of hidden scenarios passed (a partial port shows how far
it got); passed = all 9 checks.

Usage:
    python -m scorers.r8_scorer --output-file <answer.txt>
    python -m scorers.r8_scorer --selftest       (a stub service: the pipeline works)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path

from .base import ScoreResult, apply_output, cli, record_tests
from .base import run_command as _run

CASE_ID = "r8_shogun_rust"
ROOT = Path(__file__).resolve().parent.parent
CASE_DIR = ROOT / "cases" / CASE_ID
SCHEMA = CASE_DIR / "schema.sql"
TESTS = Path(__file__).resolve().parent / "fixtures" / "r8_hidden_tests"
SELFTEST = Path(__file__).resolve().parent / "fixtures" / "r8_selftest"
RUST_IMAGE = os.environ.get("R8_RUST_IMAGE", "gate1-r8-rust:1.100.0")
TEST_IMAGE = os.environ.get("R8_TEST_IMAGE", "gate1-r8-tests:1")
PG_IMAGE = "postgres:17-alpine"
CARGO_VOLUME = "gate1_r8_scorer_cargo"           # crates downloaded by builds (never model output)
BUILD_TIMEOUT_S = 2400
TEST_TIMEOUT_S = 1800
START_TIMEOUT_S = 60
REQUIRED = ["build", "rust_only", "own_tests", "starts",
            "auth", "crud", "permissions", "queries", "database"]
HIDDEN = ["auth", "crud", "permissions", "queries"]
_JAVA_FILE_RE = re.compile(r"\.(java|jar|class|war|jsp)$", re.I)
_JVM_CRATES = {"jni", "jni-sys", "j4rs", "robusta_jni", "jvm", "jvm-rs", "rucaja", "java-locator"}
_TEST_RESULT_RE = re.compile(r"test result: (\w+)\. (\d+) passed; (\d+) failed")


def _docker(*args: str, timeout: int = 600) -> tuple[int, str]:
    return _run(["docker", *args], timeout=timeout)


def rust_only_problems(project: Path) -> list[str]:
    bad = [f.relative_to(project).as_posix() for f in project.rglob("*")
           if f.is_file() and "target" not in f.relative_to(project).parts and _JAVA_FILE_RE.search(f.name)]
    lock = project / "Cargo.lock"
    if lock.is_file():
        names = set(re.findall(r'^name = "([^"]+)"', lock.read_text(encoding="utf-8", errors="replace"), re.M))
        bad += [f"Cargo.lock: {n}" for n in sorted(names & _JVM_CRATES)]
    return bad


def binary_name(meta_json: str) -> str | None:
    """The one binary target (or the package-named one among several)."""
    try:
        meta = json.loads(meta_json[meta_json.index("{"):])
    except (ValueError, json.JSONDecodeError):
        return None
    bins, pkgs = [], []
    for p in meta.get("packages", []):
        pkgs.append(p.get("name"))
        bins += [t["name"] for t in p.get("targets", []) if "bin" in t.get("kind", [])]
    if len(bins) == 1:
        return bins[0]
    named = [b for b in bins if b in pkgs]
    return named[0] if len(named) == 1 else None


def _wait_pg(name: str) -> bool:
    # Over TCP, not the socket: on first start the image's entrypoint runs a
    # temporary socket-only server to create the database, then restarts it;
    # a socket check passes on that temporary server and the next psql can hit
    # the restart gap. Only the final server listens on TCP.
    for _ in range(60):
        if _docker("exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "ai", "-d", "aidb",
                   timeout=20)[0] == 0:
            return True
        time.sleep(1)
    return False


def _psql_file(pg: str, db: str, path: Path) -> tuple[int, str]:
    import subprocess
    with open(path, "rb") as f:
        p = subprocess.run(["docker", "exec", "-i", pg, "psql", "-U", "ai", "-d", db, "-q",
                            "-v", "ON_ERROR_STOP=1"], stdin=f, capture_output=True, timeout=300)
    return p.returncode, (p.stdout + p.stderr).decode(errors="replace")


def _tail(text: str, n: int = 40) -> str:
    return "\n".join(text.strip().splitlines()[-n:])


def score(output_text: str, *, model_slug: str = "", workdir: Path | None = None,
          project: Path | None = None, **_: object) -> ScoreResult:
    res = ScoreResult(case_id=CASE_ID, model_slug=model_slug)
    for k in REQUIRED:
        res.checks[k] = False
    tmp = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="r8_"))
    rust = tmp / "rust"
    if project is not None:                        # --selftest: a project on disk
        shutil.copytree(project, rust, dirs_exist_ok=True)
    else:
        applied = apply_output(output_text, tmp)
        res.details["files"] = len(applied.written) if hasattr(applied, "written") else None
    if not (rust / "Cargo.toml").is_file():
        res.reason = "no rust/Cargo.toml delivered"
        return res

    probs = rust_only_problems(rust)
    res.details["rust_only_problems"] = probs[:20]
    if shutil.which("docker") is None:
        res.reason = "docker not found: nothing could be built or run"
        return res
    for img, ctx in ((RUST_IMAGE, ROOT / "docker" / "r8-score"), (TEST_IMAGE, TESTS)):
        if _docker("image", "inspect", img)[0]:
            rc, out = _docker("build", "-q", "-t", img, str(ctx), timeout=1200)
            if rc:
                res.reason = f"could not build {img}: {_tail(out, 5)}"
                return res

    net = f"r8score-{uuid.uuid4().hex[:8]}"
    pg, app = f"{net}-pg", f"{net}-app"
    out_dir = tmp / "out"
    out_dir.mkdir(exist_ok=True)
    try:
        _docker("network", "create", net)
        _docker("run", "-d", "--name", pg, "--network", net, "-e", "POSTGRES_USER=ai",
                "-e", "POSTGRES_PASSWORD=ai", "-e", "POSTGRES_DB=aidb", PG_IMAGE)
        if not _wait_pg(pg):
            res.reason = "test database did not start (infra)"
            return res
        for db in ("unit", "port"):
            _docker("exec", pg, "createdb", "-U", "ai", db)
            rc, out = _psql_file(pg, db, SCHEMA)
            if rc:
                res.reason = f"could not load the schema (infra): {_tail(out, 5)}"
                return res
        cargo = ["run", "--rm", "--network", net, "-v", f"{rust}:/src", "-w", "/src",
                 "-v", f"{CARGO_VOLUME}:/usr/local/cargo/registry",
                 "-e", f"DATABASE_URL=postgres://ai:ai@{pg}:5432/unit", RUST_IMAGE]

        # 1. build
        rc, out = _docker(*cargo, "cargo", "build", "--release", "--locked", timeout=BUILD_TIMEOUT_S)
        res.checks["build"] = rc == 0
        if rc:
            res.details["build_errors"] = _tail(out, 60)
        res.checks["rust_only"] = res.checks["build"] and not probs

        # 3. own tests
        if res.checks["build"]:
            rc, out = _docker(*cargo, "cargo", "test", "--release", "--locked", timeout=TEST_TIMEOUT_S)
            sums = _TEST_RESULT_RE.findall(out)
            passed = sum(int(p) for _, p, _ in sums)
            failed = sum(int(f) for _, _, f in sums)
            record_tests(res, "unit", passed=passed, total=passed + failed)
            res.checks["own_tests"] = rc == 0
            if rc:
                res.details["own_test_errors"] = _tail(out, 60)

        # 4. start the service on the seeded database
        if res.checks["build"]:
            rc, meta = _docker(*cargo, "cargo", "metadata", "--no-deps", "--format-version", "1",
                               "--locked", timeout=300)
            name = binary_name(meta) if rc == 0 else None
            exe = rust / "target" / "release" / (name or "")
            if not name or not exe.is_file():
                res.reason = "no single binary target to start"
            else:
                rc, out = _psql_file(pg, "port", TESTS / "seed.sql")
                _docker("run", "-d", "--name", app, "--network", net,
                        "-v", f"{exe}:/srv/service:ro",
                        "-e", f"DATABASE_URL=postgres://ai:ai@{pg}:5432/port", "-e", "PORT=8080",
                        "-e", "RUST_BACKTRACE=1", "--entrypoint", "/srv/service", RUST_IMAGE)
                t0 = time.monotonic()
                up = False
                while time.monotonic() - t0 < START_TIMEOUT_S:
                    rc, code = _docker("exec", app, "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                                       "http://localhost:8080/rest/roles", timeout=10)
                    if rc == 0 and code.strip()[-3:] not in ("000", ""):
                        up = True
                        break
                    if _docker("inspect", "-f", "{{.State.Running}}", app)[1].strip() != "true":
                        break
                    time.sleep(1)
                res.details["start_s"] = round(time.monotonic() - t0, 1)
                res.checks["starts"] = up
                if not up:
                    res.details["service_log"] = _tail(_docker("logs", app)[1], 40)

        # 5-9. hidden tests
        if res.checks["starts"]:
            rc, out = _docker("run", "--rm", "--network", net, "-v", f"{TESTS}:/tests:ro",
                              "-v", f"{out_dir}:/out", TEST_IMAGE,
                              "--base-url", f"http://{app}:8080",
                              "--dsn", f"postgresql://ai:ai@{pg}:5432/port",
                              "--check", "--report", "/out/report.json", "--ready-timeout", "30",
                              timeout=3600)
            report_file = out_dir / "report.json"
            if report_file.is_file():
                rep = json.loads(report_file.read_text(encoding="utf-8"))
                results = rep["results"]
                for cat in HIDDEN:
                    rs = [r for r in results if r["category"] == cat]
                    ok = [r for r in rs if not r["http"]]
                    res.checks[cat] = bool(rs) and len(ok) == len(rs)
                    res.details[f"hidden_{cat}"] = f"{len(ok)}/{len(rs)}"
                dbs = [r for r in results if r["has_db"]]
                db_ok = [r for r in dbs if not r["db"]]
                res.checks["database"] = bool(dbs) and len(db_ok) == len(dbs)
                res.details["hidden_database"] = f"{len(db_ok)}/{len(dbs)}"
                res.details["hidden_passed"], res.details["hidden_total"] = rep["passed"], rep["total"]
                res.details["hidden_failures"] = [
                    {"id": r["id"], "why": r["http"] or r["db"]} for r in results if not r["passed"]][:40]
                record_tests(res, "hidden", passed=rep["passed"], total=rep["total"])
                res.score = rep["passed"] / rep["total"] if rep["total"] else 0.0
            else:
                res.details["hidden_errors"] = _tail(out, 20)
                res.details["service_log"] = _tail(_docker("logs", app)[1], 40)
    finally:
        _docker("rm", "-f", app, pg)
        _docker("network", "rm", net)
        if not workdir:
            # the build ran as root in Docker: clear target/ from inside it
            _docker("run", "--rm", "-v", f"{tmp}:/t", "--entrypoint", "rm", RUST_IMAGE, "-rf", "/t/rust/target")
            shutil.rmtree(tmp, ignore_errors=True)

    res.passed = all(res.checks.get(k) for k in REQUIRED)
    if not res.passed and not res.reason:
        res.reason = "failed checks: " + ", ".join(k for k in REQUIRED if not res.checks.get(k))
    return res


def selftest() -> int:
    """Score the stub (scorers/fixtures/r8_selftest/stub: a std-only service that
    answers 401 to everything): build, rust_only, own_tests and starts must pass
    and the hidden checks fail, which shows the pipeline runs end to end."""
    res = score("", model_slug="selftest-stub", project=SELFTEST / "stub")
    print(json.dumps({"passed": res.passed, "score": res.score, "checks": res.checks,
                      **{k: v for k, v in res.details.items() if k.startswith(("hidden_", "start", "tests"))}},
                     indent=2, default=str))
    want = {"build": True, "rust_only": True, "own_tests": True, "starts": True,
            "crud": False, "permissions": False, "queries": False}
    ok = all(res.checks.get(k) is v for k, v in want.items())
    print("selftest:", "ok" if ok else "UNEXPECTED")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        raise SystemExit(selftest())
    raise SystemExit(cli(score))
