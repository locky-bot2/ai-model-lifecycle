# How this reference app was made

Generated from the original project's own archetype (r7's pinned snapshot):

    mvn archetype:generate -DarchetypeCatalog=local \
        -DarchetypeGroupId=de.terrestris -DarchetypeArtifactId=shogun-core-webapp-archetype \
        -DarchetypeVersion=5.3.14-SNAPSHOT -DgroupId=de.example -DartifactId=shogunref \
        -Dversion=1.0 -Dpackage=de.example.shogunref -Dwebapp-name=shogunref

then patched. Nothing in shogun-core itself is changed; every behaviour the
hidden tests check is the library's.

The archetype is out of date with the library at this snapshot, so:

1. `pom.xml`: the dependency `de.terrestris:shogun-core` (the parent pom) is
   `shogun-core-main` (the jar).
2. Four generated classes had `{package}.x.Y;` instead of `import ...x.Y;` (an
   archetype template escape that no longer renders); fixed to imports.
3. `ProjectContentInitializer` and `ProjectApplicationPermissionEvaluator` used a
   `LOG` field the library no longer has; each now declares its own logger.

For r8:

4. PostgreSQL instead of H2 (Rust has no H2 driver): the
   `org.postgresql:postgresql` 42.4.3 dependency (the version the parent pom
   manages), `hikari.dataSourceClassName=org.postgresql.ds.PGSimpleDataSource`,
   `hibernate.dialect=de.terrestris.shoguncore.hibernate.ShogunPostgresqlDialect`
   (the library's own), and `jdbc.url`/`username`/`password` from `R8_JDBC_URL`,
   `R8_DB_USER`, `R8_DB_PASSWORD` (defaults: the sandbox's `aidb`, user `ai`).
5. REST security: the archetype's "demo scenario" lets ROLE_USER reach only
   `/rest/users` and keeps everything else for ROLE_ADMIN. For the slice
   (users, groups, roles, layers, layerdatasources, layerappearances) every
   user may call the endpoints and the library's entity permission evaluators
   decide, so permissions are exercised on every entity type of the slice.
6. Hibernate's second-level cache off: the Spring context set a cache region
   factory but never passed `hibernate.cache.use_second_level_cache`, so
   Hibernate's default (on) applied and entities were served from memory after
   the hidden tests had reset the database with SQL. Caching is not part of
   the contract (a port has none); with it off, every request reads the
   database.

Run (Java 8, port 8081):

    R8_JDBC_URL=jdbc:postgresql://host:5432/db mvn -DskipTests jetty:run   (add -o once its dependencies are local)

`hibernate.hbm2ddl.auto=create`: every start drops and recreates the schema
and the archetype's initial content (users admin/shogun and user/shogun,
roles ROLE_ADMIN and ROLE_USER, two groups, two OSM layers).
