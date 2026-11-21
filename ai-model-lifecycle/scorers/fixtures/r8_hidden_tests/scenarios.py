"""r8 hidden test scenarios. Never shown to the agent.

Each scenario: an id, the category it grades (auth, crud, permissions,
queries; its `db` rows grade the database check), the HTTP steps and the SQL
read after the last step. Expected answers are not written here: they are
recorded from the original Java shogun-core (runner.py --record), so the
original passes every scenario by construction, and a scenario on which the
original is not stable is dropped at recording time.

Seed (seed.sql): roles 1-4; users 10 admin, 11 alice, 12 bob, 13 carol,
14 dave (inactive); groups 20 Editors (alice, bob), 21 Viewers (carol),
22 Empty; data sources 50 ImageWMS, 51 TileWMS, 52 WFS, 53 WMTS, 54 XYZ;
appearances 80-82; layers 40-44 with user and group grants; map 30 showing
layers 40, 42, 43; alice may UPDATE herself, carol READ+UPDATE dave.

v1 (274 scenarios) was passed in full by both Opus 5.5 and Haiku 5.5; a
differential cross-check then found Haiku port defects it did not reach, so
v2 (below the v2 marker) adds loose JSON, ids after failed creates, relation
changes, account updates with group references, deletes that touch maps, odd
paths and more filters: 490 recorded scenarios.
"""

from __future__ import annotations

SCENARIOS: list[dict] = []

ENDPOINTS = ["users", "groups", "roles", "layers", "layerdatasources", "layerappearances"]
SEEDED = {
    "roles": [1, 2, 3, 4],
    "users": [10, 11, 12, 13, 14],
    "groups": [20, 21, 22],
    "layers": [40, 41, 42, 43, 44],
    "layerdatasources": [50, 51, 52, 53, 54],
    "layerappearances": [80, 81, 82],
}
USERS = ["alice", "bob", "carol"]

# rows the database check reads, without created/modified (not in the contract)
DB = {
    "roles": "SELECT id, name, description FROM roles",
    "users": ("SELECT p.id, p.firstname, p.lastname, p.email, p.birthday, p.language, "
              "u.accountname, u.active FROM persons p JOIN users u ON u.id = p.id"),
    "users_roles": "SELECT user_id, role_id FROM users_roles",
    "groups": "SELECT id, name, owner_id FROM usergroups",
    "members": "SELECT usergroup_id, user_id FROM user_usergroup",
    "group_roles": "SELECT usergroup_id, role_id FROM usergroups_roles",
    "layers": "SELECT id, name, description, source_id, appearance_id FROM layers",
    "sources": "SELECT id, name, type, url, format FROM layerdatasources",
    "imagewms": ("SELECT id, customrequestpath, height, width, layernames, layerstyles, "
                 "requestablebypath, version FROM imagewmslayerdatasources"),
    "tilewms": "SELECT id, request_with_tiled, tilegrid_id FROM tilewmslayerdatasources",
    "wfs": "SELECT id, typename, typenames, version FROM wfslayerdatasources",
    "wmts": ("SELECT id, capabilitiesurl, matrixset, projection, requestencoding, wmtslayer, "
             "wmtsstyle, tilegrid_id FROM wmtslayerdatasources"),
    "wmts_urls": "SELECT wmtslayerdatasources_id, urls FROM wmtslayerdatasources_urls",
    "xyz": "SELECT id, center_x, center_y, tilesize, extent_id FROM xyzlayerdatasources",
    "appearances": ("SELECT id, name, attribution, clickable, hoverable, hovertemplate, "
                    "maxresolution, minresolution, opacity, visible FROM layerappearances"),
    "appearance_props": "SELECT appearance_id, property, value FROM layerappearances_properties",
    "next_id_used": "SELECT count(*) FROM hibernate_sequences WHERE next_val > 5000",
    "next_val": "SELECT next_val FROM hibernate_sequences",
    "user_perms": "SELECT entity_id, userpermissions_id, userpermissions_key FROM userpermissions",
    "group_perms": "SELECT entity_id, grouppermissions_id, grouppermissions_key FROM grouppermissions",
    "perm_sets": "SELECT permissioncollections_id, permissions FROM permissioncollections_permissions",
    "map_layers": "SELECT map_id, layer_id, idx FROM maps_layers",
    "tilegrids": "SELECT id, type, tilesize, tilegridextent_id FROM tilegrids",
    "extents": "SELECT id, lowerleft_x, lowerleft_y, upperright_x, upperright_y FROM extents",
}
TABLES_OF = {
    "roles": ["roles", "users_roles", "group_roles"],
    "users": ["users", "users_roles", "members", "groups"],
    "groups": ["groups", "members", "group_roles"],
    "layers": ["layers", "sources", "appearances"],
    "layerdatasources": ["sources", "imagewms", "tilewms", "wfs", "wmts", "wmts_urls", "xyz", "layers"],
    "layerappearances": ["appearances", "appearance_props", "layers"],
}


def R(method, path, user="admin", body=None, password=None):
    st = {"method": method, "path": "/rest" + path, "user": user}
    if body is not None:
        st["body"] = body
    if password is not None:
        st["password"] = password
    return st


def GET(path, user="admin"):
    return R("GET", path, user)


def add(id_, category, steps, db=()):
    SCENARIOS.append({"id": id_, "category": category, "steps": list(steps),
                      "db": [DB[k] if k in DB else k for k in db]})


# ------------------------------------------------------------------ auth #
for ep in ENDPOINTS:
    add(f"auth-none-{ep}", "auth", [R("GET", f"/{ep}", user=None)])
    add(f"auth-wrongpw-{ep}", "auth", [R("GET", f"/{ep}", password="wrong")])
