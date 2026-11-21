"""tests/test_r7_scorer.py — r7 (shogun-core: Hibernate 5 → 6, JUnit 4 → 5) plumbing.

Offline: no model call, no Docker. The scorer's Maven stages are checked by
`python -m scorers.r7_scorer --baseline` (the reference migration must pass
every check); here: registration, the case setup, the static checks and the
output parsers.

    pytest -q tests/test_r7_scorer.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

import agentic
from common import load_config
from scorers import r7_scorer
from scorers.dispatch import SCORER_MAP, score_case

CASE = "r7_shogun_hibernate6"
MODULE = "shogun-core-main"


def _project(root: Path, test_java: str = "", pom: str = "<project/>") -> Path:
    """A minimal tree with the case's layout: parent pom, module pom, one test."""
    (root / MODULE / "src" / "test" / "java" / "x").mkdir(parents=True)
    (root / MODULE / "src" / "main" / "java" / "x").mkdir(parents=True)
    (root / "pom.xml").write_text(pom)
    (root / MODULE / "pom.xml").write_text("<project/>")
    if test_java:
        (root / MODULE / "src" / "test" / "java" / "x" / "ATest.java").write_text(test_java)
    return root


JUPITER_TEST = """package x;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;
class ATest { @Test void works() { assertEquals(1, 1); } }
"""


# --------------------------------------------------------------------------- #
# registration                                                                 #
# --------------------------------------------------------------------------- #
def test_r7_is_registered_on_the_screening_suite_only():
    assert SCORER_MAP[CASE] == "scorers.r7_scorer"
    assert CASE in load_config(suite="real-screen").cases
    assert CASE not in load_config(suite="real").cases          # not on the main board yet
    spec = agentic.CASES[CASE]
    assert spec.deliverables == ["pom.xml", f"{MODULE}/pom.xml", f"{MODULE}/src/**"]
    assert "776" in spec.goal and "QueryRestriction" in spec.goal


def test_r7_never_runs_on_the_main_board():
    cfg = load_config()
    pair = next(p.id for p in cfg.pairs if p.current.api == "claude-code")
    with pytest.raises(ValueError, match="still being screened"):
        agentic.run(cfg, pair, role="current", case=CASE)
    with pytest.raises(ValueError, match="still being screened"):
        agentic.run(cfg, pair, role="current", case="r1b_jhipster_boot3," + CASE)


def test_r7_prompt_pins_the_replacement_api_and_the_test_count():
    prompt = agentic.task_prompt(CASE)
    for needle in ("public interface QueryRestriction<E>",
                   "Predicate toPredicate(Root<E> root, CriteriaQuery<?> query, CriteriaBuilder cb)",
                   "public static SortOrder asc(String property)",
                   "776 tests", "mvn -B -pl shogun-core-main -am verify",
                   "terrestris/shogun, its successor"):
        assert needle in prompt
    assert "### FILE:" not in prompt               # the output-format section is replaced


def test_r7_setup_needs_the_maven_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(agentic, "r7_m2_cache", lambda: tmp_path / "no-cache")
    with pytest.raises(RuntimeError, match="setup.sh"):
        agentic._setup_r7(tmp_path / "ws")


def test_r7_setup_copies_the_project_with_its_junit4_tests_and_seeds_maven(tmp_path, monkeypatch):
    m2 = tmp_path / "m2"
    (m2 / "org" / "geotools" / "gt-main" / "22.2").mkdir(parents=True)
    seeded = []
    monkeypatch.setattr(agentic, "r7_m2_cache", lambda: m2)
    monkeypatch.setattr(agentic, "_seed_m2", lambda m, label="r7": seeded.append(m))
    ws = tmp_path / "ws"
    agentic._setup_r7(ws)
    assert seeded == [m2]
    assert (ws / "pom.xml").is_file() and (ws / "shogun-core-webapp-archetype").is_dir()
    tests = list((ws / MODULE / "src" / "test" / "java").rglob("*Test.java"))
    assert len(tests) >= 50
    assert any("org.junit.Test" in t.read_text() for t in tests)  # the original JUnit 4 suite
    # the grading tests are never in the workspace
    assert not (ws / MODULE / "src" / "test" / "SUITE.json").exists()


# --------------------------------------------------------------------------- #
# static checks                                                                #
# --------------------------------------------------------------------------- #
def test_r7_original_fails_the_static_checks():
    assert len(r7_scorer.javax_hits(r7_scorer.PROJECT)) > 100
    hits = r7_scorer.junit4_hits(r7_scorer.PROJECT)
    assert any("org.junit.Test" in h for h in hits)
    assert any("powermock" in h for h in hits)
    # the parent pom's jacoco <excludes> are not a test exclusion
    assert not any("<exclude" in h for h in hits)


def test_r7_jupiter_tests_pass_the_junit5_check(tmp_path):
    assert r7_scorer.junit4_hits(_project(tmp_path, JUPITER_TEST)) == []


