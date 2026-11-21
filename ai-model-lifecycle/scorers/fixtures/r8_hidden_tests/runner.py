"""r8 hidden tests: language-neutral HTTP + database scenarios.

Each scenario starts from seed.sql, sends one or more HTTP requests to the
service under test and, after the last one, reads rows with SQL. What it
observes (status codes, JSON bodies, rows) is compared with goldens.json,
which was recorded from the original Java shogun-core (reference-app) with
`--record`. A scenario is only kept if the original gives the same answer on
every recording run (`--record --repeat N`), so nothing timing- or
order-dependent is graded.

Comparison rules (the original defines no order for these, or a Rust port
cannot reproduce them byte for byte):
  * lists of objects with an integer "id" are compared sorted by id;
  * lists of integers or strings are compared as sorted lists (JPA sets);
    lists of floats keep their order (resolutions are ordered by index);
  * numbers compare numerically (1 == 1.0; floats to 1e-9 relative);
  * object key order is ignored;
  * ids the service allocates (>= 5000: the seed ends below) are replaced by
    their rank within the scenario, so any id allocation that follows the
    contract matches;
  * a body that is not JSON (error pages) is not compared, only its status.

Usage (inside the r8 test image; see Dockerfile):
    python runner.py --base-url URL --dsn DSN --record [--repeat 2]
    python runner.py --base-url URL --dsn DSN --check [--report report.json]
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import psycopg

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scenarios import SCENARIOS  # noqa: E402

SEED = (HERE / "seed.sql").read_text(encoding="utf-8")
GOLDENS = HERE / "goldens.json"
NEW_ID_FLOOR = 5000
PASSWORD = "shogun"


# ------------------------------------------------------------------ requests #
def request(base: str, step: dict) -> dict:
    url = base.rstrip("/") + step["path"]
    data = None
    headers = {"Accept": "application/json"}
    if step.get("user"):
        pw = step.get("password", PASSWORD)
        token = base64.b64encode(f"{step['user']}:{pw}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    if "body" in step:
        body = step["body"]
        data = (body if isinstance(body, str) else json.dumps(body)).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=step["method"], headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    except Exception as e:  # connection refused, timeout: the service is down
        return {"status": None, "error": f"{type(e).__name__}: {e}"}
    try:
        body = json.loads(raw.decode("utf-8")) if raw.strip() else None
        is_json = raw.strip() != b""
    except (ValueError, UnicodeDecodeError):
        body, is_json = None, False
    out = {"status": status}
    if is_json:
        out["json"] = body
    return out


def reset(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(SEED)
    conn.commit()


def query(conn, sql: str) -> list:
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = [list(r) for r in cur.fetchall()]
    conn.commit()
    return [[_db_value(v) for v in r] for r in rows]


def _db_value(v):
    if isinstance(v, (bytes, memoryview)):
        return {"bytes": len(bytes(v))}
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if hasattr(v, "as_integer_ratio") and not isinstance(v, (int, float)):
        return float(v)   # Decimal
    return v


def run_scenario(base: str, conn, sc: dict) -> dict:
    reset(conn)
    steps = [request(base, st) for st in sc["steps"]]
    db = [query(conn, q) for q in sc.get("db", [])]
    return renumber({"steps": steps, "db": db})


# ------------------------------------------------------------- normalising #
def _ints(o, acc):
    if isinstance(o, bool):
        return
    if isinstance(o, int):
        if o >= NEW_ID_FLOOR:
            acc.add(o)
    elif isinstance(o, dict):
        for v in o.values():
            _ints(v, acc)
    elif isinstance(o, list):
        for v in o:
            _ints(v, acc)


def renumber(obs: dict) -> dict:
    """Allocated ids -> "new#1", "new#2"... by size (allocation order)."""
    acc: set[int] = set()
    _ints(obs, acc)
    names = {v: f"new#{i + 1}" for i, v in enumerate(sorted(acc))}

    def walk(o):
        if isinstance(o, bool):
            return o
        if isinstance(o, int) and o in names:
            return names[o]
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        return o
    return walk(obs)


def canon(o):
    if isinstance(o, dict):
        return {k: canon(v) for k, v in o.items()}
    if isinstance(o, list):
        items = [canon(v) for v in o]
        if items and all(isinstance(v, dict) and "id" in v for v in items):
            return sorted(items, key=lambda v: json.dumps(v.get("id"), sort_keys=True))
        if items and all(isinstance(v, (str, int)) and not isinstance(v, bool) for v in items):
            return sorted(items, key=lambda v: (isinstance(v, str), str(v)))
        if items and all(isinstance(v, list) for v in items):   # SQL rows
            return sorted(items, key=lambda v: json.dumps(v, sort_keys=True, default=str))
        return items
    return o


def diff(want, got, path="$") -> str | None:
    """None if equal under the rules above, else where they first differ."""
    if isinstance(want, bool) or isinstance(got, bool):
        return None if want is got else f"{path}: want {want!r}, got {got!r}"
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        if want == got or math.isclose(want, got, rel_tol=1e-9, abs_tol=1e-12):
            return None
        return f"{path}: want {want!r}, got {got!r}"
    if isinstance(want, dict) and isinstance(got, dict):
        if set(want) != set(got):
            missing, extra = sorted(set(want) - set(got)), sorted(set(got) - set(want))
            return f"{path}: keys differ (missing {missing}, extra {extra})"
        for k in want:
            d = diff(want[k], got[k], f"{path}.{k}")
            if d:
                return d
        return None
    if isinstance(want, list) and isinstance(got, list):
        if len(want) != len(got):
            return f"{path}: want {len(want)} items, got {len(got)}"
        for i, (a, b) in enumerate(zip(want, got)):
            d = diff(a, b, f"{path}[{i}]")
            if d:
                return d
        return None
    return None if want == got else f"{path}: want {want!r}, got {got!r}"


def compare(want: dict, got: dict) -> dict:
    """Per part: 'http' (statuses and JSON bodies) and 'db' (rows)."""
    http = None
    for i, (w, g) in enumerate(zip(want["steps"], got["steps"])):
        if g.get("status") != w.get("status"):
            http = f"step {i + 1}: status want {w.get('status')}, got {g.get('status')}" \
                   + (f" ({g['error']})" if g.get("error") else "")
            break
        if "json" in w:
            if "json" not in g:
                http = f"step {i + 1}: want a JSON body, got none or not JSON"
                break
            d = diff(canon(w["json"]), canon(g["json"]), f"step{i + 1}")
            if d:
                http = d
                break
    db = None
    for i, (w, g) in enumerate(zip(want["db"], got["db"])):
        d = diff(canon(w), canon(g), f"db{i + 1}")
        if d:
            db = d
            break
    return {"http": http, "db": db}


# ------------------------------------------------------------------- main #
def wait_ready(base: str, timeout_s: int) -> bool:
    end = time.time() + timeout_s
    while time.time() < end:
        r = request(base, {"method": "GET", "path": "/rest/roles", "user": "admin"})
        if r.get("status") in (200, 401):
            return True
        time.sleep(1)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--dsn", required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true")
    mode.add_argument("--check", action="store_true")
    ap.add_argument("--repeat", type=int, default=2, help="--record: runs that must agree")
    ap.add_argument("--report", default="-")
    ap.add_argument("--ready-timeout", type=int, default=120)
    ap.add_argument("--only", default="", help="comma-separated scenario ids")
    ap.add_argument("--reverse", action="store_true", help="run in reverse order (order-dependence check)")
    a = ap.parse_args()

    only = {s for s in a.only.split(",") if s}
    scenarios = [s for s in SCENARIOS if not only or s["id"] in only]
    if a.reverse:
        scenarios = scenarios[::-1]
    with psycopg.connect(a.dsn) as conn:
        reset(conn)
        if not wait_ready(a.base_url, a.ready_timeout):
            print(json.dumps({"error": "service not ready"}))
            return 2
        if a.record:
            goldens, unstable = {}, []
            for sc in scenarios:
                runs = [run_scenario(a.base_url, conn, sc) for _ in range(a.repeat)]
                c = [compare(runs[0], r) for r in runs[1:]]
                if any(x["http"] or x["db"] for x in c):
                    unstable.append({"id": sc["id"], "why": c})
                    continue
                goldens[sc["id"]] = runs[0]
            reset(conn)
            if only and GOLDENS.exists():   # re-record some: keep the others
                kept = json.loads(GOLDENS.read_text(encoding="utf-8"))
                kept = {k: v for k, v in kept.items() if k not in only}
                goldens = {**kept, **goldens}
            known = {s["id"] for s in SCENARIOS}
            goldens = {k: v for k, v in goldens.items() if k in known}
            GOLDENS.write_text(json.dumps(goldens, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({"recorded": len(goldens), "unstable": unstable}, indent=1))
            return 0
        goldens = json.loads(GOLDENS.read_text(encoding="utf-8"))
        results = []
        for sc in scenarios:
            if sc["id"] not in goldens:
                continue
            got = run_scenario(a.base_url, conn, sc)
            c = compare(goldens[sc["id"]], got)
            results.append({"id": sc["id"], "category": sc["category"],
                            "has_db": bool(sc.get("db")), "http": c["http"], "db": c["db"],
                            "passed": not c["http"] and not c["db"]})
        reset(conn)
    report = {"total": len(results), "passed": sum(r["passed"] for r in results),
              "results": results}
    text = json.dumps(report, indent=1)
    if a.report == "-":
        print(text)
    else:
        Path(a.report).write_text(text, encoding="utf-8")
        print(json.dumps({"total": report["total"], "passed": report["passed"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