add("auth-inactive", "auth", [GET("/roles", "dave")])
add("auth-unknown-user", "auth", [GET("/roles", "mallory")])
add("auth-ok-user", "auth", [GET("/roles", "alice")])
for u in ["admin", "bob", "carol"]:
    add(f"auth-ok-{u}", "auth", [GET("/roles", u)])
for ep in ENDPOINTS:
    add(f"auth-ok-alice-{ep}", "auth", [GET(f"/{ep}", "alice")])
add("auth-account-name-case", "auth", [GET("/roles", "ALICE")])
add("auth-ok-then-wrong", "auth", [GET("/roles", "bob"), R("GET", "/roles", "bob", password="nope")])
add("auth-none-by-id", "auth", [R("GET", "/layers/40", user=None)])
add("auth-none-post", "auth", [R("POST", "/roles", user=None, body={"name": "ROLE_X"})], db=["roles"])
add("auth-none-delete", "auth", [R("DELETE", "/layers/40", user=None)], db=["layers"])

# ------------------------------------------------------------- crud: reads #
for ep in ENDPOINTS:
    add(f"read-list-{ep}", "crud", [GET(f"/{ep}")])
    for i in SEEDED[ep]:
        add(f"read-{ep}-{i}", "crud", [GET(f"/{ep}/{i}")])
    add(f"read-missing-{ep}", "crud", [GET(f"/{ep}/4999")])
add("read-nonnumeric-id", "crud", [GET("/roles/abc")])
add("read-user-groups-alice", "crud", [GET("/users/11/userGroups")])
add("read-user-groups-carol", "crud", [GET("/users/13/userGroups")])
add("read-user-groups-none", "crud", [GET("/users/10/userGroups")])
add("read-group-users-editors", "crud", [GET("/groups/20/users")])
add("read-group-users-empty", "crud", [GET("/groups/22/users")])

# ------------------------------------------------------------ crud: writes #
add("create-role", "crud",
    [R("POST", "/roles", body={"name": "ROLE_AUDIT", "description": "Auditors"}), GET("/roles")],
    db=["roles", "next_id_used"])
add("create-role-minimal", "crud", [R("POST", "/roles", body={"name": "ROLE_MIN"})], db=["roles"])
add("create-two-roles", "crud",
    [R("POST", "/roles", body={"name": "ROLE_A"}), R("POST", "/roles", body={"name": "ROLE_B"})],
    db=["roles"])
add("create-role-with-id", "crud", [R("POST", "/roles", body={"id": 7, "name": "ROLE_ID"})], db=["roles"])
add("create-role-bad-json", "crud", [R("POST", "/roles", body="{not json")], db=["roles"])
add("create-role-unknown-field", "crud",
    [R("POST", "/roles", body={"name": "ROLE_U", "colour": "blue"})], db=["roles"])
add("update-role", "crud",
    [R("PUT", "/roles/3", body={"id": 3, "description": "Content editors"}), GET("/roles/3")],
    db=["roles"])
add("update-role-name", "crud", [R("PUT", "/roles/3", body={"id": 3, "name": "ROLE_WRITER"})], db=["roles"])
add("update-role-id-mismatch", "crud", [R("PUT", "/roles/3", body={"id": 2, "description": "x"})], db=["roles"])
add("update-role-no-id", "crud", [R("PUT", "/roles/3", body={"description": "x"})], db=["roles"])
add("update-role-missing", "crud", [R("PUT", "/roles/4999", body={"id": 4999, "description": "x"})], db=["roles"])
add("update-role-bad-json", "crud", [R("PUT", "/roles/3", body="{oops")], db=["roles"])
add("delete-unused-role", "crud", [R("DELETE", "/roles/4"), GET("/roles/4")], db=["roles"])
add("delete-role-in-use", "crud", [R("DELETE", "/roles/3")], db=["roles", "group_roles"])
add("delete-missing-role", "crud", [R("DELETE", "/roles/4999")], db=["roles"])

add("create-user", "crud",
    [R("POST", "/users", body={"firstName": "Eve", "lastName": "Ernst", "email": "eve@example.org",
                               "accountName": "eve", "active": True}), GET("/users")],
    db=["users"])
add("update-user", "crud",
    [R("PUT", "/users/12", body={"id": 12, "firstName": "Robert", "email": "bob@example.org"}),
     GET("/users/12")], db=["users"])
add("update-user-active", "crud", [R("PUT", "/users/14", body={"id": 14, "active": True})], db=["users"])
add("update-user-birthday", "crud",
    [R("PUT", "/users/13", body={"id": 13, "birthday": "1985-12-24"}), GET("/users/13")], db=["users"])
add("delete-user", "crud", [R("DELETE", "/users/14"), GET("/users")], db=["users", "users_roles"])

add("create-group", "crud", [R("POST", "/groups", body={"name": "Reviewers"}), GET("/groups")],
    db=["groups", "members"])
add("update-group-name", "crud",
    [R("PUT", "/groups/22", body={"id": 22, "name": "Still empty"}), GET("/groups/22")], db=["groups"])
add("delete-group", "crud", [R("DELETE", "/groups/22"), GET("/groups")], db=["groups", "members"])

add("create-layer", "crud",
    [R("POST", "/layers", body={"name": "Rivers", "description": "All rivers"}), GET("/layers")],
    db=["layers"])
add("create-layer-with-source", "crud",
    [R("POST", "/layers", body={"name": "Rivers", "source": {"id": 52}})], db=["layers"])
add("update-layer", "crud",
    [R("PUT", "/layers/42", body={"id": 42, "name": "Highways", "description": None}),
     GET("/layers/42")], db=["layers"])
