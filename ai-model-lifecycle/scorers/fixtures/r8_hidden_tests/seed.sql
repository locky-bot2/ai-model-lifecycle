-- r8 hidden tests: the data every scenario starts from.
SET client_min_messages = warning;
-- Applied to the pinned schema (cases/r8_shogun_rust/schema.sql) before each
-- scenario. Ids are below 5000; new rows get ids from hibernate_sequences
-- (next_val 5000). Every password is "shogun" (bcrypt, as the original stores it).
DO $$
DECLARE t text;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'hibernate_sequences' LOOP
    EXECUTE format('TRUNCATE TABLE public.%I CASCADE', t);
  END LOOP;
END $$;
DELETE FROM hibernate_sequences;
INSERT INTO hibernate_sequences (sequence_name, next_val) VALUES ('default', 5000);

-- roles
INSERT INTO roles (id, name, description) VALUES
  (1, 'ROLE_ADMIN', 'Administrator Role'),
  (2, 'ROLE_USER', 'User Role'),
  (3, 'ROLE_EDITOR', 'Editors'),
  (4, 'ROLE_SPARE', NULL);

-- users (Person -> User, joined)
INSERT INTO persons (id, firstname, lastname, email, birthday, language) VALUES
  (10, 'Ada', 'Admin', 'admin@example.org', NULL, 'en'),
  (11, 'Alice', 'Anders', 'alice@example.org', '1990-04-01', 'de'),
  (12, 'Bob', 'Berger', NULL, NULL, NULL),
  (13, 'Carol', 'Chen', 'carol@example.org', NULL, 'en'),
  (14, 'Dave', 'Dorn', NULL, NULL, NULL);
INSERT INTO users (id, accountname, active, password) VALUES
  (10, 'admin', true,  '$2a$10$p2HOrSY9YhzfI2JQbOUKleEBryW0Jv.m6E0FLLMgW206aWLstUP7K'),
  (11, 'alice', true,  '$2a$10$p2HOrSY9YhzfI2JQbOUKleEBryW0Jv.m6E0FLLMgW206aWLstUP7K'),
  (12, 'bob',   true,  '$2a$10$p2HOrSY9YhzfI2JQbOUKleEBryW0Jv.m6E0FLLMgW206aWLstUP7K'),
  (13, 'carol', true,  '$2a$10$p2HOrSY9YhzfI2JQbOUKleEBryW0Jv.m6E0FLLMgW206aWLstUP7K'),
  (14, 'dave',  false, '$2a$10$p2HOrSY9YhzfI2JQbOUKleEBryW0Jv.m6E0FLLMgW206aWLstUP7K');
INSERT INTO users_roles (user_id, role_id) VALUES (10, 1), (11, 2), (12, 2), (13, 2), (14, 2);

-- groups
INSERT INTO usergroups (id, name, owner_id) VALUES
  (20, 'Editors', 11),
  (21, 'Viewers', 10),
  (22, 'Empty', 10);
INSERT INTO user_usergroup (usergroup_id, user_id) VALUES (20, 11), (20, 12), (21, 13);
INSERT INTO usergroups_roles (usergroup_id, role_id) VALUES (20, 3), (21, 2);

-- extents and tile grids
INSERT INTO extents (id, lowerleft_x, lowerleft_y, upperright_x, upperright_y) VALUES
  (70, -180, -90, 180, 90),
  (71, 0, 0, 10, 10);
INSERT INTO tilegrids (id, type, tilegridorigin_x, tilegridorigin_y, tilesize, tilegridextent_id) VALUES
  (60, 'TileGrid', -20037508.34, -20037508.34, 256, 70),
  (61, 'WMTSTileGrid', -20037508.34, 20037508.34, 512, 70);
INSERT INTO tilegrid_resolution (tilegrid_id, resolution, idx) VALUES
  (60, 156543.03390625, 0), (60, 78271.516953125, 1), (60, 39135.7584765625, 2),
  (61, 1000.5, 0), (61, 500.25, 1);
INSERT INTO wmtstilegrids (id) VALUES (61);
INSERT INTO wmtstilegrids_matrixids (wmtstilegrids_id, matrixids) VALUES (61, 'EPSG:3857:0'), (61, 'EPSG:3857:1');

-- layer data sources: one per subtype (ImageWMS; TileWMS extends ImageWMS; WFS; WMTS; XYZ)
INSERT INTO layerdatasources (id, name, type, url, format) VALUES
  (50, 'States', 'ImageWMS', 'http://geo.example.org/wms', 'image/png'),
  (51, 'OSM tiles', 'TileWMS', 'http://ows.example.org/osm/service', NULL),
  (52, 'Roads', 'WFS', 'http://geo.example.org/wfs', 'application/json'),
  (53, 'Basemap', 'WMTS', 'http://tiles.example.org/wmts', 'image/jpeg'),
  (54, 'XYZ tiles', 'XYZ', 'http://xyz.example.org/{z}/{x}/{y}.png', NULL);
