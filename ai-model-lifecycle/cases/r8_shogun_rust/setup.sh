#!/bin/sh
# Build r8's Maven cache: everything the reference server needs to run offline.
#
#   sh cases/r8_shogun_rust/setup.sh      (from ai-model-lifecycle/; Docker running)
#
# r8's behavioural reference is the original shogun-core (the same pinned
# snapshot as r7) running as a webapp: cases/r8_shogun_rust/reference-app/,
# generated from the project's own shogun-core-webapp-archetype and patched
# (see reference-app/R8_PATCHES.md). Starting from r7's cache (r7's setup.sh,
# which holds the three libraries only terrestris's Nexus serves), this
# installs the original shogun-core into the cache, then starts the reference
# app once against a throwaway PostgreSQL so that Jetty, the PostgreSQL driver
# and every plugin resolve; after that it runs with `mvn -o`.
#
# Output: $GATE1_CACHE/r8_shogun_rust/m2 (default ~/.cache/ai-model-lifecycle).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
cache="${GATE1_CACHE:-$HOME/.cache/ai-model-lifecycle}"
r7m2="$cache/r7_shogun_hibernate6/m2"
m2="$cache/r8_shogun_rust/m2"
image="maven:3.8-openjdk-8"
if [ -f "$cache/r8_shogun_rust/ready" ]; then
    echo "r8 cache ready: $m2"; exit 0
fi
[ -d "$r7m2/org/geotools/gt-main/22.2" ] || { echo "run cases/r7_shogun_hibernate6/setup.sh first" >&2; exit 1; }
(cd "$root" && "${PYTHON:-python3}" -m cases.sources r7_shogun_hibernate6)
mkdir -p "$m2"
cp -Rn "$r7m2/." "$m2/"
work=$(mktemp -d)
net="r8setup-$$"
cleanup() { docker rm -f "$net-pg" "$net-app" >/dev/null 2>&1 || true
            docker network rm "$net" >/dev/null 2>&1 || true; rm -rf "$work"; }
trap cleanup EXIT
cp -R "$root/cases/r7_shogun_hibernate6/project/." "$work/src/"
cp -R "$here/reference-app/." "$work/app/"
# 1. the original library, installed (no tests: r7's setup already ran them)
docker run --rm -v "$work/src:/w" -v "$m2:/root/.m2/repository" -w /w "$image" \
    mvn -B -ntp -DskipTests install >"$work/install.log" 2>&1 \
    || { tail -30 "$work/install.log"; exit 1; }
# 2. the reference app, started once so that everything it runs with resolves
docker network create "$net" >/dev/null
docker run -d --name "$net-pg" --network "$net" -e POSTGRES_USER=ai -e POSTGRES_PASSWORD=ai \
    -e POSTGRES_DB=aidb postgres:17-alpine >/dev/null
sleep 5
docker run -d --name "$net-app" --network "$net" -e R8_JDBC_URL="jdbc:postgresql://$net-pg:5432/aidb" \
    -v "$work/app:/w" -v "$m2:/root/.m2/repository" -w /w "$image" \
    mvn -B -ntp -DskipTests jetty:run >/dev/null
i=0
until docker logs "$net-app" 2>&1 | grep -q "Started Jetty Server"; do
    if docker logs "$net-app" 2>&1 | grep -qE "BUILD FAILURE|Failed startup"; then
        docker logs "$net-app" 2>&1 | grep -E "ERROR|Caused by" | head -20 >&2; exit 1
    fi
    i=$((i + 1)); [ "$i" -lt 300 ] || { echo "reference app did not start in 15 min" >&2; exit 1; }
    sleep 3
done
touch "$cache/r8_shogun_rust/ready"
echo "r8 cache ready: $m2"
