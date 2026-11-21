# r8: Port a slice of shogun-core from Java to Rust (draft spec)

Status: **built and run**. Below is the pre-build draft, kept as the design
record. Where it differs from what was built, the built version wins:

* **The contract** is `prompt.md` (what the agent sees); the grading is
  `scorers/r8_scorer.py` and `scorers/fixtures/r8_hidden_tests/`.
* **Slice: six resources**, not four: users, groups, roles, layers, layer data
  sources (ImageWMS, TileWMS, WFS, WMTS, XYZ, with tile grids and extents
  embedded) and layer appearances.
* **Crates come from crates.io** through the egress allowlist
  (`index.crates.io`, `static.crates.io`), not a vendored offline set. The
  agent picks its own crates (both Opus and the Haiku runs used axum).
* **The reference app** is generated from the project's own archetype and
  patched (`reference-app/R8_PATCHES.md`): PostgreSQL, the six endpoints open
  to ROLE_USER so the entity permission evaluators decide, and Hibernate's
  second-level cache off. The agent may run it in its sandbox.
* **Kept limit of the original:** it cannot deserialize the abstract
  `LayerDataSource`, so creating a data source or setting a layer's source is
  refused; XYZ resolutions (Java-serialized bytea) are not checked.
* **Hidden tests: 490 scenarios** (v1: 274), recorded from the original 3x
  and re-passed after a restart in reverse order (`record.sh`). v2 was added
  after Opus 5.5 high and Haiku 5.5 high both passed all of v1; a
  differential cross-check using Opus's own cases showed v1 missed real
  port defects (loose JSON, failed-create ids, map layer order, odd paths,
  group references on account updates).
* **Snapshots** at 1, 2 and 4 h of the 8-hour cap (`agentic.py`).
* **Runs so far** (one attempt each, v2): Opus 5.5 high pass 490/490 (154 min);
  Sonnet 5.5 high fail 483/490 (63 min, no permission failures);
  Haiku 5.5 medium fail 477/490 (63 min); Haiku 5.5 high fail 468/490 (58 min);
  GLM-5.3 high (opencode) fail 463/490 (163 min, $31.57 Go credit).

## 1. Purpose

r7 asks a model to *upgrade* a real Java library in its own language. r8 asks
it to *rewrite* part of the same library in another language, Rust, and keep
the behaviour. It tests a different skill: translating a Spring + Hibernate
design into a language that has neither, not following a migration guide.

It is a capability probe on the screening track, not a main-board task (same
rule as r7: screening results stay on their own track).

## 2. How it relates to r7