add("update-layer-source-ref", "crud",
    [R("PUT", "/layers/41", body={"id": 41, "source": {"id": 52}}), GET("/layers/41")], db=["layers"])
add("delete-layer", "crud", [R("DELETE", "/layers/44"), GET("/layers")], db=["layers", "sources"])

add("create-appearance", "crud",
    [R("POST", "/layerappearances", body={"name": "Bold", "opacity": 0.8, "visible": True,
                                          "properties": {"stroke": "4"}}), GET("/layerappearances")],
    db=["appearances", "appearance_props"])
add("update-appearance", "crud",
    [R("PUT", "/layerappearances/80", body={"id": 80, "opacity": 0.25, "hoverable": True}),
     GET("/layerappearances/80")], db=["appearances", "appearance_props"])
add("update-appearance-properties", "crud",
    [R("PUT", "/layerappearances/80", body={"id": 80, "properties": {"color": "blue"}}),
     GET("/layerappearances/80")], db=["appearance_props"])
add("delete-appearance-unused", "crud", [R("DELETE", "/layerappearances/82")], db=["appearances"])
add("delete-appearance-in-use", "crud", [R("DELETE", "/layerappearances/80")],
    db=["appearances", "layers"])

# data sources. The original cannot build the abstract LayerDataSource from
# JSON (no type information for Jackson), so creating one through the API is
# refused with 400 whatever the body; updating an existing one works.
add("create-source-refused", "crud",
    [R("POST", "/layerdatasources", body={"type": "WFS", "name": "Rivers WFS",
                                          "url": "http://geo.example.org/wfs", "typeName": "topp:rivers"})],
    db=TABLES_OF["layerdatasources"][:-1])
add("create-source-no-type", "crud",
    [R("POST", "/layerdatasources", body={"name": "Typeless", "url": "http://x.example.org"})],
    db=["sources"])
add("update-source-tilewms", "crud",
    [R("PUT", "/layerdatasources/51", body={"id": 51, "url": "http://new.example.org/osm", "width": 512}),
     GET("/layerdatasources/51")], db=["sources", "imagewms", "tilewms"])
add("update-source-wfs", "crud",
    [R("PUT", "/layerdatasources/52", body={"id": 52, "typeName": "topp:highways"}),
     GET("/layerdatasources/52")], db=["sources", "wfs"])
add("update-source-wmts-urls", "crud",
    [R("PUT", "/layerdatasources/53", body={"id": 53, "urls": ["http://z.tiles.example.org/wmts"]}),
     GET("/layerdatasources/53")], db=["wmts", "wmts_urls"])
add("update-source-xyz", "crud",
    [R("PUT", "/layerdatasources/54", body={"id": 54, "tileSize": 128}), GET("/layerdatasources/54")],
    db=["xyz"])
add("delete-source-in-use", "crud", [R("DELETE", "/layerdatasources/52")], db=["sources", "wfs", "layers"])
add("delete-source-unused", "crud",
    [R("DELETE", "/layers/42"), R("DELETE", "/layerdatasources/52"), GET("/layerdatasources")],
    db=["sources", "wfs", "layers"])

# ----------------------------------------------------------- permissions #
for u in USERS:
    for ep in ENDPOINTS:
        add(f"perm-list-{ep}-{u}", "permissions", [GET(f"/{ep}", u)])
    for i in SEEDED["layers"]:
        add(f"perm-read-layer-{i}-{u}", "permissions", [GET(f"/layers/{i}", u)])
        add(f"perm-update-layer-{i}-{u}", "permissions",
            [R("PUT", f"/layers/{i}", u, body={"id": i, "description": f"edited by {u}"})], db=["layers"])
        add(f"perm-delete-layer-{i}-{u}", "permissions", [R("DELETE", f"/layers/{i}", u)], db=["layers"])
    add(f"perm-create-layer-{u}", "permissions",
        [R("POST", "/layers", u, body={"name": f"{u}'s layer"})], db=["layers"])
    add(f"perm-create-role-{u}", "permissions",
        [R("POST", "/roles", u, body={"name": f"ROLE_{u.upper()}"})], db=["roles"])
    add(f"perm-update-role-{u}", "permissions",
        [R("PUT", "/roles/3", u, body={"id": 3, "description": u})], db=["roles"])
    add(f"perm-delete-source-{u}", "permissions", [R("DELETE", "/layerdatasources/54", u)], db=["sources"])
    for i in SEEDED["users"]:
        add(f"perm-read-user-{i}-{u}", "permissions", [GET(f"/users/{i}", u)])
    for i in SEEDED["groups"]:
        add(f"perm-read-group-{i}-{u}", "permissions", [GET(f"/groups/{i}", u)])
    add(f"perm-update-group-20-{u}", "permissions",
        [R("PUT", "/groups/20", u, body={"id": 20, "name": f"Editors ({u})"})], db=["groups"])
    add(f"perm-update-self-{u}", "permissions",
        [R("PUT", f"/users/{ {'alice': 11, 'bob': 12, 'carol': 13}[u] }", u,
           body={"id": {"alice": 11, "bob": 12, "carol": 13}[u], "language": "fr"})], db=["users"])
    add(f"perm-user-groups-{u}", "permissions", [GET("/users/11/userGroups", u)])
    add(f"perm-group-users-{u}", "permissions", [GET("/groups/20/users", u)])
add("perm-admin-reads-secret", "permissions", [GET("/layers/44")])
add("perm-admin-deletes-secret", "permissions", [R("DELETE", "/layers/44")], db=["layers"])

