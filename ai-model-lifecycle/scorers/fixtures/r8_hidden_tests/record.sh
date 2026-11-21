#!/bin/sh
# Record goldens.json from the original Java shogun-core, then prove them:
#   1. start the reference app fresh and record every scenario 3 times
#      (a scenario whose answers differ between runs is dropped);
#   2. restart it and check every scenario in reverse order: the original must
#      pass all of them, so nothing depends on scenario order or on state a
#      server run kept in memory.
#   sh scorers/fixtures/r8_hidden_tests/record.sh   (from ai-model-lifecycle/; Docker; r8 setup done)
set -eu
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
m2="${GATE1_CACHE:-$HOME/.cache/ai-model-lifecycle}/r8_shogun_rust/m2"
[ -f "$m2/../ready" ] || { echo "run cases/r8_shogun_rust/setup.sh first" >&2; exit 1; }
net="r8rec-$$"; work=$(mktemp -d)
cleanup() { docker rm -f "$net-pg" "$net-app" >/dev/null 2>&1 || true
            docker network rm "$net" >/dev/null 2>&1 || true; rm -rf "$work"; }
trap cleanup EXIT
docker build -q -t gate1-r8-tests:1 "$here" >/dev/null
cp -R "$root/cases/r8_shogun_rust/reference-app/." "$work/"
docker network create "$net" >/dev/null
docker run -d --name "$net-pg" --network "$net" -e POSTGRES_USER=ai -e POSTGRES_PASSWORD=ai \
    -e POSTGRES_DB=aidb postgres:17-alpine >/dev/null
start_app() {
    docker rm -f "$net-app" >/dev/null 2>&1 || true
    docker run -d --name "$net-app" --network "$net" -e R8_JDBC_URL="jdbc:postgresql://$net-pg:5432/aidb" \
        -v "$work:/w" -v "$m2:/root/.m2/repository" -w /w maven:3.8-openjdk-8 \
        mvn -B -ntp -o -DskipTests jetty:run >/dev/null
    i=0
    until docker logs "$net-app" 2>&1 | grep -q "Started Jetty Server"; do
        i=$((i + 1)); [ "$i" -lt 200 ] || { docker logs "$net-app" 2>&1 | tail -30 >&2; exit 1; }
        sleep 3
    done
}
tests() { docker run --rm --network "$net" -v "$here:/tests" gate1-r8-tests:1 \
    --base-url "http://$net-app:8081" --dsn "postgresql://ai:ai@$net-pg:5432/aidb" "$@"; }
# over TCP: the image's first start runs a socket-only init server, then restarts
until docker exec "$net-pg" pg_isready -h 127.0.0.1 -U ai -d aidb >/dev/null 2>&1; do sleep 1; done
start_app
tests --record --repeat 3
start_app
tests --check --reverse --report /tests/reference_check.json
python3 - "$here/reference_check.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
bad = [x for x in r["results"] if not x["passed"]]
print(f"original after a restart, reverse order: {r['passed']}/{r['total']}")
for x in bad[:20]:
    print(" ", x["id"], x["http"] or x["db"])
sys.exit(1 if bad else 0)
PY