INSERT INTO imagewmslayerdatasources (id, customrequestpath, height, width, layernames, layerstyles, requestablebypath, version) VALUES
  (50, NULL, 512, 768, 'topp:states', 'population', false, '1.3.0'),
  (51, '/osm', 256, 256, 'OSM-WMS', '', true, '1.1.1');
INSERT INTO tilewmslayerdatasources (id, request_with_tiled, tilegrid_id) VALUES (51, true, 60);
INSERT INTO wfslayerdatasources (id, typename, typenames, version) VALUES (52, 'topp:roads', 'topp:roads,topp:rivers', '2.0.0');
INSERT INTO wmtslayerdatasources (id, capabilitiesurl, matrixset, projection, requestencoding, wmtslayer, wmtsstyle, tilegrid_id) VALUES
  (53, 'http://tiles.example.org/wmts?REQUEST=GetCapabilities', 'EPSG:3857', 'EPSG:3857', 'KVP', 'basemap', 'default', 61);
INSERT INTO wmtslayerdatasources_urls (wmtslayerdatasources_id, urls) VALUES
  (53, 'http://a.tiles.example.org/wmts'), (53, 'http://b.tiles.example.org/wmts');
INSERT INTO xyzlayerdatasources (id, center_x, center_y, tilesize, extent_id) VALUES (54, 1.5, 2.5, 256, 71);

-- layer appearances
INSERT INTO layerappearances (id, name, attribution, clickable, hoverable, hovertemplate, maxresolution, minresolution, opacity, visible) VALUES
  (80, 'Streets style', '© Example', true, false, '{name}', 1000, 1, 0.5, true),
  (81, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 1, false),
  (82, 'Spare', NULL, NULL, NULL, NULL, NULL, NULL, 1, true);
INSERT INTO layerappearances_properties (appearance_id, property, value) VALUES
  (80, 'color', 'red'), (80, 'weight', '2');

-- layers
INSERT INTO layers (id, name, description, source_id, appearance_id) VALUES
  (40, 'Streets', 'City streets', 51, 80),
  (41, 'Imagery', NULL, 50, 81),
  (42, 'Roads', 'Main roads', 52, NULL),
  (43, 'Tiles', NULL, 53, NULL),
  (44, 'Secret', 'Nobody may read this', 54, NULL);

-- a map module that shows three of the layers, in order (a layer's delete
-- must keep the map consistent; maps themselves are out of the slice)
INSERT INTO modules (id, name, xtype) VALUES (30, 'Main map', 'shogun-component-map');
INSERT INTO maps (id, mapconfig_id) VALUES (30, NULL);
INSERT INTO maps_layers (map_id, layer_id, idx) VALUES (30, 40, 0), (30, 42, 1), (30, 43, 2);

-- permissions: a collection is a set of permissions, granted to a user or a
-- group on one entity (entity_id: any entity, ids are unique across types)
INSERT INTO permissioncollections (id) VALUES (87), (88), (90), (91), (92), (93), (94), (95), (96), (97), (98), (99);
INSERT INTO permissioncollections_permissions (permissioncollections_id, permissions) VALUES
  (87, 'UPDATE'),
  (88, 'READ'), (88, 'UPDATE'),
  (90, 'READ'),
  (91, 'READ'), (91, 'UPDATE'),
  (92, 'READ'), (92, 'UPDATE'), (92, 'DELETE'),
  (93, 'ADMIN'),
  (94, 'READ'),
  (95, 'UPDATE'),
  (96, 'READ'),
  (97, 'READ'),
  (98, 'UPDATE'),
  (99, 'DELETE');
INSERT INTO userpermissions (entity_id, userpermissions_id, userpermissions_key) VALUES
  (40, 90, 11),   -- alice: READ on Streets
  (42, 92, 11),   -- alice: READ, UPDATE, DELETE on Roads
  (43, 93, 12),   -- bob: ADMIN on Tiles
  (40, 95, 13),   -- carol: UPDATE (no READ) on Streets
  (13, 96, 12),   -- bob: READ on user carol
  (20, 98, 11),   -- alice: UPDATE on group Editors
  (44, 99, 12),   -- bob: DELETE (no READ) on Secret
  (11, 87, 11),   -- alice: UPDATE on herself
  (14, 88, 13);   -- carol: READ, UPDATE on user dave
INSERT INTO grouppermissions (entity_id, grouppermissions_id, grouppermissions_key) VALUES
  (41, 91, 20),   -- Editors (alice, bob): READ, UPDATE on Imagery
  (42, 94, 21),   -- Viewers (carol): READ on Roads
  (20, 97, 21);   -- Viewers (carol): READ on group Editors