# --------------------------------------------------------------- queries #
ONLY = "output:only"
for ep, fields in [("roles", "name"), ("users", "accountName"), ("groups", "name"),
                   ("layers", "name"), ("layerdatasources", "url"), ("layerappearances", "opacity")]:
    add(f"only-{ep}-with-id", "queries", [GET(f"/{ep}?{ONLY}=id,{fields}")])
    add(f"only-{ep}-without-id", "queries", [GET(f"/{ep}?{ONLY}={fields}")])
add("only-id-alone", "queries", [GET(f"/layers?{ONLY}=id")])
add("only-case-insensitive-key", "queries", [GET("/roles?OUTPUT:ONLY=ID,NAME")])
add("only-case-insensitive-field", "queries", [GET(f"/users?{ONLY}=id,ACCOUNTNAME")])
add("only-unknown-field", "queries", [GET(f"/roles?{ONLY}=colour")])
add("only-empty", "queries", [GET(f"/roles?{ONLY}=")])
add("only-relation", "queries", [GET(f"/users?{ONLY}=id,accountName,roles")])
add("only-relation-layers", "queries", [GET(f"/layers?{ONLY}=id,source")])
add("only-as-user", "queries", [GET(f"/layers?{ONLY}=id,name", "alice")])
add("only-users-as-bob", "queries", [GET(f"/users?{ONLY}=id,firstName", "bob")])
add("only-other-params-ignored", "queries", [GET(f"/roles?{ONLY}=id,name&name=ROLE_USER")])

add("filter-role-name", "queries", [GET("/roles/filter?name=ROLE_USER")])
add("filter-or-same-field", "queries", [GET("/roles/filter?name=ROLE_USER&name=ROLE_EDITOR")])
add("filter-case-insensitive-key", "queries", [GET("/roles/filter?NAME=ROLE_ADMIN")])
add("filter-value-case-sensitive", "queries", [GET("/roles/filter?name=role_admin")])
add("filter-unknown-field", "queries", [GET("/roles/filter?colour=blue")])
add("filter-no-params", "queries", [GET("/roles/filter")])
add("filter-no-match", "queries", [GET("/roles/filter?name=ROLE_NOBODY")])
add("filter-and-two-fields", "queries", [GET("/roles/filter?name=ROLE_USER&description=User%20Role")])
add("filter-and-two-fields-no-match", "queries", [GET("/roles/filter?name=ROLE_USER&description=Editors")])
add("filter-with-only", "queries", [GET(f"/roles/filter?name=ROLE_EDITOR&{ONLY}=id,name")])
add("filter-with-only-no-id", "queries", [GET(f"/roles/filter?name=ROLE_EDITOR&{ONLY}=description")])
add("filter-user-account", "queries", [GET("/users/filter?accountName=carol")])
add("filter-user-boolean", "queries", [GET("/users/filter?active=false")])
add("filter-user-language", "queries", [GET("/users/filter?language=en")])
add("filter-user-two-values", "queries", [GET("/users/filter?accountName=alice&accountName=bob")])
add("filter-groups-name", "queries", [GET("/groups/filter?name=Viewers")])
add("filter-layers-name", "queries", [GET("/layers/filter?name=Roads")])
add("filter-layers-name-as-alice", "queries", [GET("/layers/filter?name=Roads", "alice")])
add("filter-layers-name-as-bob", "queries", [GET("/layers/filter?name=Roads", "bob")])
add("filter-layers-description", "queries", [GET("/layers/filter?description=City%20streets")])
add("filter-sources-type", "queries", [GET("/layerdatasources/filter?type=WFS")])
add("filter-sources-url", "queries", [GET("/layerdatasources/filter?url=http://geo.example.org/wms")])
add("filter-sources-name-two", "queries", [GET("/layerdatasources/filter?name=Basemap&name=Roads")])
add("filter-appearance-visible", "queries", [GET("/layerappearances/filter?visible=false")])
add("filter-appearance-opacity", "queries", [GET("/layerappearances/filter?opacity=0.5")])
add("filter-users-only-id", "queries", [GET(f"/users/filter?active=true&{ONLY}=id")])

# =================================================================== v2 #
# Added after the first two runs (Opus 5.5, Haiku 5.5) both passed all of the
# above: a differential cross-check found real port defects these did not
# reach. Written from the original's behaviour, not from either model's cases.
PERMS = ["user_perms", "group_perms", "perm_sets"]

# -------------------------------------------- loose JSON (Jackson's rules) #
for n, body in [
    ("active-string", {"accountName": "x1", "active": "true"}),
    ("active-null", {"accountName": "x2", "active": None}),
    ("birthday-short", {"accountName": "x3", "birthday": "2001-1-5"}),
    ("birthday-epoch", {"accountName": "x4", "birthday": 978307200000}),
    ("birthday-bad", {"accountName": "x5", "birthday": "not a date"}),
    ("language-dash", {"accountName": "x6", "language": "en-US"}),
    ("roles-null-entry", {"accountName": "x7", "roles": [None]}),
    ("groups-null-entry", {"accountName": "x8", "userGroups": [None]}),
    ("groups-duplicate", {"accountName": "x9", "userGroups": [20, 20, 21]}),
    ("role-ref-other-name", {"accountName": "x10", "roles": [{"id": 3, "name": "bogus"}]}),
    ("group-missing", {"accountName": "x11", "userGroups": [4999]}),
    ("role-missing", {"accountName": "x12", "roles": [{"id": 4999}]}),
    ("name-number", {"accountName": 42, "firstName": 2.5}),
]:
    add(f"loose-create-user-{n}", "crud", [R("POST", "/users", body=body)],
        db=["users", "users_roles", "members", "roles", "next_val"])
