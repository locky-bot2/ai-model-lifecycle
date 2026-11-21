"""tests/test_real_suite.py — the `real` suite (r1b JHipster, r2 GWT→Angular) plumbing.

Offline: no model call, no Docker. The r1b/r2 scorers' Maven/Angular/browser
stages are validated by hand (see scorers/fixtures/README.md); here we check
config, dispatch, the EDIT format and the scorers' output parsers.

    pytest -q tests/test_real_suite.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from common import load_config
from runner import build_prompt
from scorers import r1b_scorer, r2_scorer
from scorers.base import apply_edits, apply_output, parse_edits
from scorers.dispatch import SCORER_MAP, score_case

REAL = load_config(suite="real")


# --------------------------------------------------------------------------- #
# suite config                                                                 #
# --------------------------------------------------------------------------- #
def test_real_suite_config():
    assert REAL.suite == "real"
    assert REAL.cases == ["r1b_jhipster_boot3", "r2_gwt_to_angular"]
    assert REAL.max_tokens == 128000         # suite override; sanity keeps 32000
    assert REAL.max_tokens_for("anthropic/claude-haiku-4.5") == 64000      # its Bedrock maximum
    assert REAL.max_tokens_for("anthropic/claude-sonnet-5.5") == 128000
    assert REAL.timeout_s == 1800
    assert REAL.report_name == "REPORT.real.md"
    sanity = load_config()
    assert sanity.suite == "sanity" and sanity.report_name == "REPORT.md"
    assert sanity.max_tokens == 32000 and "r1b_jhipster_boot3" not in sanity.cases
    assert sanity.suites == ["sanity", "real", "real-screen"]


def test_unknown_suite_is_an_error():
    with pytest.raises(KeyError, match="known: sanity, real"):
        load_config(suite="nope")


def test_real_cases_have_a_scorer():
    for case in REAL.cases:
        assert SCORER_MAP[case] == f"scorers.{case.split('_')[0]}_scorer"


def test_real_prompts_inline_the_sources():
    p = build_prompt("r1b_jhipster_boot3")
    assert "--- ARTIFACT: project/pom.xml ---" in p
    assert "--- ARTIFACT: project/src/main/java/io/github/jhipster/sample/config/SecurityConfiguration.java ---" in p
    assert "ArchUnit 1.x" in p                      # the hidden suite's one test-dependency need
    assert "src/test" not in "".join(l for l in p.splitlines() if l.startswith("--- ARTIFACT"))
    p = build_prompt("r2_gwt_to_angular")
    assert "--- ARTIFACT: e2e/resources/com/gwtplatform/carstore/cucumber/Manufacturers.feature ---" in p
    assert "--- ARTIFACT: workspace/src/main.ts ---" in p


def test_report_ignores_runs_of_the_other_suite(tmp_path, monkeypatch):
    """A `--suite real` run is not a 'partial' sanity run, and vice versa."""
    import common
    import report

    d = tmp_path / "p"
    d.mkdir()
    sanity = load_config()
    for case in sanity.cases:
        (d / f"m.{case}.20261009T000000Z.json").write_text(json.dumps({"case_id": case}))
    (d / "m.r2_gwt_to_angular.20261013T020049Z.json").write_text(json.dumps({"case_id": "r2_gwt_to_angular"}))
    monkeypatch.setattr(common, "RUNS_DIR", tmp_path)
    assert report.suite_run_ids(sanity, "p") == ["20261009T000000Z"]
    assert report.suite_run_ids(REAL, "p") == ["20261013T020049Z"]


# --------------------------------------------------------------------------- #
# EDIT blocks                                                                  #
# --------------------------------------------------------------------------- #
ANSWER = """\
### EDIT: src/A.java
```java
<<<<<<< SEARCH
import javax.persistence.*;
=======
import jakarta.persistence.*;
>>>>>>> REPLACE
<<<<<<< SEARCH
    int x = 1;
=======
    int x = 2;
>>>>>>> REPLACE
```

### FILE: src/New.java
```java
class New {}
```