@pytest.mark.parametrize("line", [
    "import org.junit.Test;",
    "import org.junit.Assert;",
    "import static org.junit.Assert.assertEquals;",
    "import org.junit.runner.RunWith;",
    "import org.powermock.api.mockito.PowerMockito;",
])
def test_r7_junit4_or_powermock_in_tests_fails(tmp_path, line):
    hits = r7_scorer.junit4_hits(_project(tmp_path, f"package x;\n{line}\nclass ATest {{}}\n"))
    assert hits and line.split()[-1].rstrip(";") in hits[0]


@pytest.mark.parametrize("marker", [
    "@Disabled", "@Ignore", "@DisabledOnOs(OS.LINUX)", "@EnabledIfSystemProperty(named = \"x\", matches = \"y\")",
    "Assumptions.assumeTrue(false);", "assumeTrue(false);",
])
def test_r7_own_tests_counts_disabled_as_missing(tmp_path, marker):
    java = JUPITER_TEST.replace("@Test void works()", f"{marker} @Test void works()")
    assert r7_scorer.junit4_hits(_project(tmp_path, java))


@pytest.mark.parametrize("pom, flagged", [
    ("<dependency><groupId>junit</groupId><artifactId>junit</artifactId></dependency>", True),
    ("<dependency><artifactId>junit-vintage-engine</artifactId></dependency>", True),
    ("<dependency><artifactId>powermock-module-junit4</artifactId></dependency>", True),
    ("<properties><skipTests>true</skipTests></properties>", True),
    ("<plugin><artifactId>maven-surefire-plugin</artifactId><configuration><excludes>"
     "<exclude>**/HardTest.java</exclude></excludes></configuration></plugin>", True),
    ("<plugin><artifactId>maven-surefire-plugin</artifactId><configuration>"
     "<testFailureIgnore>true</testFailureIgnore></configuration></plugin>", True),
    # fine: excluding JUnit 4 from a library, a jacoco exclude, a comment
    ("<dependency><artifactId>greenmail</artifactId><exclusions><exclusion>"
     "<groupId>junit</groupId><artifactId>junit</artifactId></exclusion></exclusions></dependency>", False),
    ("<plugin><artifactId>jacoco-maven-plugin</artifactId><configuration><excludes>"
     "<exclude>x/**</exclude></excludes></configuration></plugin>", False),
    ("<!-- <artifactId>junit</artifactId> -->", False),
])
def test_r7_pom_checks(tmp_path, pom, flagged):
    hits = r7_scorer.junit4_hits(_project(tmp_path, JUPITER_TEST, f"<project>{pom}</project>"))
    assert bool(hits) is flagged, hits


def test_r7_javax_check_ignores_unmoved_packages_and_comments(tmp_path):
    root = _project(tmp_path, JUPITER_TEST)
    (root / MODULE / "src" / "main" / "java" / "x" / "A.java").write_text(
        "package x;\nimport javax.xml.parsers.DocumentBuilder;\nimport javax.naming.NamingEnumeration;\n"
        "// import javax.persistence.Entity;\nimport jakarta.persistence.Entity;\nclass A {}\n")
    assert r7_scorer.javax_hits(root) == []
    (root / MODULE / "src" / "test" / "java" / "x" / "BTest.java").write_text(
        "package x;\nimport javax.servlet.http.HttpServletRequest;\nclass BTest {}\n")
    assert len(r7_scorer.javax_hits(root)) == 1          # src/test counts too


# --------------------------------------------------------------------------- #
# parsers                                                                      #
# --------------------------------------------------------------------------- #
def test_r7_last_summary_takes_the_final_totals():
    out = ("[INFO] Tests run: 11, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.1 s - in x.ATest\n"
           "[INFO] Results:\n[ERROR] Tests run: 776, Failures: 2, Errors: 1, Skipped: 3\n")
    assert r7_scorer.last_summary(out) == (776, 2, 1, 3)
    assert r7_scorer.last_summary("[ERROR] COMPILATION ERROR") is None
    assert r7_scorer._passes(0, (776, 0, 0, 0), 776)
    assert not r7_scorer._passes(0, (775, 0, 0, 0), 776)       # a test went missing
    assert not r7_scorer._passes(0, (776, 0, 0, 1), 776)       # one skipped
    assert not r7_scorer._passes(1, (776, 0, 0, 0), 776)       # the build failed after the tests


def test_r7_resolved_versions_and_major():
    deps = ("The following files have been resolved:\n"
            "   org.hibernate.orm:hibernate-core:jar:6.4.4.Final:compile -- module org.hibernate.orm.core\n"
            "   org.springframework:spring-core:jar:6.1.14:compile\n"
            "   org.springframework.security:spring-security-core:jar:6.3.4:compile\n"
            "   org.junit.jupiter:junit-jupiter-api:jar:5.10.2:test\n")
    v = r7_scorer.resolved_versions(deps)
    assert v["org.hibernate.orm:hibernate-core"] == "6.4.4.Final"
    assert r7_scorer.major(v["org.springframework:spring-core"]) == 6
    assert r7_scorer.major(None) == 0