for n, body in [
    ("id-empty", {"id": "", "name": "ROLE_E"}),
    ("id-null", {"id": None, "name": "ROLE_N"}),
    ("id-string", {"id": "7", "name": "ROLE_S"}),
    ("name-number", {"name": 123}),
    ("name-bool", {"name": True}),
    ("name-object", {"name": {"a": 1}}),
    ("name-list", {"name": ["ROLE_L"]}),
    ("array-body", [{"name": "ROLE_ARR"}]),
    ("empty-body", {}),
    ("null-body", "null"),
    ("empty-string-body", ""),
]:
    add(f"loose-create-role-{n}", "crud", [R("POST", "/roles", body=body)], db=["roles", "next_val"])
for n, path, body, tables in [
    ("appearance-opacity-string", "/layerappearances/80", {"id": 80, "opacity": "0.3"}, ["appearances"]),
    ("appearance-opacity-bad", "/layerappearances/80", {"id": 80, "opacity": "abc"}, ["appearances"]),
    ("appearance-visible-int", "/layerappearances/80", {"id": 80, "visible": 0}, ["appearances"]),
    ("appearance-props-null", "/layerappearances/80", {"id": 80, "properties": None}, ["appearance_props"]),
    ("appearance-props-number", "/layerappearances/80", {"id": 80, "properties": {"w": 5}}, ["appearance_props"]),
    ("appearance-props-empty", "/layerappearances/80", {"id": 80, "properties": {}}, ["appearance_props"]),
    ("source-null-and-empty", "/layerdatasources/50",
     {"id": 50, "width": None, "height": "", "requestableByPath": "false"}, ["imagewms"]),
    ("source-width-string", "/layerdatasources/50", {"id": 50, "width": "1024"}, ["imagewms"]),
    ("source-width-float", "/layerdatasources/50", {"id": 50, "width": 1024.0}, ["imagewms"]),
    ("source-urls-null", "/layerdatasources/53", {"id": 53, "urls": None}, ["wmts_urls"]),
    ("source-urls-duplicate", "/layerdatasources/53", {"id": 53, "urls": ["http://u", "http://u"]}, ["wmts_urls"]),
    ("user-birthday-epoch", "/users/13", {"id": 13, "birthday": 0}, ["users"]),
    ("user-birthday-null", "/users/11", {"id": 11, "birthday": None}, ["users"]),
    ("user-email-number", "/users/13", {"id": 13, "email": 7}, ["users"]),
    ("role-id-string", "/roles/3", {"id": "3", "description": "s"}, ["roles"]),
    ("role-id-float", "/roles/3", {"id": 3.0, "description": "f"}, ["roles"]),
    ("role-unknown-field", "/roles/3", {"id": 3, "colour": "blue"}, ["roles"]),
    ("role-description-null", "/roles/3", {"id": 3, "description": None}, ["roles"]),
    ("layer-name-null", "/layers/42", {"id": 42, "name": None}, ["layers"]),
    ("layer-array-body", "/layers/42", [{"id": 42}], ["layers"]),
    ("layer-empty-body", "/layers/42", {}, ["layers"]),
]:
    add(f"loose-update-{n}", "crud", [R("PUT", path, body=body), GET(path)], db=tables)

# -------------------------------------------- id allocation after failures #
add("seq-after-bad-create", "crud",
    [R("POST", "/roles", body={"name": "ROLE_U", "colour": "x"}), R("POST", "/roles", body={"name": "ROLE_OK"})],
    db=["roles", "next_val"])
add("seq-after-missing-group", "crud",
    [R("POST", "/users", body={"accountName": "t1", "userGroups": [4999]}),
     R("POST", "/users", body={"accountName": "t2"})], db=["users", "members", "next_val"])
add("seq-after-refused-source", "crud",
    [R("POST", "/layerdatasources", body={"name": "n", "url": "u"}), R("POST", "/layers", body={"name": "after"})],
    db=["layers", "next_val"])
add("seq-after-denied-create", "crud",
    [R("POST", "/layers", "alice", body={"name": "denied"}), R("POST", "/layers", body={"name": "allowed"})],
    db=["layers", "next_val"])
add("seq-mixed-types", "crud",
    [R("POST", "/roles", body={"name": "ROLE_1"}), R("POST", "/groups", body={"name": "G1"}),
     R("POST", "/layerappearances", body={"name": "A1"}), R("POST", "/layers", body={"name": "L1"})],
    db=["roles", "groups", "appearances", "layers", "next_val"])

# --------------------------------------------- relations set by POST / PUT #
for n, path, body, tables in [
    ("layer-appearance", "/layers/42", {"id": 42, "appearance": {"id": 82}}, ["layers"] + PERMS),
    ("layer-appearance-null", "/layers/40", {"id": 40, "appearance": None}, ["layers", "appearances"]),
    ("layer-appearance-inline", "/layers/42", {"id": 42, "appearance": {"name": "inline", "opacity": 0.4}},
     ["layers", "appearances", "next_val"]),
    ("layer-appearance-missing", "/layers/42", {"id": 42, "appearance": {"id": 4999}}, ["layers"]),
    ("layer-source-null", "/layers/42", {"id": 42, "source": None}, ["layers"]),
    ("tilewms-tilegrid", "/layerdatasources/51", {"id": 51, "tileGrid": {"id": 61}}, ["tilewms", "tilegrids"]),
    ("wmts-tilegrid", "/layerdatasources/53", {"id": 53, "tileGrid": {"id": 60}}, ["wmts", "tilegrids"]),
    ("tilegrid-null", "/layerdatasources/51", {"id": 51, "tileGrid": None}, ["tilewms", "tilegrids"]),
    ("tilegrid-inline", "/layerdatasources/51", {"id": 51, "tileGrid": {"tileSize": 64}},
     ["tilewms", "tilegrids", "next_val"]),
    ("xyz-extent", "/layerdatasources/54", {"id": 54, "extent": {"id": 70}}, ["xyz", "extents"]),
    ("source-type-change", "/layerdatasources/52", {"id": 52, "type": "WMTS"}, ["sources", "wfs"]),
    ("source-id-mismatch", "/layerdatasources/52", {"id": 53, "name": "x"}, ["sources"]),
    ("user-roles", "/users/12", {"id": 12, "roles": [{"id": 3}]}, ["users_roles", "roles"]),
    ("user-roles-empty", "/users/12", {"id": 12, "roles": []}, ["users_roles"]),
    ("user-groups", "/users/13", {"id": 13, "userGroups": [20]}, ["members"]),
    ("user-groups-empty", "/users/11", {"id": 11, "userGroups": []}, ["members"]),
    ("group-members", "/groups/22", {"id": 22, "members": [{"id": 13}]}, ["members"]),
    ("group-members-empty", "/groups/20", {"id": 20, "members": []}, ["members"]),
    ("group-owner", "/groups/22", {"id": 22, "owner": {"id": 12}}, ["groups"]),
    ("group-owner-null", "/groups/20", {"id": 20, "owner": None}, ["groups"]),
    ("group-roles", "/groups/21", {"id": 21, "roles": [{"id": 3}, {"id": 4}]}, ["group_roles"]),
]:
    add(f"rel-update-{n}", "crud", [R("PUT", path, body=body), GET(path)], db=tables)