### EDIT: project/src/B.java
```java
<<<<<<< SEARCH
not in the file
=======
whatever
>>>>>>> REPLACE
```
### DELETE: src/Old.java
"""


def test_parse_edits_splits_sections_and_blocks():
    edits = parse_edits(ANSWER)
    assert [(e.path, e.search) for e in edits] == [
        ("src/A.java", "import javax.persistence.*;\n"),
        ("src/A.java", "    int x = 1;\n"),
        ("project/src/B.java", "not in the file\n"),
    ]
    assert edits[0].replace == "import jakarta.persistence.*;\n"


def test_apply_output_edits_writes_and_deletes(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/A.java").write_text("import javax.persistence.*;\nclass A {\n    int x = 1;   \n}\n")
    (tmp_path / "src/B.java").write_text("class B {}\n")
    (tmp_path / "src/Old.java").write_text("class Old {}\n")
    out = apply_output(ANSWER, tmp_path, strip_prefix="project/")
    # trailing whitespace in the file ("int x = 1;   ") still matches
    assert (tmp_path / "src/A.java").read_text() == "import jakarta.persistence.*;\nclass A {\n    int x = 2;\n}\n"
    assert out.written == ["src/New.java"] and out.deleted == ["src/Old.java"]
    assert out.edited == ["src/A.java", "src/A.java"]
    assert out.edit_failures == ["src/B.java: SEARCH text not found (starts 'not in the file')"]
    assert (tmp_path / "src/B.java").read_text() == "class B {}\n"     # a failed edit changes nothing


def test_apply_edits_refuses_escapes_and_creates_new_files(tmp_path):
    from scorers.base import Edit

    applied, failures = apply_edits([
        Edit("../outside.txt", "", "x"),
        Edit("new/File.txt", "", "hello\n"),
        Edit("missing.txt", "something", "x"),
    ], tmp_path)
    assert applied == ["new/File.txt"] and (tmp_path / "new/File.txt").read_text() == "hello\n"
    assert failures == ["../outside.txt: path escapes the project", "missing.txt: file not found"]
    assert not (tmp_path.parent / "outside.txt").exists()


# --------------------------------------------------------------------------- #
# r1b scorer                                                                   #
# --------------------------------------------------------------------------- #
def test_r1b_hidden_tests_match_the_promised_counts():
    """The fixture must hold the suite the prompt describes (52 unit + 140 IT)."""
    java = r1b_scorer.HIDDEN_TESTS / "java"
    tests = sum(f.read_text().count("@Test\n") + f.read_text().count("@ArchTest\n") for f in java.rglob("*.java"))
    assert tests == r1b_scorer.MIN_UNIT + r1b_scorer.MIN_IT == 192
    assert (r1b_scorer.HIDDEN_TESTS / "resources/config/application.yml").is_file()
    leftovers = [str(f) for f in java.rglob("*.java") if r1b_scorer._JAVAX_EE_RE.search(f.read_text())]
    assert leftovers == []


def test_r1b_parsers():
    pom = "<properties><java.version>17</java.version><spring-boot.version>3.1.5</spring-boot.version>"
    assert r1b_scorer.boot_version(pom) == "3.1.5" and r1b_scorer.java_version(pom) == 17
    assert r1b_scorer.boot_version("<parent><artifactId>spring-boot-starter-parent</artifactId>\n"
                                   "  <version>3.2.0</version></parent>") == "3.2.0"
    mvn = ("[INFO] Tests run: 3, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 1 s - in x.Y\n"
           "[INFO] Tests run: 52, Failures: 0, Errors: 0, Skipped: 0\n"
           "[ERROR] Tests run: 140, Failures: 1, Errors: 2, Skipped: 0\n")
    assert r1b_scorer.test_summaries(mvn) == [(52, 0, 0), (140, 1, 2)]   # per-class lines are not summaries
    ok = "\x1b[32m  ✔  All specs passed!\x1b[39m        02:10       54       54        -        -        -"
    bad = "  ✖  2 of 15 failed (13%)                    02:10       54       51        3        -        -"
    assert r1b_scorer.cypress_totals(ok) == (54, 54, 0)
    assert r1b_scorer.cypress_totals(bad) == (54, 51, 3)
    assert r1b_scorer.cypress_totals("no table") is None


def test_r1b_javax_check_ignores_comments_and_unmoved_packages(tmp_path):
    src = tmp_path / "src/main/java"
    src.mkdir(parents=True)
    (src / "A.java").write_text(
        "import javax.sql.DataSource;\n"            # did not move
        "import javax.annotation.Nonnull;\n"        # JSR-305, did not move
        "// import javax.persistence.Entity;\n"     # comment
        "import javax.annotation.PostConstruct;\n"  # moved
        "import javax.persistence.Entity;\n"        # moved
    )
    assert [h.split(": ", 1)[1] for h in r1b_scorer.javax_hits(tmp_path)] == [
        "import javax.annotation.PostConstruct;", "import javax.persistence.Entity;"]


def test_r1b_reference_answer_passes_the_static_checks(tmp_path):
    """The known-good answer (tests/r1b_reference_answer.txt) applies cleanly and
    clears every check before the build. Its build and test stages run in
    tests/test_r1b_reference_slow.py (GATE1_SLOW_TESTS=1)."""
    answer = (Path(__file__).parent / "r1b_reference_answer.txt").read_text(encoding="utf-8")
    shutil.copytree(r1b_scorer.PROJECT, tmp_path, dirs_exist_ok=True)
    applied = apply_output(answer, tmp_path, strip_prefix="project/")
    assert applied.edit_failures == []
    pom = (tmp_path / "pom.xml").read_text(encoding="utf-8")
    assert r1b_scorer.boot_version(pom).startswith("3.") and r1b_scorer.java_version(pom) == 17
    assert r1b_scorer.javax_hits(tmp_path) == []
    # the three hand fixes from cases/r1b_jhipster_boot3/NEAR_MISS.md are in place
    assert "<artifactId>jackson-datatype-problem</artifactId>" in pom
    sec = (tmp_path / "src/main/java/io/github/jhipster/sample/config/SecurityConfiguration.java").read_text()
    assert sec.index(".frameOptions(") < sec.index(".permissionsPolicy(")
    assert "queue-size" not in (tmp_path / "src/main/resources/config/application-dev.yml").read_text()


def test_r1b_no_blocks_fails_without_building():
    res = score_case("r1b_jhipster_boot3", "I migrated it, trust me.")
    assert not res.passed and "no `### FILE:` or `### EDIT:` blocks" in res.reason


# --------------------------------------------------------------------------- #
# r2 scorer                                                                    #
# --------------------------------------------------------------------------- #
def test_r2_parity_counts(tmp_path):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"stats": {"expected": 7, "unexpected": 1, "flaky": 0}}))
    assert r2_scorer.parity_counts(report) == (7, 1)
    # Playwright's "flaky": failed, then passed on its one retry. A pass, not a
    # failure: one flaky failure in seven scorings once failed a working port
    # (GLM-5.3 r2, 2026-11-01). Which tests were flaky is recorded separately.
    report.write_text(json.dumps({"stats": {"expected": 7, "unexpected": 0, "flaky": 1}}))
    assert r2_scorer.parity_counts(report) == (8, 0)
    assert r2_scorer.parity_counts(tmp_path / "missing.json") == (0, 0)


def _pw_spec(title, status, retries=0):
    return {"title": title, "tests": [{"status": status,
                                       "results": [{"retry": i} for i in range(retries + 1)]}]}


def test_r2_parity_names_the_failed_and_flaky_tests(tmp_path):
    """Playwright's JSON report nests suites (file > describe > spec); the
    scorer records which tests failed and which passed only on their retry."""
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"stats": {"expected": 6, "unexpected": 1, "flaky": 1}, "suites": [
        {"title": "parity.spec.ts", "specs": [_pw_spec("Reports show the average", "expected")],
         "suites": [
             {"title": "Manufacturers", "specs": [
                 _pw_spec("add then save appends the manufacturer", "flaky", retries=1),
                 _pw_spec("editing the first manufacturer updates it", "expected")]},
             {"title": "Ratings", "specs": [
                 _pw_spec("deleting the first rating removes a row", "unexpected", retries=1)]}]}]}))
    assert r2_scorer.parity_outcomes(report) == {
        "failed": ["Ratings › deleting the first rating removes a row"],
        "flaky": ["Manufacturers › add then save appends the manufacturer"]}
    assert r2_scorer.parity_outcomes(tmp_path / "missing.json") == {"failed": [], "flaky": []}


def test_r2_parity_suite_retries_a_failed_test_once():
    config = (r2_scorer.PARITY / "playwright.config.ts").read_text()
    assert "retries: 1," in config


def test_r2_fixed_files_exist_and_parity_suite_has_8_tests():
    for rel in r2_scorer.FIXED_FILES:
        assert (r2_scorer.WORKSPACE / rel).is_file(), rel
    spec = (r2_scorer.PARITY / "parity.spec.ts").read_text()
    assert spec.count("test(") == r2_scorer.MIN_PARITY == 8


def test_r2_static_checks_without_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(r2_scorer, "cache_problem", lambda: "missing everything (UNVERIFIED)")
    answer = ("### FILE: src/app/app.component.ts\n```ts\nexport class AppComponent {}\n```\n"
              "### FILE: workspace/src/app/app.config.ts\n```ts\nexport const appConfig = {};\n```\n"
              "### FILE: package.json\n```json\n{\"name\": \"hacked\"}\n```\n")
    res = r2_scorer.score(answer, workdir=tmp_path / "ws")
    assert res.checks == {"edits_applied": True, "has_app": True, "build": False, "parity": False,
                          "integration": False}
    assert not res.passed and "unverified" in res.reason
    # the fixed toolchain files are restored, whatever the answer wrote
    assert json.loads((tmp_path / "ws/package.json").read_text())["name"] != "hacked"


# --------------------------------------------------------------------------- #
# verify_failures evidence                                                     #
# --------------------------------------------------------------------------- #
def test_verify_failures_explains_real_suite_failures():
    from scorers.base import ScoreResult
    from verify_failures import _evidence

    r1b = ScoreResult("r1b_jhipster_boot3", checks={"build": True, "integration_tests": False}, details={
        "edit_failures": ["pom.xml: SEARCH text not found (starts '<x>')"],
        "tests_run": {"unit": 52, "integration": 140, "expected_at_least": [52, 140]},
        "build_errors": ["[ERROR] Tests run: 140, Failures: 1"]})
    ev = _evidence("r1b_jhipster_boot3", r1b, [])
    assert ev[0] == "failed checks: integration_tests"
    assert any(e.startswith("edits that did not apply") for e in ev)
    assert any(e.startswith("build: [ERROR] Tests run: 140") for e in ev)
    assert any(e.startswith("tests_run: ") for e in ev)

    r2 = ScoreResult("r2_gwt_to_angular", checks={"build": False, "parity": False}, details={
        "build_tail": "x\nsrc/app/a.ts:3:1 - error TS2304: Cannot find name 'Foo'.\ny"})
    assert _evidence("r2_gwt_to_angular", r2, []) == [
        "failed checks: build, parity", "ng build: src/app/a.ts:3:1 - error TS2304: Cannot find name 'Foo'."]


def test_scorer_run_keeps_output_on_timeout():
    for mod in (r1b_scorer, r2_scorer):
        rc, out = mod._run(["bash", "-c", "echo spec-1 passed; sleep 5"], timeout=1)
        assert rc == 124 and "spec-1 passed" in out and out.rstrip().endswith("...")


def test_r1b_http_status_reports_error_codes():
    import http.server
    import threading

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/ok" else 401)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{srv.server_port}"
        assert r1b_scorer.http_status(base + "/ok") == 200
        assert r1b_scorer.http_status(base + "/") == 401
    finally:
        srv.shutdown()
    assert r1b_scorer.http_status("http://127.0.0.1:9/") is None


def test_run_command_does_not_wait_for_leftover_children():
    """Cypress leaves a browser helper behind holding its stdout: the scorer must not wait for it."""
    import time

    from scorers.base import run_command

    t = time.time()
    rc, out = run_command(["bash", "-c", "sleep 30 & echo done"], timeout=20)
    assert rc == 0 and out.strip() == "done" and time.time() - t < 10
    assert run_command(["no-such-binary-xyz"]) == (127, "command not found: no-such-binary-xyz")


# --------------------------------------------------------------------------- #
# thinking budget                                                              #
# --------------------------------------------------------------------------- #
def test_real_suite_caps_thinking_and_sanity_does_not():
    assert REAL.reasoning == {"effort": "medium"}
    assert load_config().reasoning is None


def test_call_sends_thinking_budget_and_records_thinking_tokens(tmp_path, monkeypatch):
    import sys
    import types

    import common
    import runner

    calls = []

    def completion(**kw):
        calls.append(kw)
        msg = types.SimpleNamespace(content="### FILE: a\n```\nx\n```\n")
        usage = {"prompt_tokens": 10, "completion_tokens": 900, "total_tokens": 910, "cost": 0.01,
                 "completion_tokens_details": {"reasoning_tokens": 700}}
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg, finish_reason="stop")],
                                     usage=usage, provider="Amazon Bedrock")

    monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(drop_params=False, completion=completion))
    monkeypatch.setenv("OPENROUTER_TOKEN", "sk-or-v1-test")
    monkeypatch.setattr(common, "RUNS_DIR", tmp_path)
    pair = REAL.get_pair("haiku-4.5-vs-5.5")
    res = runner.run_case(REAL, pair.id, "r2_gwt_to_angular", pair.target, "target", run_id="20261013T000000Z")
    assert calls[0]["extra_body"]["reasoning"] == {"effort": "medium"}
    assert calls[0]["max_tokens"] == 128000                              # Haiku 5.5 (target)
    assert res.max_tokens == 128000
    assert res.reasoning_requested == {"effort": "medium"} and res.reasoning_tokens == 700

    runner.run_case(REAL, pair.id, "r2_gwt_to_angular", pair.current, "current", run_id="20261013T000002Z")
    assert calls[1]["max_tokens"] == 64000                               # Haiku 4.5: its maximum

    sanity = load_config()
    runner.run_case(sanity, pair.id, "r3_oracle_to_postgres", pair.target, "target", run_id="20261013T000001Z")
    assert "reasoning" not in calls[2]["extra_body"]                     # default behavior untouched
    assert calls[2]["max_tokens"] == 32000


def test_report_shows_thinking_budget_and_tokens():
    import report

    base = {"case_id": "r2_gwt_to_angular", "ok": True, "output_text": "", "latency_s": 1.0,
            "billed_cost_usd": 0.1, "provider": "Amazon Bedrock", "_run": "20261013T000000Z",
            "reasoning_requested": {"effort": "medium"}}
    pair = REAL.get_pair("haiku-4.5-vs-5.5")
    runs = [dict(base, role="current", model_slug=pair.current.id, output_tokens=100, reasoning_tokens=0,
                 max_tokens=64000),
            dict(base, role="target", model_slug=pair.target.id, output_tokens=900, reasoning_tokens=700,
                 max_tokens=128000)]
    md = report.render_pair(REAL, pair.id, report.aggregate(runs, score=False), runs, score=False)
    assert '> Thinking budget sent: {"effort": "medium"}' in md
    assert "> Output limit (max_tokens): current 64,000 · target 128,000" in md
    assert "| · of which thinking | 0 | 700 |" in md


def test_apply_edits_matches_a_unique_fragment_inside_a_line(tmp_path):
    from scorers.base import Edit

    (tmp_path / "R.java").write_text(
        "class R {\n"
        "    List<U> all(@org.springdoc.api.annotations.ParameterObject Pageable p) { return x; }\n"
        "    int a = 1; int b = 1;\n"
        "}\n")
    applied, failures = apply_edits([
        # a fragment of a line, unique in the file: replaced in place
        Edit("R.java", "@org.springdoc.api.annotations.ParameterObject\n",
             "@org.springdoc.core.annotations.ParameterObject\n"),
        # a fragment that occurs twice is ambiguous: refused, file unchanged there
        Edit("R.java", " = 1\n", " = 2\n"),
    ], tmp_path)
    assert applied == ["R.java"]
    assert failures == ["R.java: SEARCH text not found (starts ' = 1')"]
    assert (tmp_path / "R.java").read_text() == (
        "class R {\n"
        "    List<U> all(@org.springdoc.core.annotations.ParameterObject Pageable p) { return x; }\n"
        "    int a = 1; int b = 1;\n"
        "}\n")


def test_apply_edits_ignores_indentation_when_unambiguous(tmp_path):
    from scorers.base import Edit

    (tmp_path / "pom.xml").write_text(
        "<properties>\n"
        "        <liquibase.version>4.15.0</liquibase.version>\n"
        "        <liquibase-hibernate5.version>4.15.0</liquibase-hibernate5.version>\n"
        "</properties>\n"
        "<a>\n    <x>1</x>\n</a>\n<b>\n    <x>1</x>\n</b>\n")
    applied, failures = apply_edits([
        Edit("pom.xml",                                   # indentation dropped, unique
             "<liquibase.version>4.15.0</liquibase.version>\n"
             "<liquibase-hibernate5.version>4.15.0</liquibase-hibernate5.version>\n",
             "        <liquibase.version>4.24.0</liquibase.version>\n"
             "        <liquibase-hibernate6.version>4.24.0</liquibase-hibernate6.version>\n"),
        Edit("pom.xml", "<x>1</x>\n</a>\n<b>\n<x>1</x>\n", "gone\n"),   # unique window: applies
        Edit("pom.xml", "<y>\n", "z\n"),                              # nowhere: still fails
    ], tmp_path)
    assert applied == ["pom.xml", "pom.xml"] and failures == ["pom.xml: SEARCH text not found (starts '<y>')"]
    assert (tmp_path / "pom.xml").read_text() == (
        "<properties>\n"
        "        <liquibase.version>4.24.0</liquibase.version>\n"
        "        <liquibase-hibernate6.version>4.24.0</liquibase-hibernate6.version>\n"
        "</properties>\n"
        "<a>\n    gone\n</b>\n".replace("    gone", "gone"))
    from scorers.base import _unique_dedented_match
    assert _unique_dedented_match("<a>\n  <x/>\n</a>\n<b>\n  <x/>\n</b>\n", "<x/>\n") is None   # twice: refused


# --------------------------------------------------------------------------- #
# case sources fetched from the forks (cases/sources.py)                       #
# --------------------------------------------------------------------------- #
def test_real_case_sources_are_pinned_forks_and_not_committed():
    from cases import sources

    lock = sources._lock()
    # r8 reuses r7's pinned shogun-core (its own files are the reference app,
    # the schema and the prompt, committed): it has no sources of its own
    reuses = {"r8_shogun_rust"}
    assert set(lock) == (set(REAL.cases) | set(load_config(suite="real-screen").cases)) - reuses
    for case_id, srcs in lock.items():
        for s in srcs:
            assert s["repo"].startswith("https://github.com/abralock/")
            # provenance: the project it was forked from, and the branch of the commit
            assert s["upstream"].startswith("https://github.com/") and s["branch"]
            assert s["upstream"].rsplit("/", 1)[1] == s["repo"].rsplit("/", 1)[1]
            assert len(s["commit"]) == 40                  # a full SHA, not a movable tag/branch
            tracked = subprocess.run(["git", "ls-files", str(sources.CASES_DIR / case_id / s["to"])],
                                     capture_output=True, text=True, check=True).stdout
            assert tracked == "", f"{case_id}/{s['to']} must be fetched, not committed"


def test_real_prompts_match_the_committed_runs():
    """Fetched sources + the runner rebuild exactly the prompt the committed runs
    were made with, so new runs stay comparable with them."""
    from common import RUNS_DIR

    for case in REAL.cases:
        stored = {json.loads(f.read_text())["prompt"]
                  for f in RUNS_DIR.glob(f"*/*.{case}.20261013T130717Z*.json")}
        assert len(stored) == 1
        assert hashlib.sha256(build_prompt(case).encode()).digest() == \
            hashlib.sha256(stored.pop().encode()).digest()


def test_changed_case_source_is_refused(tmp_path, monkeypatch):
    from cases import sources

    lock = {"c": [{"repo": "x", "commit": "0" * 40, "from": "", "to": "p",
                   "files": {"a.txt": hashlib.sha256(b"good").hexdigest()}}]}
    (tmp_path / "sources.lock.json").write_text(json.dumps(lock))
    monkeypatch.setattr(sources, "CASES_DIR", tmp_path)
    monkeypatch.setattr(sources, "LOCK_FILE", tmp_path / "sources.lock.json")
    assert sources.problems("c") == ["missing c/p/a.txt"]
    (tmp_path / "c" / "p").mkdir(parents=True)
    (tmp_path / "c" / "p" / "a.txt").write_bytes(b"good")
    assert sources.problems("c") == []
    sources.ensure("c")                                    # present and exact: no fetch
    (tmp_path / "c" / "p" / "a.txt").write_bytes(b"edited")
    with pytest.raises(sources.SourceError, match="differ from the pinned fork commit"):
        sources.ensure("c")
    sources.ensure("not_locked")                           # sanity cases: nothing to do


# --------------------------------------------------------------------------- #
# test counts per kind (details["tests"]): partial results for reports         #
# --------------------------------------------------------------------------- #
def test_r1b_records_unit_and_integration_counts_and_suites_that_never_ran():
    res = r1b_scorer.ScoreResult(case_id="r1b_jhipster_boot3")
    # surefire ran 52 (1 failure, 1 error); the build then stopped before failsafe
    r1b_scorer.record_maven_tests(res, [(52, 1, 1)])
    assert res.details["tests"] == {
        "unit": {"passed": 50, "total": 52, "ran": True},
        "integration": {"passed": 0, "total": 140, "ran": False}}


def test_r1b_records_e2e_counts_or_not_run():
    res = r1b_scorer.ScoreResult(case_id="r1b_jhipster_boot3")
    r1b_scorer.record_e2e_tests(res, (54, 53, 1))
    assert res.details["tests"]["e2e"] == {"passed": 53, "total": 54, "ran": True}
    r1b_scorer.record_e2e_tests(res, None)
    assert res.details["tests"]["e2e"] == {"passed": 0, "total": 54, "ran": False}


def test_r2_records_parity_as_e2e_and_counts_skipped_tests_as_not_passed():
    res = r2_scorer.ScoreResult(case_id="r2_gwt_to_angular")
    r2_scorer.record_parity_tests(res, passed=6, failed=1)      # 1 skipped after a failure
    assert res.details["tests"]["e2e"] == {"passed": 6, "total": 8, "ran": True}
    r2_scorer.record_parity_tests(res, passed=0, failed=0, ran=False)
    assert res.details["tests"]["e2e"] == {"passed": 0, "total": 8, "ran": False}


def test_r1_records_hidden_test_counts_from_surefire():
    from scorers import r1_scorer
    res = r1_scorer.ScoreResult(case_id="r1_springboot2to3")
    out = "[INFO] Tests run: 4, Failures: 0, Errors: 0, Skipped: 0\n[INFO] Tests run: 9, Failures: 1, Errors: 0, Skipped: 0\n"
    r1_scorer.record_hidden_tests(res, out)
    assert res.details["tests"]["unit"] == {"passed": 8, "total": 9, "ran": True}
    r1_scorer.record_hidden_tests(res, None)
    assert res.details["tests"]["unit"] == {"passed": 0, "total": r1_scorer.expected_test_count(),
                                            "ran": False}


def test_r2_integration_suite_checks_the_ui_against_the_api_on_its_own_server():
    """Every UI action is checked against the REST API (a port that only
    changes its tables in the browser fails), and each suite runs on its own
    freshly seeded server so their data changes never meet."""
    spec = (r2_scorer.PARITY / "integration.spec.ts").read_text()
    import re
    assert len(re.findall(r"^\s*test\('", spec, re.M)) == r2_scorer.MIN_INTEGRATION == 7
    assert "apiUrl(" in spec and "'/manufacturers'" in spec and "'/ratings'" in spec
    assert r2_scorer.SUITES == {"parity": ("parity.spec.ts", 8, "e2e"),
                                "integration": ("integration.spec.ts", 7, "integration")}


def test_r2_requires_the_integration_suite(monkeypatch):
    """A port that passes the 8 parity tests but not the API checks fails."""
    monkeypatch.setattr(r2_scorer, "cache_problem", lambda: None)
    monkeypatch.setattr(r2_scorer, "build_angular", lambda ws, res: ws)
    monkeypatch.setattr(r2_scorer, "run_parity", lambda *a: True)

    def integration(base, dist, res):
        r2_scorer.record_tests(res, "integration", passed=5, total=7)
        res.details["integration_tests"] = {"passed": 5, "failed": 2, "flaky": 0, "expected": 7}
        return False

    monkeypatch.setattr(r2_scorer, "run_integration", integration)
    answer = ("### FILE: src/app/app.component.ts\n```\nexport class AppComponent {}\n```\n"
              "### FILE: src/app/app.config.ts\n```\nexport const appConfig = {};\n```\n")
    res = r2_scorer.score(answer)
    assert not res.passed and res.checks["parity"] and not res.checks["integration"]
    assert "integration 5 passed, 2 failed" in res.reason
    assert res.details["tests"]["integration"] == {"passed": 5, "total": 7, "ran": True}
