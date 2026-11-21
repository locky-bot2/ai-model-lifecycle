# Task: Port part of a real Java library's REST API to Rust

The attached project is a real open-source framework: **SHOGun-Core**
(`de.terrestris:shogun-core`, 5.3.14-SNAPSHOT) by terrestris, the backend
library of a web-GIS platform, on Java 8, Spring Framework 5.3, Spring
Security 5.5 and Hibernate ORM 5.4. `reference/reference-app/` is a webapp
built on it (generated from the project's own archetype); it serves a REST
API under `/rest`, backed by PostgreSQL.

Rewrite one slice of that REST API as a **Rust** service with the **same
behaviour**: the same URLs, status codes and JSON, on the **same database
schema**, so that a client or the database cannot tell the two apart. Spring,
Hibernate and Jackson do not exist in Rust: rebuild what they do (routing,
security, permission checks, queries, JSON mapping, inheritance) yourself.

## The slice

Six resources, each with the generic endpoints of the library's
`AbstractRestController` (`de.terrestris.shoguncore.rest`):

| Path | Entity |
|---|---|
| `/rest/users` | `User` (extends `Person`) |
| `/rest/groups` | `UserGroup` |
| `/rest/roles` | `Role` |
| `/rest/layers` | `Layer` |
| `/rest/layerdatasources` | `LayerDataSource` and its subtypes ImageWMS, TileWMS, WFS, WMTS, XYZ |
| `/rest/layerappearances` | `LayerAppearance` |

For each: `GET /` (list; `output:only=a,b` restricts the fields set), `GET
/filter` (equality filter on fields), `GET /{id}`, `POST /`, `PUT /{id}`
(partial update) and `DELETE /{id}`; and also `GET /rest/users/{id}/userGroups`
and `GET /rest/groups/{id}/users`. Related objects are embedded as the
original embeds them (for example a layer's source with its tile grid and
extent).

Everything else in shogun-core (other entities and controllers, the non-REST
web controllers, GeoServer interceptors, proxy, mail, tokens, LDAP, files,
importer) is out of scope.

## The contract

**The original is the reference.** Where this prompt is silent, the original
app's behaviour decides, including status codes for errors and denied access,
which fields appear in the JSON and how lists, nulls and nested objects look.
Its source is in `reference/` and you can run it (below) and compare.

* **Security**: HTTP Basic on `/rest/**`; accounts are the `users` table
  (inactive users cannot log in), passwords are bcrypt. Roles `ROLE_ADMIN`
  (the super admin: allowed everything) and `ROLE_USER`; every user may call
  the six resources, and the library's entity permission evaluators decide
  per entity (`de.terrestris.shoguncore.security.access`): user and group
  permission collections on every entity, plus the evaluators' own rules (a
  user may always read itself, group members their group, everyone the
  roles, data sources and appearances). Lists are filtered by READ, a single
  entity needs READ, update UPDATE, delete DELETE, create CREATE.
* **Database**: `schema.sql` is the schema the original's Hibernate creates on
  PostgreSQL. Your service must work on it **unchanged**: do not create, alter
  or drop tables. New ids come from `hibernate_sequences` (row `default`), as
  Hibernate's table generator allocates them (new id = `next_val` + 1, then
  `next_val` = the new id), so ids never collide across entity types. Data
  written by your service must be readable by the original and the other way
  round.
* **Known limits of the original, to keep**: it cannot build the abstract
  `LayerDataSource` from JSON, so creating a data source through the API, or
  setting a layer's `source` in a POST or PUT body, is refused as the
  original refuses it. Updating an existing data source's fields works.
* **Not checked**: the XYZ source's resolutions (the original stores them as
  Java-serialized bytes); `created`/`modified` timestamps; the order of
  elements in a list; JSON key order.

## What you deliver

A Cargo project in `rust/` (your `Cargo.toml`, `Cargo.lock` and sources; no
`target/`). It is built with `cargo build --release --locked` with the Rust
toolchain installed here, and started as the only binary target, with:

* `DATABASE_URL` — a PostgreSQL URL (`postgres://user:pass@host:5432/db`) of a
  database that already has `schema.sql` and data;
* `PORT` — the port to listen on, on all interfaces (`0.0.0.0`).

It must answer on `/rest/...` within 60 seconds of starting. The build and
`cargo test` also run with `DATABASE_URL` set (a database with `schema.sql`
loaded and no data), in case your queries are checked at compile time or your
tests need a database. Crates come from
crates.io. The service must be Rust: no JVM, Java code, jar or call out to the
original.

## Acceptance criteria (this is how your work is checked)

1. `cargo build --release --locked` passes in `rust/`.
2. It is a Rust service: no JVM, jar or Java involved.
3. `cargo test --release --locked` passes (your own tests).
4. Started as above on a database with `schema.sql` loaded, it answers on
   `/rest/...` within 60 seconds.
5. to 9. Our own hidden tests, which reset the database to known data,
   call the API as different users and read the database afterwards, give the
   same results against your service as against the original: login and roles;
   create, read, update and delete on every resource; permissions; field
   restriction and filters; and the rows written.