for n, path, body, tables in [
    ("layer-appearance", "/layers", {"name": "s5", "appearance": {"id": 82}}, ["layers"] + PERMS),
    ("group-members-owner", "/groups", {"name": "G", "members": [{"id": 11}], "owner": {"id": 13}},
     ["groups", "members"]),
    ("group-roles", "/groups", {"name": "GR", "roles": [{"id": 2}]}, ["groups", "group_roles"]),
    ("user-roles-groups", "/users", {"accountName": "rg", "roles": [{"id": 2}], "userGroups": [21]},
     ["users", "users_roles", "members"]),
    ("appearance-props", "/layerappearances", {"name": "P", "properties": {"a": "1", "b": "2"}},
     ["appearances", "appearance_props"]),
]:
    add(f"rel-create-{n}", "crud", [R("POST", path, body=body)], db=tables)

# ------------------------------------------ passwords and account changes #
add("account-create-then-login", "auth",
    [R("POST", "/users", body={"accountName": "pw", "password": "secret", "active": True}),
     R("GET", "/roles", "pw", password="secret"), R("GET", "/roles", "pw", password="shogun")])
add("account-create-inactive-login", "auth",
    [R("POST", "/users", body={"accountName": "pw2", "password": "secret"}),
     R("GET", "/roles", "pw2", password="secret")])
add("account-password-change", "auth",
    [R("PUT", "/users/12", body={"id": 12, "password": "changed"}),
     R("GET", "/roles", "bob", password="changed"), R("GET", "/roles", "bob")])
add("account-deactivate", "auth",
    [R("PUT", "/users/12", body={"id": 12, "active": False}), GET("/roles", "bob")])
add("account-rename", "auth",
    [R("PUT", "/users/12", body={"id": 12, "accountName": "robert"}),
     GET("/roles", "robert"), GET("/roles", "bob")])
add("account-reactivate", "auth",
    [R("PUT", "/users/14", body={"id": 14, "active": True}), GET("/roles", "dave")])
add("account-lose-role", "auth",
    [R("PUT", "/users/12", body={"id": 12, "roles": []}), GET("/roles", "bob"), GET("/layers", "bob")])
add("account-password-not-shown", "auth", [GET("/users/11"), GET("/users/filter?accountName=alice")])
add("account-delete-then-login", "auth", [R("DELETE", "/users/14"), GET("/roles", "dave")])
add("account-self-password", "auth",
    [R("PUT", "/users/11", "alice", body={"id": 11, "password": "mine"}),
     R("GET", "/roles", "alice", password="mine"), GET("/roles", "alice")])

# ------------------------------------- permissions on relation changes #
for n, user, path, body, tables in [
    ("alice-group-members", "alice", "/groups/20", {"id": 20, "members": [{"id": 11}, {"id": 13}]}, ["members"]),
    ("alice-group-roles", "alice", "/groups/20", {"id": 20, "roles": [{"id": 1}]}, ["group_roles"]),
    ("alice-group-owner", "alice", "/groups/20", {"id": 20, "owner": {"id": 12}}, ["groups"]),
    ("alice-self-groups", "alice", "/users/11", {"id": 11, "userGroups": [20, 21]}, ["members"]),
    ("alice-self-groups-drop", "alice", "/users/11", {"id": 11, "userGroups": []}, ["members"]),
    ("alice-self-roles-admin", "alice", "/users/11", {"id": 11, "roles": [{"id": 1}]}, ["users_roles"]),
    ("alice-other-groups", "alice", "/users/12", {"id": 12, "userGroups": [20]}, ["members"]),
    ("alice-other-name", "alice", "/users/12", {"id": 12, "firstName": "x"}, ["users"]),
    ("bob-self-groups", "bob", "/users/12", {"id": 12, "userGroups": [22]}, ["members"]),
    ("bob-self-roles-admin", "bob", "/users/12", {"id": 12, "roles": [{"id": 1}]}, ["users_roles"]),
    ("bob-read-only-user", "bob", "/users/13", {"id": 13, "firstName": "x"}, ["users"]),
    ("bob-admin-user", "bob", "/users/10", {"id": 10, "firstName": "x"}, ["users"]),
    ("carol-self-groups", "carol", "/users/13", {"id": 13, "userGroups": [20]}, ["members"]),
    ("carol-self-name", "carol", "/users/13", {"id": 13, "firstName": "Caro"}, ["users"]),
    ("carol-group-viewers", "carol", "/groups/21", {"id": 21, "name": "x"}, ["groups"]),
    ("alice-layer-appearance", "alice", "/layers/42", {"id": 42, "appearance": {"id": 80}}, ["layers"] + PERMS),
    ("bob-layer-appearance", "bob", "/layers/43", {"id": 43, "appearance": {"id": 82}}, ["layers"] + PERMS),
    ("carol-layer-appearance", "carol", "/layers/40", {"id": 40, "appearance": {"id": 82}}, ["layers"]),
    ("alice-source-update", "alice", "/layerdatasources/51", {"id": 51, "url": "http://x"}, ["sources"]),
    ("alice-appearance-update", "alice", "/layerappearances/80", {"id": 80, "opacity": 0.1}, ["appearances"]),
    ("bob-group-editors", "bob", "/groups/20", {"id": 20, "name": "x"}, ["groups"]),
]:
    add(f"perm-rel-{n}", "permissions", [R("PUT", path, user, body=body)], db=tables)