def test_r7_class_major_reads_the_bytecode_version(tmp_path):
    classes = tmp_path / MODULE / "target" / "classes" / "x"
    classes.mkdir(parents=True)
    (classes / "A.class").write_bytes(b"\xca\xfe\xba\xbe\x00\x00\x00\x3d" + b"\x00" * 8)   # 61
    assert r7_scorer.class_major(tmp_path) == 61
    assert r7_scorer.class_major(tmp_path / "none") is None


def test_r7_answer_from_tree_lists_changed_new_and_deleted_deliverables(tmp_path):
    import shutil
    ref = tmp_path / "ref"
    shutil.copytree(r7_scorer.PROJECT, ref)
    pom = ref / "pom.xml"
    pom.write_text(pom.read_text().replace("<hibernate.version>5.4.24.Final", "<hibernate.version>6.4.4.Final"))
    new = ref / MODULE / "src" / "main" / "java" / "de" / "terrestris" / "shoguncore" / "dao" / "SortOrder.java"
    new.write_text("package de.terrestris.shoguncore.dao;\npublic final class SortOrder {}\n")
    gone = next((ref / MODULE / "src" / "test" / "java").rglob("*Test.java"))
    gone.unlink()
    (ref / "shogun-core-webapp-archetype" / "pom.xml").write_text("<changed/>")   # not a deliverable
    answer = r7_scorer.answer_from_tree(ref)
    assert "### FILE: pom.xml" in answer and "6.4.4.Final" in answer
    assert f"### FILE: {new.relative_to(ref).as_posix()}" in answer
    assert f"### DELETE: {gone.relative_to(ref).as_posix()}" in answer
    assert "### FILE: shogun-core-webapp-archetype" not in answer


def test_r7_no_blocks_fails_without_building():
    res = score_case(CASE, "I could not finish.")
    assert not res.passed and "no `### FILE:`" in res.reason


# --------------------------------------------------------------------------- #
# the grading suite (scorers/fixtures/r7_hidden_tests)                         #
# --------------------------------------------------------------------------- #
def test_r7_hidden_tests_use_only_public_api():
    """Our grading tests may only depend on what every correct migration has:
    the original project's classes and the prompt's two new types. A test of a
    class the reference invented would grade the reference's design choices."""
    import re
    original = {p.relative_to(r7_scorer.PROJECT / MODULE / "src" / "main" / "java").with_suffix("")
                .as_posix().replace("/", ".")
                for p in (r7_scorer.PROJECT / MODULE / "src" / "main" / "java").rglob("*.java")}
    allowed = original | {"de.terrestris.shoguncore.dao.QueryRestriction",
                          "de.terrestris.shoguncore.dao.SortOrder"}
    test_classes = {p.relative_to(r7_scorer.HIDDEN_TESTS / "java").with_suffix("").as_posix().replace("/", ".")
                    for p in (r7_scorer.HIDDEN_TESTS / "java").rglob("*.java")}
    unknown = set()
    for f in (r7_scorer.HIDDEN_TESTS / "java").rglob("*.java"):
        for imp in re.findall(r"^import (?:static )?(de\.terrestris\.shoguncore\.[\w.]+);", f.read_text(), re.M):
            # a static import names a member: walk up to the class
            parts = imp.split(".")
            hit = any(".".join(parts[:n]) in allowed | test_classes for n in range(len(parts), 3, -1))
            if not hit:
                unknown.add(f"{f.name}: {imp}")
    assert unknown == set()


def test_r7_hidden_tests_are_junit5_with_the_original_resources(tmp_path):
    hidden = r7_scorer.HIDDEN_TESTS
    hits = [h for h in r7_scorer.junit4_hits(_layout(hidden, tmp_path)) if "pom.xml" not in h]
    assert hits == []
    # the test resources (Spring contexts, H2 settings) are the project's own,
    # unchanged except for one added setting: quote identifiers that are keywords
    # (USER, VALUE in H2 2.x), so an H2 upgrade works whether the agent put that
    # setting in its pom (the reference) or in its own test resources
    original = r7_scorer.PROJECT / MODULE / "src" / "test" / "resources"
    added = {"META-INF/hibernate.properties", "META-INF/spring/test-context-dao.xml"}
    for f in original.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(original).as_posix()
        ours = hidden / "resources" / rel
        if rel in added:
            mine, theirs = ours.read_text().splitlines(), f.read_text().splitlines()
            extra = [ln for ln in mine if ln not in theirs]
            assert extra and all("auto_quote_keyword" in ln or ln.startswith("#") for ln in extra), (rel, extra)
            assert set(theirs) <= set(mine), rel
        else:
            assert ours.read_bytes() == f.read_bytes(), rel
    assert int(__import__("json").loads((hidden / "SUITE.json").read_text())["tests"]) >= 776


def _layout(hidden: Path, root: Path) -> Path:
    """junit4_hits reads <root>/shogun-core-main/src/test: point it at the fixture."""
    (root / MODULE / "src").mkdir(parents=True)
    (root / MODULE / "src" / "test").symlink_to(hidden.resolve())
    return root