| | r7 | r8 |
|---|---|---|
| Source project | terrestris/shogun-core 5.3.14-SNAPSHOT, pinned in `cases/sources.lock.json` | **the same snapshot**, the original Java 8 / Spring 5.3 / Hibernate 5.4 code, not r7's upgraded output |
| What the agent produces | the same Java project, upgraded | a new Rust service for one slice of the API |
| Behavioural reference | the original project | **the original project, running as a server** |
| Grading tests | 792 hidden JUnit 5 tests | hidden **HTTP and database** tests (JUnit can't call Rust) |
| Fairness rule | every hidden test passes on the original | **the same**: every hidden test must pass against the original Java server first |
| Time limit | 60 min | **8-hour safety cap**, not told to the agent |
| Models | 6 attempts | Opus 5.5 high, then Sonnet 5.5 high; GLM-5.3 decided afterwards |

## 3. The slice

The REST API under `/rest` for four entity types, plus the permission model
they share:

| Endpoint | Entity | Why it is in the slice |
|---|---|---|
| `/rest/users` (+ `/{id}/userGroups`) | `User` (extends `Person`, JOINED inheritance) | entity inheritance; many-to-many to roles and groups |
| `/rest/groups` (+ `/{id}/users`) | `UserGroup` | owner, members, roles |
| `/rest/roles` | `Role` | simplest entity; baseline CRUD |
| `/rest/layers`, `/rest/layerdatasources`, `/rest/layerappearances` | `Layer` (JOINED), `LayerDataSource` (JOINED, 5 subtypes: ImageWms, TileWms, Wfs, Wmts, Xyz), `LayerAppearance` | polymorphic JSON and inheritance in the database |

For each, the generic endpoints of `AbstractRestController`:

* `GET /` list, with field restriction from the request parameters (the
  code path of Haiku's r7 **id bug**);
* `GET /filter` simple filter;
* `GET /{id}`, `POST /` (id must be null → 400), `PUT /{id}` (partial update;
  body id must equal path id → 400), `DELETE /{id}`.

Shared behaviour:

* **HTTP Basic auth** on `/rest/**`, as the webapp archetype configures it;
  superadmin role versus default user role.
* **Permissions**: every entity carries user and group permission collections
  (`PersistentObject.userPermissions` / `groupPermissions`). Lists are filtered
  by READ; update needs UPDATE; delete needs DELETE; superadmin bypasses. This
  is the code path of GLM-5.3 medium's r7 **permission-lookup bug**.

So the slice covers all three places r7 attempts broke or nearly broke: field
restriction, permission lookups across entity types, and inheritance.

**Out of scope:** GeoServer interceptors, HTTP proxy, mail, tokens and
registration, LDAP, files and images, importer, the non-REST web controllers,
and every other entity.

*To confirm in build step 1:* that these entities don't pull in others through
their relations (for example a layer's appearance or source referencing
something outside the slice), and the exact endpoint list and status codes, by
running the original.

## 4. What the agent gets

* The original shogun-core source, read-only, as the reference.
* A prompt that pins the **contract**:
  * the endpoints, methods and status codes above;
  * the JSON shapes as the original's Jackson produces them (field names,
    nesting, how subtypes are marked, how permissions appear);
  * Basic auth and the two role names;
  * the **database schema**: the PostgreSQL DDL that the original's Hibernate
    generates. The Rust service must use that schema unchanged, so the
    hidden tests can seed and check data with plain SQL.
* A Rust toolchain at a pinned stable version and a **fixed, vendored crate
  set** (the sandbox is offline, as r7's Maven cache was): axum, tokio, tower,
  sqlx (postgres), serde, serde_json, chrono, the password-hash crate matching
  the original's encoder, base64, thiserror/anyhow, tracing.
* A PostgreSQL instance in the sandbox.
* **Open question:** whether the agent can also start the original Java server
  to compare responses. Recommended: yes. A team porting a service would have
  the old one running, and it tests whether the model uses that.

## 5. Acceptance checks (draft; a pass needs all)

| # | Check | What it verifies |
|---|---|---|
| 1 | Builds | `cargo build --release` passes offline, in Docker, with the pinned toolchain |
| 2 | Really Rust | no JVM, jar or Java process involved; the service is the Rust binary |
| 3 | Own tests | `cargo test` passes (no minimum count; to discuss) |
| 4 | Starts | the binary starts with `DATABASE_URL` and a port, on the pinned schema, and answers within 60 s |
| 5 | Auth | 401 without or with wrong credentials; role rules as the original |
| 6 | CRUD contract | hidden tests: status codes and JSON for every endpoint and entity |
| 7 | Permissions | hidden tests: READ filtering, UPDATE and DELETE allowed or denied per user and group, superadmin |
| 8 | Queries and inheritance | hidden tests: field restriction (including `id`), `/filter`, every data-source subtype |
| 9 | Database state | after each write, the rows in the schema match what the original writes |

Besides pass/fail, the board shows the **share of hidden tests passed**, so a
partial port still shows how far it got.

## 6. Hidden tests

* **Language-neutral:** Python (pytest, requests, psycopg) in its own
  container, given a server URL and a database URL. The same suite runs
  against the original Java server and against the Rust port.
* **Seeded with SQL**, so the tests don't depend on the port's POST working to
  set up other tests.
* **Fair by construction:** every test must pass against the original Java
  server (Java 8, Hibernate 5, PostgreSQL) before it is used. A test the
  original fails is fixed or dropped, as in r7's 14 November corrections.
* **Normalised comparison:** ignore `created`/`modified` timestamps, list
  order where the original doesn't define one, and JSON key order.
* **Never shown to the agent.**
* Rough size: 150–250 tests (an estimate, set when written).
* **Caveat to state on the slide:** I would write these tests, as a Claude
  model. They are checked only against the original's behaviour, not against
  any model's port, but say so.

## 7. Run protocol

1. **Opus 5.5 high:** one attempt, 8-hour cap, Claude Code, subscription.
2. **Sonnet 5.5 high:** the same task, the same cap, even if Opus finishes
   early.
3. **GLM-5.3:** your decision after 1 and 2. I give the expected Go credit
   spend first. At r7's rate of about $17/hour, a long run could cost
   $100–200 or more.

Rules:

* A stop caused by subscription usage limits or quota is an **infrastructure
  stop**, not a model failure; rerun.
* **Progress snapshots:** save the agent's work at 1, 2, 4 and 8 hours and score
  each, for a progress curve (needs a harness change).
* Record the same fields as r7: model, effort, harness, time, turns/requests,
  tokens (fresh, cache read, cache write, output), cost, plus the snapshot
  scores.

## 8. Build work before any run

| Step | Work |
|---|---|
| 1 | Confirm the slice: relations, endpoint list, status codes, JSON shapes |
| 2 | Reference server: a webapp generated from `shogun-core-webapp-archetype`, Java 8, PostgreSQL, in Docker, with seed users and roles |
| 3 | Extract the PostgreSQL DDL the original generates; pin it |
| 4 | Rust image: pinned toolchain, vendored crates, offline build tested |
| 5 | Write the hidden tests; all pass on the original |
| 6 | `scorers/r8_scorer.py`: build, start, run the tests, check the database |
| 7 | Write `cases/r8_.../prompt.md` |
| 8 | Harness: 8-hour cap, PostgreSQL in the sandbox, snapshot scoring |
| 9 | Sanity runs of the scorer: an empty Rust project must fail; the original Java server must pass checks 5–9 |

There is no reference Rust port. Unlike r7, the grading tests don't come from
a model run; the original Java server is the behavioural reference. So the
first Opus run is also the first evidence that the task is achievable.

## 9. Open questions for you

1. Is the slice right: users, groups, roles and layers, plus permissions?
2. Can the agent run the original Java server to compare? (Recommended: yes.)
3. PostgreSQL for both sides instead of the original's H2: fine? (Rust has no
   H2 driver.)
4. A fixed, offline crate set: fine?
5. An 8-hour cap: fine?
6. Must `cargo test` have a minimum number of tests, or only pass?