for n, user, method, path, tables in [
    ("alice-delete-group", "alice", "DELETE", "/groups/20", ["groups", "members"]),
    ("bob-delete-admin-layer", "bob", "DELETE", "/layers/43", ["layers", "map_layers"]),
    ("alice-delete-role", "alice", "DELETE", "/roles/4", ["roles"]),
    ("alice-delete-self", "alice", "DELETE", "/users/11", ["users"]),
    ("alice-delete-appearance", "alice", "DELETE", "/layerappearances/82", ["appearances"]),
    ("bob-delete-group-of-his", "bob", "DELETE", "/groups/20", ["groups"]),
]:
    add(f"perm-rel-{n}", "permissions", [R(method, path, user)], db=tables)
for n, user, path in [
    ("carol-group-users", "carol", "/groups/20/users"),
    ("carol-group-users-own", "carol", "/groups/21/users"),
    ("bob-user-groups-carol", "bob", "/users/13/userGroups"),
    ("alice-user-groups-bob", "alice", "/users/12/userGroups"),
    ("bob-group-users-empty", "bob", "/groups/22/users"),
    ("alice-filter-users", "alice", "/users/filter?active=true"),
    ("carol-filter-groups", "carol", "/groups/filter?name=Editors"),
    ("bob-filter-layers", "bob", "/layers/filter?description=Nobody%20may%20read%20this"),
    ("alice-only-users", "alice", "/users?output:only=id,accountName,email"),
    ("dave-inactive-get", "dave", "/layers/42"),
]:
    add(f"perm-read2-{n}", "permissions", [GET(path, user)])
add("perm-rel-after-grant-removed", "permissions",
    [R("PUT", "/users/12", body={"id": 12, "userGroups": []}), GET("/layers/41", "bob")])
add("perm-rel-after-group-join", "permissions",
    [R("PUT", "/users/13", body={"id": 13, "userGroups": [20, 21]}), GET("/layers/41", "carol")])
add("perm-rel-after-admin-role", "permissions",
    [R("PUT", "/users/13", body={"id": 13, "roles": [{"id": 1}]}), GET("/layers/44", "carol")])

# ------------------------------------------- deletes that touch other rows #
for i in [40, 42, 43, 41]:
    add(f"delete-layer-map-{i}", "crud", [R("DELETE", f"/layers/{i}")], db=["layers", "map_layers"])
add("delete-two-map-layers", "crud", [R("DELETE", "/layers/40"), R("DELETE", "/layers/43")],
    db=["layers", "map_layers"])
add("delete-layer-perms", "crud", [R("DELETE", "/layers/42")], db=["layers"] + PERMS)
add("delete-user-with-perms", "crud", [R("DELETE", "/users/12")], db=["users", "members"] + PERMS)
add("delete-group-with-perms", "crud", [R("DELETE", "/groups/21")], db=["groups", "members"] + PERMS)
add("delete-appearance-then-layer", "crud",
    [R("DELETE", "/layers/41"), R("DELETE", "/layerappearances/81")], db=["layers", "appearances"])
add("delete-twice", "crud", [R("DELETE", "/roles/4"), R("DELETE", "/roles/4")], db=["roles"])
add("delete-user-owner-of-group", "crud", [R("DELETE", "/users/11")], db=["users", "groups", "members"])

# ---------------------------------------------------------- odd paths #
for n, path in [
    ("hex", "/roles/0x3"), ("plus", "/roles/+3"), ("leading-zero", "/roles/03"),
    ("trailing-slash", "/roles/3/"), ("double-slash", "/roles//3"), ("decimal", "/roles/1.5"),
    ("too-big", "/roles/99999999999"), ("negative", "/roles/-1"), ("space", "/roles/%203"),
    ("list-trailing-slash", "/roles/"), ("sub-trailing-slash", "/users/11/userGroups/"),
    ("sub-unknown", "/users/11/roles"), ("groups-userGroups", "/groups/20/userGroups"),
    ("users-users", "/users/11/users"), ("unknown-resource", "/maps"), ("filter-id", "/roles/filter/3"),
    ("case-path", "/Roles"), ("users-groups-missing", "/users/4999/userGroups"),
    ("groups-users-missing", "/groups/4999/users"), ("users-groups-bad-id", "/users/abc/userGroups"),
]:
    add(f"path-{n}", "crud", [GET(path)])
for n, method, path, body in [
    ("put-list", "PUT", "/roles", {"id": 3}), ("delete-list", "DELETE", "/roles", None),
    ("post-id", "POST", "/roles/3", {"name": "x"}), ("patch", "PATCH", "/roles/3", {"id": 3}),
    ("put-hex", "PUT", "/roles/0x3", {"id": 3, "description": "hex"}),
    ("delete-hex", "DELETE", "/roles/0x4", None),
]:
    add(f"path-{n}", "crud", [R(method, path, body=body)], db=["roles"])

# --------------------------------------------------- filters and fields #
for n, path in [
    ("bool-yes", "/users/filter?active=yes"), ("bool-1", "/users/filter?active=1"),
    ("bool-upper", "/users/filter?active=TRUE"), ("bool-bad", "/users/filter?active=maybe"),
    ("ids", "/layers/filter?id=40&id=42"), ("id-bad", "/layers/filter?id=abc"),
    ("number-bad", "/layerappearances/filter?opacity=abc"), ("number-int", "/layerappearances/filter?opacity=1"),
    ("subtype-field", "/layerdatasources/filter?width=256"),
    ("subtype-field-wfs", "/layerdatasources/filter?typeName=topp:roads"),
    ("encoded-key", "/layers/filter?n%61me=Roads"), ("encoded-value", "/layers/filter?name=R%6fads"),
    ("plus-space", "/layers/filter?description=City+streets"), ("empty-value", "/roles/filter?description="),
    ("relation-field", "/layers/filter?source=52"), ("relation-owner", "/groups/filter?owner=11"),
    ("date-field", "/users/filter?birthday=1990-04-01"), ("null-word", "/users/filter?email=null"),
    ("mixed-known-unknown", "/roles/filter?name=ROLE_USER&colour=x"),
    ("only-repeated", "/roles?output:only=id&output:only=name"),
    ("only-spaces", "/roles?output:only=id,%20name"), ("only-subtype", "/layerdatasources?output:only=id,width"),
    ("only-nested", "/layers?output:only=id,appearance"), ("only-on-get-by-id", "/roles/3?output:only=id"),
    ("only-on-sub-path", "/users/11/userGroups?output:only=id"),
    ("only-filter-subtype", "/layerdatasources/filter?type=TileWMS&output:only=id,tileGrid"),
    ("filter-as-carol", "/layers/filter?name=Streets"),
]:
    add(f"query2-{n}", "queries", [GET(path, "carol" if n == "filter-as-carol" else "admin")])

# ------------------------- updating a user account one may update (v2b) #
# alice has UPDATE on herself, carol READ+UPDATE on dave (seed). The groups a
# user is put in are resolved through the secured group service: a group the
# caller cannot read is refused, even though the account itself may be updated.
for n, user, uid, body, tables in [
    ("alice-name", "alice", 11, {"firstName": "Ali"}, ["users"]),
    ("alice-groups-own", "alice", 11, {"userGroups": [20]}, ["members"]),
    ("alice-groups-unreadable", "alice", 11, {"userGroups": [21]}, ["members"]),
    ("alice-groups-mixed", "alice", 11, {"userGroups": [20, 22]}, ["members"]),
    ("alice-groups-objects", "alice", 11, {"userGroups": [{"id": 20}]}, ["members"]),
    ("alice-groups-none", "alice", 11, {"userGroups": []}, ["members"]),
    ("alice-groups-missing", "alice", 11, {"userGroups": [4999]}, ["members"]),
    ("alice-roles-admin", "alice", 11, {"roles": [{"id": 1}]}, ["users_roles"]),
    ("alice-active-false", "alice", 11, {"active": False}, ["users"]),
    ("alice-account-name", "alice", 11, {"accountName": "alicia"}, ["users"]),
    ("carol-name", "carol", 14, {"firstName": "David"}, ["users"]),
    ("carol-activate", "carol", 14, {"active": True}, ["users"]),
    ("carol-groups-member", "carol", 14, {"userGroups": [21]}, ["members"]),
    ("carol-groups-granted", "carol", 14, {"userGroups": [20]}, ["members"]),
    ("carol-groups-unreadable", "carol", 14, {"userGroups": [22]}, ["members"]),
    ("carol-groups-both", "carol", 14, {"userGroups": [20, 21]}, ["members"]),
    ("carol-roles-editor", "carol", 14, {"roles": [{"id": 3}]}, ["users_roles"]),
    ("carol-password", "carol", 14, {"password": "x"}, ["users"]),
    ("bob-groups-on-carol-read-only", "bob", 13, {"userGroups": [20]}, ["members"]),
]:
    add(f"perm-acct-{n}", "permissions", [R("PUT", f"/users/{uid}", user, body={"id": uid, **body})], db=tables)
add("perm-acct-carol-reads-dave", "permissions", [GET("/users/14", "carol"), GET("/users/14/userGroups", "carol")])
add("perm-acct-carol-deletes-dave", "permissions", [R("DELETE", "/users/14", "carol")], db=["users"])
add("perm-acct-carol-list-users", "permissions", [GET("/users", "carol")])
add("perm-acct-alice-joined-then-reads", "permissions",
    [R("PUT", "/users/11", "alice", body={"id": 11, "userGroups": [20]}), GET("/layers/41", "alice")])
for n, user, path, body, tables in [
    ("alice-members-unreadable-user", "alice", "/groups/20", {"id": 20, "members": [{"id": 14}]}, ["members"]),
    ("alice-members-ids", "alice", "/groups/20", {"id": 20, "members": [11, 12]}, ["members"]),
    ("alice-owner-unreadable", "alice", "/groups/20", {"id": 20, "owner": {"id": 14}}, ["groups"]),
    ("carol-perm-on-dave-via-group", "carol", "/groups/21", {"id": 21, "members": [{"id": 14}]}, ["members"]),
]:
    add(f"perm-acct-{n}", "permissions", [R("PUT", path, user, body=body)], db=tables)
