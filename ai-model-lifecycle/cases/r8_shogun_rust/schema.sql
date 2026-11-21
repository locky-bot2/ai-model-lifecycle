
\restrict b9mHBYjcPGSeBjloOmfdiArYMJl8w4ZyhUT9OKOHXGcKK1WZauLv3dWSLqTOkMd

CREATE TABLE public.absolutelayouts (
    id integer NOT NULL
);

CREATE TABLE public.absolutelayouts_coords (
    layout_id integer NOT NULL,
    coord bytea,
    idx integer NOT NULL
);

CREATE TABLE public.accordionpanels (
    expandeditem bytea,
    id integer NOT NULL
);

CREATE TABLE public.applications (
    dtype character varying(31) NOT NULL,
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    active boolean,
    description character varying(255),
    language character varying(255),
    name character varying(255) NOT NULL,
    open boolean,
    url character varying(255),
    projectspecificinteger integer,
    projectspecificstring character varying(255),
    viewport_id integer
);

CREATE TABLE public.applications_plugins (
    application_id integer NOT NULL,
    plugin_id integer NOT NULL,
    idx integer NOT NULL
);

CREATE TABLE public.borderlayouts (
    id integer NOT NULL
);

CREATE TABLE public.borderlayouts_regions (
    layout_id integer NOT NULL,
    region character varying(255),
    idx integer NOT NULL
);

CREATE TABLE public.buttons (
    buttonaction character varying(255),
    connectedmodule bytea,
    defaultbutton boolean,
    glyph character varying(255),
    interaction character varying(255),
    text character varying(255),
    tooltip character varying(255),
    id integer NOT NULL
);

CREATE TABLE public.compositemodules (
    id integer NOT NULL,
    layout_id integer
);

CREATE TABLE public.coordinatetransformations (
    transformcenteronrender boolean,
    id integer NOT NULL
);

CREATE TABLE public.coordinatetransformations_epsg (
    coordtrans_id integer NOT NULL,
    epsg character varying(255),
    idx integer NOT NULL
);

CREATE TABLE public.extents (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    lowerleft_x double precision,
    lowerleft_y double precision,
    upperright_x double precision,
    upperright_y double precision
);

CREATE TABLE public.files (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    active boolean,
    file bytea,
    filename character varying(255),
    filetype character varying(255)
);

CREATE TABLE public.grouppermissions (
    entity_id integer NOT NULL,
    grouppermissions_id integer NOT NULL,
    grouppermissions_key integer NOT NULL
);

CREATE TABLE public.hibernate_sequences (
    sequence_name character varying(255) NOT NULL,
    next_val bigint
);

CREATE TABLE public.imagefiles (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    active boolean,
    file bytea,
    filename character varying(255),
    filetype character varying(255),
    height integer,
    thumbnail bytea,
    width integer
);

CREATE TABLE public.images (
    alttext character varying(255),
    link character varying(255),
    src character varying(255),
    id integer NOT NULL
);

CREATE TABLE public.imagewmslayerdatasources (
    customrequestpath character varying(255),
    height integer NOT NULL,
    layernames character varying(2048),
    layerstyles character varying(2048),
    requestablebypath boolean,
    version character varying(255),
    width integer NOT NULL,
    id integer NOT NULL
);

CREATE TABLE public.interceptorrules (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    endpoint character varying(255),
    event character varying(255) NOT NULL,
    operation character varying(255),
    rule character varying(255) NOT NULL,
    service character varying(255) NOT NULL
);

CREATE TABLE public.layerappearances (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    attribution character varying(255),
    clickable boolean,
    hovertemplate character varying(255),
    hoverable boolean,
    maxresolution double precision,
    minresolution double precision,
    name character varying(255),
    opacity double precision,
    visible boolean
);

CREATE TABLE public.layerappearances_properties (
    appearance_id integer NOT NULL,
    value character varying(255),
    property character varying(255) NOT NULL
);

CREATE TABLE public.layerdatasources (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    format character varying(255),
    name character varying(255),
    type character varying(255),
    url character varying(255)
);

CREATE TABLE public.layers (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    description character varying(255),
    name character varying(255),
    appearance_id integer,
    source_id integer
);

CREATE TABLE public.layouts (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    type character varying(255)
);

CREATE TABLE public.layouts_propertyhints (
    layout_id integer NOT NULL,
    propertyname character varying(255)
);

CREATE TABLE public.layouts_propertymusts (
    layout_id integer NOT NULL,
    propertyname character varying(255)
);

CREATE TABLE public.mapconfig_resolution (
    mapconfig_id integer NOT NULL,
    resolution double precision,
    idx integer NOT NULL
);

CREATE TABLE public.mapconfigs (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    center_x double precision,
    center_y double precision,
    maxresolution double precision,
    minresolution double precision,
    name character varying(255),
    projection character varying(255),
    resolution double precision,
    rotation double precision,
    zoom integer,
    extent_id integer
);

CREATE TABLE public.mapcontrols (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    mapcontrolname character varying(255)
);

CREATE TABLE public.mapcontrols_properties (
    mapcontrol_id integer NOT NULL,
    value character varying(255),
    property character varying(255) NOT NULL
);

CREATE TABLE public.maps (
    id integer NOT NULL,
    mapconfig_id integer
);

CREATE TABLE public.maps_layers (
    map_id integer NOT NULL,
    layer_id integer NOT NULL,
    idx integer NOT NULL
);

CREATE TABLE public.maps_mapcontrols (
    map_id integer NOT NULL,
    control_id integer NOT NULL
);

CREATE TABLE public.modules (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    name character varying(255),
    xtype character varying(255)
);

CREATE TABLE public.modules_properties (
    module_id integer NOT NULL,
    value character varying(255),
    property character varying(255) NOT NULL
);

CREATE TABLE public.modules_submodules (
    module_id integer NOT NULL,
    submodule_id integer NOT NULL,
    idx integer NOT NULL
);

CREATE TABLE public.nominatimsearches (
    format character varying(255),
    groupheadertpl character varying(255),
    minsearchtextchars integer,
    resultlimit integer,
    typedelay integer,
    id integer NOT NULL
);

CREATE TABLE public.nominatimsearches_viewboxlbrt (
    nominatim_id integer NOT NULL,
    viewboxinteger integer,
    idx integer NOT NULL
);

CREATE TABLE public.overpasssearches (
    format character varying(255),
    groupheadertpl character varying(255),
    minsearchtextchars integer,
    resultlimit integer,
    typedelay integer,
    id integer NOT NULL
);

CREATE TABLE public.overpasssearches_viewboxlbrt (
    overpass_id integer NOT NULL,
    viewboxinteger integer,
    idx integer NOT NULL
);

CREATE TABLE public.overviewmaps (
    magnification integer,
    id integer NOT NULL,
    parentmapmodule_id integer
);

CREATE TABLE public.overviewmaps_layers (
    overviewmap_id integer NOT NULL,
    layer_id integer NOT NULL,
    idx integer NOT NULL
);

CREATE TABLE public.passwordresettokens (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    expirationdate timestamp without time zone,
    token character varying(255),
    user_id integer
);

CREATE TABLE public.permissioncollections (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone
);

CREATE TABLE public.permissioncollections_permissions (
    permissioncollections_id integer NOT NULL,
    permissions character varying(255)
);

CREATE TABLE public.persons (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    birthday date,
    email character varying(255),
    firstname character varying(255),
    language character varying(255),
    lastname character varying(255)
);

CREATE TABLE public.plugins (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    classname character varying(255) NOT NULL,
    name character varying(255),
    sourcecode text,
    stylesheet text,
    systemplugin boolean,
    xtype character varying(255)
);

CREATE TABLE public.plugins_files (
    plugin_id integer NOT NULL,
    file_id integer NOT NULL
);

CREATE TABLE public.prints (
    url character varying(255),
    id integer NOT NULL
);

CREATE TABLE public.registrationtokens (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    expirationdate timestamp without time zone,
    token character varying(255),
    user_id integer
);

CREATE TABLE public.roles (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    description character varying(255),
    name character varying(255) NOT NULL
);

CREATE TABLE public.territories (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    geometry jsonb,
    name character varying(255)
);

CREATE TABLE public.tilegrid_resolution (
    tilegrid_id integer NOT NULL,
    resolution double precision,
    idx integer NOT NULL
);

CREATE TABLE public.tilegrids (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    tilegridorigin_x double precision,
    tilegridorigin_y double precision,
    tilesize integer,
    type character varying(255),
    tilegridextent_id integer
);

CREATE TABLE public.tilewmslayerdatasources (
    request_with_tiled boolean,
    id integer NOT NULL,
    tilegrid_id integer
);

CREATE TABLE public.treefolders (
    id integer NOT NULL
);

CREATE TABLE public.treenodes (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    checked boolean,
    expandable boolean NOT NULL,
    expanded boolean NOT NULL,
    icon character varying(255),
    iconcls character varying(255),
    index integer NOT NULL,
    leaf boolean NOT NULL,
    qtip character varying(255),
    qtitle character varying(255),
    root boolean NOT NULL,
    text character varying(255),
    parentfolder_id integer
);

CREATE TABLE public.user_usergroup (
    usergroup_id integer NOT NULL,
    user_id integer NOT NULL
);

CREATE TABLE public.usergroups (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    name character varying(255),
    owner_id integer
);

CREATE TABLE public.usergroups_roles (
    usergroup_id integer NOT NULL,
    role_id integer NOT NULL
);

CREATE TABLE public.userpermissions (
    entity_id integer NOT NULL,
    userpermissions_id integer NOT NULL,
    userpermissions_key integer NOT NULL
);

CREATE TABLE public.users (
    accountname character varying(255),
    active boolean,
    password character varying(255),
    id integer NOT NULL
);

CREATE TABLE public.users_roles (
    user_id integer NOT NULL,
    role_id integer NOT NULL
);

CREATE TABLE public.wfslayerdatasources (
    typename character varying(2048),
    typenames character varying(2048),
    version character varying(255),
    id integer NOT NULL
);

CREATE TABLE public.wfssearches (
    groupheadertpl character varying(255),
    minsearchtextchars integer,
    typedelay integer,
    wfsserverurl character varying(255),
    id integer NOT NULL
);

CREATE TABLE public.wfssearches_featuredatatypes (
    wfssearch_id integer NOT NULL,
    featuredatatype character varying(255),
    idx integer NOT NULL
);

CREATE TABLE public.wfssearches_layers (
    wfssearch_id integer NOT NULL,
    layer_id integer NOT NULL,
    idx integer NOT NULL
);

CREATE TABLE public.wmtslayerdatasources (
    capabilitiesurl character varying(255),
    matrixset character varying(255),
    projection character varying(255),
    requestencoding character varying(255),
    wmtslayer character varying(255),
    wmtsstyle character varying(255),
    id integer NOT NULL,
    tilegrid_id integer
);

CREATE TABLE public.wmtslayerdatasources_urls (
    wmtslayerdatasources_id integer NOT NULL,
    urls character varying(255)
);

CREATE TABLE public.wmtstilegrids (
    id integer NOT NULL
);

CREATE TABLE public.wmtstilegrids_matrixids (
    wmtstilegrids_id integer NOT NULL,
    matrixids character varying(255)
);

CREATE TABLE public.wpsparameters_supportedformats (
    wpsparam_id integer NOT NULL,
    format_name character varying(255)
);

CREATE TABLE public.wpsparameters_supportedgeometrytypes (
    wpsparam_id integer NOT NULL,
    geomtype_name character varying(255)
);

CREATE TABLE public.wpsplugins (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    classname character varying(255) NOT NULL,
    name character varying(255),
    sourcecode text,
    stylesheet text,
    systemplugin boolean,
    xtype character varying(255),
    process_id integer
);

CREATE TABLE public.wpsprimitives (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    classtype character varying(255),
    displayname character varying(255),
    valuetype character varying(255),
    inputplugin_id integer
);

CREATE TABLE public.wpsprocessexecutes (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    classtype character varying(255),
    displayname character varying(255),
    valuetype character varying(255),
    method character varying(255),
    mimetype character varying(255),
    url character varying(255),
    body_id integer,
    identifier character varying(255)
);

CREATE TABLE public.wpsprocessexecutes_inputs (
    wpsexecuteprocess_id integer NOT NULL,
    wpsparameter_id integer NOT NULL,
    identifier character varying(255) NOT NULL
);

CREATE TABLE public.wpsprocessexecutes_inputvalues (
    wpsexecuteprocess_id integer NOT NULL,
    value character varying(255),
    identifier character varying(255) NOT NULL
);

CREATE TABLE public.wpsreferences (
    id integer NOT NULL,
    created timestamp without time zone,
    modified timestamp without time zone,
    classtype character varying(255),
    displayname character varying(255),
    valuetype character varying(255),
    method character varying(255),
    mimetype character varying(255),
    url character varying(255),
    body_id integer
);

CREATE TABLE public.xyzlayerdatasources (
    center_x double precision,
    center_y double precision,
    tilesize integer,
    id integer NOT NULL,
    extent_id integer
);

CREATE TABLE public.xyzlayerdatasrc_resolution (
    xyzlayerdatasrc_id integer NOT NULL,
    resolution bytea,
    idx integer NOT NULL
);

ALTER TABLE ONLY public.absolutelayouts_coords
    ADD CONSTRAINT absolutelayouts_coords_pkey PRIMARY KEY (layout_id, idx);

ALTER TABLE ONLY public.absolutelayouts
    ADD CONSTRAINT absolutelayouts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.accordionpanels
    ADD CONSTRAINT accordionpanels_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.applications_plugins
    ADD CONSTRAINT applications_plugins_pkey PRIMARY KEY (application_id, idx);

ALTER TABLE ONLY public.borderlayouts
    ADD CONSTRAINT borderlayouts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.borderlayouts_regions
    ADD CONSTRAINT borderlayouts_regions_pkey PRIMARY KEY (layout_id, idx);

ALTER TABLE ONLY public.buttons
    ADD CONSTRAINT buttons_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.compositemodules
    ADD CONSTRAINT compositemodules_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.coordinatetransformations_epsg
    ADD CONSTRAINT coordinatetransformations_epsg_pkey PRIMARY KEY (coordtrans_id, idx);

ALTER TABLE ONLY public.coordinatetransformations
    ADD CONSTRAINT coordinatetransformations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.extents
    ADD CONSTRAINT extents_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.grouppermissions
    ADD CONSTRAINT grouppermissions_pkey PRIMARY KEY (entity_id, grouppermissions_key);

ALTER TABLE ONLY public.hibernate_sequences
    ADD CONSTRAINT hibernate_sequences_pkey PRIMARY KEY (sequence_name);

ALTER TABLE ONLY public.imagefiles
    ADD CONSTRAINT imagefiles_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.imagewmslayerdatasources
    ADD CONSTRAINT imagewmslayerdatasources_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.interceptorrules
    ADD CONSTRAINT interceptorrules_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.layerappearances
    ADD CONSTRAINT layerappearances_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.layerappearances_properties
    ADD CONSTRAINT layerappearances_properties_pkey PRIMARY KEY (appearance_id, property);

ALTER TABLE ONLY public.layerdatasources
    ADD CONSTRAINT layerdatasources_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.layers
    ADD CONSTRAINT layers_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.layouts
    ADD CONSTRAINT layouts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.mapconfig_resolution
    ADD CONSTRAINT mapconfig_resolution_pkey PRIMARY KEY (mapconfig_id, idx);

ALTER TABLE ONLY public.mapconfigs
    ADD CONSTRAINT mapconfigs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.mapcontrols
    ADD CONSTRAINT mapcontrols_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.mapcontrols_properties
    ADD CONSTRAINT mapcontrols_properties_pkey PRIMARY KEY (mapcontrol_id, property);

ALTER TABLE ONLY public.maps_layers
    ADD CONSTRAINT maps_layers_pkey PRIMARY KEY (map_id, idx);

ALTER TABLE ONLY public.maps_mapcontrols
    ADD CONSTRAINT maps_mapcontrols_pkey PRIMARY KEY (map_id, control_id);

ALTER TABLE ONLY public.maps
    ADD CONSTRAINT maps_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.modules
    ADD CONSTRAINT modules_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.modules_properties
    ADD CONSTRAINT modules_properties_pkey PRIMARY KEY (module_id, property);

ALTER TABLE ONLY public.modules_submodules
    ADD CONSTRAINT modules_submodules_pkey PRIMARY KEY (module_id, idx);

ALTER TABLE ONLY public.nominatimsearches
    ADD CONSTRAINT nominatimsearches_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.nominatimsearches_viewboxlbrt
    ADD CONSTRAINT nominatimsearches_viewboxlbrt_pkey PRIMARY KEY (nominatim_id, idx);

ALTER TABLE ONLY public.overpasssearches
    ADD CONSTRAINT overpasssearches_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.overpasssearches_viewboxlbrt
    ADD CONSTRAINT overpasssearches_viewboxlbrt_pkey PRIMARY KEY (overpass_id, idx);

ALTER TABLE ONLY public.overviewmaps_layers
    ADD CONSTRAINT overviewmaps_layers_pkey PRIMARY KEY (overviewmap_id, idx);

ALTER TABLE ONLY public.overviewmaps
    ADD CONSTRAINT overviewmaps_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.passwordresettokens
    ADD CONSTRAINT passwordresettokens_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.permissioncollections
    ADD CONSTRAINT permissioncollections_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.persons
    ADD CONSTRAINT persons_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.plugins_files
    ADD CONSTRAINT plugins_files_pkey PRIMARY KEY (plugin_id, file_id);

ALTER TABLE ONLY public.plugins
    ADD CONSTRAINT plugins_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.prints
    ADD CONSTRAINT prints_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.registrationtokens
    ADD CONSTRAINT registrationtokens_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.territories
    ADD CONSTRAINT territories_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.tilegrid_resolution
    ADD CONSTRAINT tilegrid_resolution_pkey PRIMARY KEY (tilegrid_id, idx);

ALTER TABLE ONLY public.tilegrids
    ADD CONSTRAINT tilegrids_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.tilewmslayerdatasources
    ADD CONSTRAINT tilewmslayerdatasources_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.treefolders
    ADD CONSTRAINT treefolders_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.treenodes
    ADD CONSTRAINT treenodes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.passwordresettokens
    ADD CONSTRAINT uk_3c6qk2vk9nk497pk09owffn94 UNIQUE (token);

ALTER TABLE ONLY public.wpsplugins
    ADD CONSTRAINT uk_fxmlg6hddrieyv0n1vswqo1um UNIQUE (classname);

ALTER TABLE ONLY public.plugins
    ADD CONSTRAINT uk_jpa1io4je97p66w45icij65jk UNIQUE (xtype);

ALTER TABLE ONLY public.plugins
    ADD CONSTRAINT uk_lccwfqwmw3nn82q9sj20n7isl UNIQUE (classname);

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT uk_ofx66keruapi6vyqpv6f2or37 UNIQUE (name);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT uk_qveiwb1gk2t4og3w7vdwxm9d4 UNIQUE (accountname);

ALTER TABLE ONLY public.wpsplugins
    ADD CONSTRAINT uk_qwdmjhfybrtjyg3k3ulxgpxvo UNIQUE (xtype);

ALTER TABLE ONLY public.registrationtokens
    ADD CONSTRAINT uk_s8grhjko0xet4dwg1v8tmdyar UNIQUE (token);

ALTER TABLE ONLY public.user_usergroup
    ADD CONSTRAINT user_usergroup_pkey PRIMARY KEY (user_id, usergroup_id);

ALTER TABLE ONLY public.usergroups
    ADD CONSTRAINT usergroups_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.usergroups_roles
    ADD CONSTRAINT usergroups_roles_pkey PRIMARY KEY (usergroup_id, role_id);

ALTER TABLE ONLY public.userpermissions
    ADD CONSTRAINT userpermissions_pkey PRIMARY KEY (entity_id, userpermissions_key);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.users_roles
    ADD CONSTRAINT users_roles_pkey PRIMARY KEY (user_id, role_id);

ALTER TABLE ONLY public.wfslayerdatasources
    ADD CONSTRAINT wfslayerdatasources_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.wfssearches_featuredatatypes
    ADD CONSTRAINT wfssearches_featuredatatypes_pkey PRIMARY KEY (wfssearch_id, idx);

ALTER TABLE ONLY public.wfssearches_layers
    ADD CONSTRAINT wfssearches_layers_pkey PRIMARY KEY (wfssearch_id, idx);

ALTER TABLE ONLY public.wfssearches
    ADD CONSTRAINT wfssearches_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.wmtslayerdatasources
    ADD CONSTRAINT wmtslayerdatasources_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.wmtstilegrids
    ADD CONSTRAINT wmtstilegrids_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.wpsplugins
    ADD CONSTRAINT wpsplugins_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.wpsprimitives
    ADD CONSTRAINT wpsprimitives_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.wpsprocessexecutes_inputs
    ADD CONSTRAINT wpsprocessexecutes_inputs_pkey PRIMARY KEY (wpsexecuteprocess_id, identifier);

ALTER TABLE ONLY public.wpsprocessexecutes_inputvalues
    ADD CONSTRAINT wpsprocessexecutes_inputvalues_pkey PRIMARY KEY (wpsexecuteprocess_id, identifier);

ALTER TABLE ONLY public.wpsprocessexecutes
    ADD CONSTRAINT wpsprocessexecutes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.wpsreferences
    ADD CONSTRAINT wpsreferences_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.xyzlayerdatasources
    ADD CONSTRAINT xyzlayerdatasources_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.xyzlayerdatasrc_resolution
    ADD CONSTRAINT xyzlayerdatasrc_resolution_pkey PRIMARY KEY (xyzlayerdatasrc_id, idx);

ALTER TABLE ONLY public.overpasssearches
    ADD CONSTRAINT fk1sjbxclbe95wmsq8ablyg080m FOREIGN KEY (id) REFERENCES public.modules(id);

ALTER TABLE ONLY public.nominatimsearches_viewboxlbrt
    ADD CONSTRAINT fk20f7i1g4ajdbboddu3xrtooqo FOREIGN KEY (nominatim_id) REFERENCES public.nominatimsearches(id);

ALTER TABLE ONLY public.users_roles
    ADD CONSTRAINT fk2o0jvgh89lemvvo17cbqvdxaa FOREIGN KEY (user_id) REFERENCES public.users(id);

ALTER TABLE ONLY public.layerappearances_properties
    ADD CONSTRAINT fk3deoji5xfqomu9u1c2e9vsg40 FOREIGN KEY (appearance_id) REFERENCES public.layerappearances(id);

ALTER TABLE ONLY public.wfssearches_layers
    ADD CONSTRAINT fk3w7k8n49n5icefe3msd5i6l77 FOREIGN KEY (layer_id) REFERENCES public.layers(id);

ALTER TABLE ONLY public.user_usergroup
    ADD CONSTRAINT fk4tvjsdf79c13ux4iiwcjk4qu8 FOREIGN KEY (usergroup_id) REFERENCES public.usergroups(id);

ALTER TABLE ONLY public.usergroups_roles
    ADD CONSTRAINT fk5234g43g3j7voqqm4yij6brfs FOREIGN KEY (role_id) REFERENCES public.roles(id);

ALTER TABLE ONLY public.layers
    ADD CONSTRAINT fk54oio2rexrnk1jp8e6tbrstiy FOREIGN KEY (appearance_id) REFERENCES public.layerappearances(id);

ALTER TABLE ONLY public.overviewmaps
    ADD CONSTRAINT fk590ek3644l5qtjvpf57lbjdhq FOREIGN KEY (parentmapmodule_id) REFERENCES public.maps(id);

ALTER TABLE ONLY public.treenodes
    ADD CONSTRAINT fk5dww0ulqj3rvp2ix99pqjx5ch FOREIGN KEY (parentfolder_id) REFERENCES public.treefolders(id);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk5uc5tjg1ntoe9gtweyu57c9rv FOREIGN KEY (id) REFERENCES public.persons(id);

ALTER TABLE ONLY public.compositemodules
    ADD CONSTRAINT fk6l20c811lgcjxe3i8u6vkwto5 FOREIGN KEY (id) REFERENCES public.modules(id);

ALTER TABLE ONLY public.maps_layers
    ADD CONSTRAINT fk6mfa2fhgtu1hu5k9434xr6aqw FOREIGN KEY (layer_id) REFERENCES public.layers(id);

ALTER TABLE ONLY public.permissioncollections_permissions
    ADD CONSTRAINT fk6qgrf1hag18te8vc89g3copu2 FOREIGN KEY (permissioncollections_id) REFERENCES public.permissioncollections(id);

ALTER TABLE ONLY public.wmtstilegrids
    ADD CONSTRAINT fk7oq6kwhm4ivs3dtj9neebmjdu FOREIGN KEY (id) REFERENCES public.tilegrids(id);

ALTER TABLE ONLY public.tilegrid_resolution
    ADD CONSTRAINT fk7ps10vl37yrjawbctew8v4fj2 FOREIGN KEY (tilegrid_id) REFERENCES public.tilegrids(id);

ALTER TABLE ONLY public.overviewmaps
    ADD CONSTRAINT fk89cj3ntpkgbph6bl4na9lnkyu FOREIGN KEY (id) REFERENCES public.modules(id);

ALTER TABLE ONLY public.imagewmslayerdatasources
    ADD CONSTRAINT fk8jelo83jk3uyikcy8e14q14kh FOREIGN KEY (id) REFERENCES public.layerdatasources(id);

ALTER TABLE ONLY public.wmtslayerdatasources
    ADD CONSTRAINT fk8q0rl952euvex9epy76kbxfx FOREIGN KEY (id) REFERENCES public.layerdatasources(id);

ALTER TABLE ONLY public.maps_layers
    ADD CONSTRAINT fk8wiqni7ib0384kvo2wllxj8lv FOREIGN KEY (map_id) REFERENCES public.maps(id);

ALTER TABLE ONLY public.registrationtokens
    ADD CONSTRAINT fk_c2jfl8vejjhnpe1ww0bxrbhte FOREIGN KEY (user_id) REFERENCES public.users(id);

ALTER TABLE ONLY public.passwordresettokens
    ADD CONSTRAINT fk_kqc3vqprnlcijm4b89pa34qg0 FOREIGN KEY (user_id) REFERENCES public.users(id);

ALTER TABLE ONLY public.mapconfigs
    ADD CONSTRAINT fkaas82an383c6w54lo3evk874i FOREIGN KEY (extent_id) REFERENCES public.extents(id);

ALTER TABLE ONLY public.overviewmaps_layers
    ADD CONSTRAINT fkaxehb42bttad6kvckb6n54fg5 FOREIGN KEY (overviewmap_id) REFERENCES public.overviewmaps(id);

ALTER TABLE ONLY public.maps
    ADD CONSTRAINT fkaykrqlkhis1v9pw9m2epgmldm FOREIGN KEY (mapconfig_id) REFERENCES public.mapconfigs(id);

ALTER TABLE ONLY public.buttons
    ADD CONSTRAINT fkb4bmsbuf47l2oyf1arxhtx32u FOREIGN KEY (id) REFERENCES public.modules(id);

ALTER TABLE ONLY public.maps_mapcontrols
    ADD CONSTRAINT fkcgqse2e5toypq1hn75xefl66h FOREIGN KEY (map_id) REFERENCES public.maps(id);

ALTER TABLE ONLY public.wmtslayerdatasources_urls
    ADD CONSTRAINT fkd2f717si95oll02ddhco50dln FOREIGN KEY (wmtslayerdatasources_id) REFERENCES public.wmtslayerdatasources(id);

ALTER TABLE ONLY public.xyzlayerdatasources
    ADD CONSTRAINT fkd34i41icgcwir8ubwfs3hvhc2 FOREIGN KEY (extent_id) REFERENCES public.extents(id);

ALTER TABLE ONLY public.layouts_propertyhints
    ADD CONSTRAINT fke2fwetyphyjq9ndnfnx9e76wy FOREIGN KEY (layout_id) REFERENCES public.layouts(id);

ALTER TABLE ONLY public.wfslayerdatasources
    ADD CONSTRAINT fke7oevl95y8tccs8r6sgxsebj FOREIGN KEY (id) REFERENCES public.layerdatasources(id);

ALTER TABLE ONLY public.layers
    ADD CONSTRAINT fkecbq0trhnls2c4rdhxyddn98 FOREIGN KEY (source_id) REFERENCES public.layerdatasources(id);

ALTER TABLE ONLY public.wmtstilegrids_matrixids
    ADD CONSTRAINT fketps6cyp4ralw6hg8unxwp5ov FOREIGN KEY (wmtstilegrids_id) REFERENCES public.wmtstilegrids(id);

ALTER TABLE ONLY public.mapconfig_resolution
    ADD CONSTRAINT fkex8883yu3pp297qw7hhcb2f5g FOREIGN KEY (mapconfig_id) REFERENCES public.mapconfigs(id);

ALTER TABLE ONLY public.usergroups
    ADD CONSTRAINT fkf9jdwwebc56lroer4270vi6wk FOREIGN KEY (owner_id) REFERENCES public.users(id);

ALTER TABLE ONLY public.modules_submodules
    ADD CONSTRAINT fkff7t5jqya8kc3hoy0n2s6r9ck FOREIGN KEY (module_id) REFERENCES public.compositemodules(id);

ALTER TABLE ONLY public.grouppermissions
    ADD CONSTRAINT fkgat4lw0ats3bkc66s4sf6oti2 FOREIGN KEY (grouppermissions_id) REFERENCES public.permissioncollections(id);

ALTER TABLE ONLY public.overpasssearches_viewboxlbrt
    ADD CONSTRAINT fkgf01tdcp1xpfcjkwhd4jleyt7 FOREIGN KEY (overpass_id) REFERENCES public.overpasssearches(id);

ALTER TABLE ONLY public.tilewmslayerdatasources
    ADD CONSTRAINT fkgo9y39t49c6my6jubkm655bu8 FOREIGN KEY (tilegrid_id) REFERENCES public.tilegrids(id);

ALTER TABLE ONLY public.tilegrids
    ADD CONSTRAINT fkhgcp4yru8bf15howoqwfl1sca FOREIGN KEY (tilegridextent_id) REFERENCES public.extents(id);

ALTER TABLE ONLY public.absolutelayouts_coords
    ADD CONSTRAINT fkhjy1vx0ucjjg7cyemxbms1gxu FOREIGN KEY (layout_id) REFERENCES public.absolutelayouts(id);

ALTER TABLE ONLY public.wfssearches_layers
    ADD CONSTRAINT fkhnxr4iq4avy4247sqn66hqe98 FOREIGN KEY (wfssearch_id) REFERENCES public.wfssearches(id);

ALTER TABLE ONLY public.user_usergroup
    ADD CONSTRAINT fkhv6qti3p9lj22w32nar6xcd8b FOREIGN KEY (user_id) REFERENCES public.users(id);

ALTER TABLE ONLY public.wpsprocessexecutes_inputs
    ADD CONSTRAINT fkijepj1d2m8x2130hvn1ees0qn FOREIGN KEY (wpsexecuteprocess_id) REFERENCES public.wpsprocessexecutes(id);

ALTER TABLE ONLY public.xyzlayerdatasources
    ADD CONSTRAINT fkip5b1f3b2o0yi5ugx9bfq5wxt FOREIGN KEY (id) REFERENCES public.layerdatasources(id);

ALTER TABLE ONLY public.borderlayouts
    ADD CONSTRAINT fkiqi2dm4dh9oswlyg1fb6wy41j FOREIGN KEY (id) REFERENCES public.layouts(id);

ALTER TABLE ONLY public.users_roles
    ADD CONSTRAINT fkj6m8fwv7oqv74fcehir1a9ffy FOREIGN KEY (role_id) REFERENCES public.roles(id);

ALTER TABLE ONLY public.absolutelayouts
    ADD CONSTRAINT fkjgnqke6rttl5f7d37tha4s6cq FOREIGN KEY (id) REFERENCES public.layouts(id);

ALTER TABLE ONLY public.wfssearches
    ADD CONSTRAINT fkk6eipef6dtt8xc9tv5pv5q7b4 FOREIGN KEY (id) REFERENCES public.modules(id);

ALTER TABLE ONLY public.grouppermissions
    ADD CONSTRAINT fkkdbfgj1ec5kyxy36i759l14h2 FOREIGN KEY (grouppermissions_key) REFERENCES public.usergroups(id);

ALTER TABLE ONLY public.wmtslayerdatasources
    ADD CONSTRAINT fkknvbqn84gvkdh8u72spgmbk0u FOREIGN KEY (tilegrid_id) REFERENCES public.wmtstilegrids(id);

ALTER TABLE ONLY public.compositemodules
    ADD CONSTRAINT fkl6qrbdx1t3ndgnf6w963lu8of FOREIGN KEY (layout_id) REFERENCES public.layouts(id);

ALTER TABLE ONLY public.overviewmaps_layers
    ADD CONSTRAINT fklj2ff5ug30vgv619x0hq14el6 FOREIGN KEY (layer_id) REFERENCES public.layers(id);

ALTER TABLE ONLY public.treefolders
    ADD CONSTRAINT fklm1qtidfx9vj5o7cwuhm6ojj8 FOREIGN KEY (id) REFERENCES public.treenodes(id);

ALTER TABLE ONLY public.mapcontrols_properties
    ADD CONSTRAINT fkn3h0vah1epaga3c4vqrtl648 FOREIGN KEY (mapcontrol_id) REFERENCES public.mapcontrols(id);

ALTER TABLE ONLY public.coordinatetransformations
    ADD CONSTRAINT fknnnq3t0pg2a5vjefd6p37a1mx FOREIGN KEY (id) REFERENCES public.modules(id);

ALTER TABLE ONLY public.wpsplugins
    ADD CONSTRAINT fknt0j3j5o5qdwmxulqx0w8aitx FOREIGN KEY (process_id) REFERENCES public.wpsprocessexecutes(id);

ALTER TABLE ONLY public.usergroups_roles
    ADD CONSTRAINT fkny71ti3okrgth2ipfpme24r84 FOREIGN KEY (usergroup_id) REFERENCES public.usergroups(id);

ALTER TABLE ONLY public.layouts_propertymusts
    ADD CONSTRAINT fko8hhu1kfshvk7bgtdo1bsq7cg FOREIGN KEY (layout_id) REFERENCES public.layouts(id);

ALTER TABLE ONLY public.userpermissions
    ADD CONSTRAINT fkoh9jpj4y9v8ec65hjeqyjuj2l FOREIGN KEY (userpermissions_key) REFERENCES public.users(id);

ALTER TABLE ONLY public.borderlayouts_regions
    ADD CONSTRAINT fkp2nliw8ryrq1thqm5cpsgxkos FOREIGN KEY (layout_id) REFERENCES public.borderlayouts(id);

ALTER TABLE ONLY public.userpermissions
    ADD CONSTRAINT fkp75s1i0om57xmlj8laxt83an2 FOREIGN KEY (userpermissions_id) REFERENCES public.permissioncollections(id);

ALTER TABLE ONLY public.applications_plugins
    ADD CONSTRAINT fkp7a6tyqsjb8l9q02egplhvqae FOREIGN KEY (application_id) REFERENCES public.applications(id);

ALTER TABLE ONLY public.nominatimsearches
    ADD CONSTRAINT fkpbxo0f4jffaq3ygn5gv67rcwp FOREIGN KEY (id) REFERENCES public.modules(id);

ALTER TABLE ONLY public.modules_submodules
    ADD CONSTRAINT fkq2ql0nyjajki4h3it7vs8hag9 FOREIGN KEY (submodule_id) REFERENCES public.modules(id);

ALTER TABLE ONLY public.coordinatetransformations_epsg
    ADD CONSTRAINT fkqowx6gfl8tdmbynb9xp3itg04 FOREIGN KEY (coordtrans_id) REFERENCES public.coordinatetransformations(id);

ALTER TABLE ONLY public.modules_properties
    ADD CONSTRAINT fkqriwohch3hnat5unepdu7j205 FOREIGN KEY (module_id) REFERENCES public.modules(id);

ALTER TABLE ONLY public.tilewmslayerdatasources
    ADD CONSTRAINT fkr6j3rf485miyoety0ctxrlcmm FOREIGN KEY (id) REFERENCES public.imagewmslayerdatasources(id);

ALTER TABLE ONLY public.wpsprocessexecutes_inputvalues
    ADD CONSTRAINT fkrapqbitwatd2c7h07ndrygy3g FOREIGN KEY (wpsexecuteprocess_id) REFERENCES public.wpsprocessexecutes(id);

ALTER TABLE ONLY public.accordionpanels
    ADD CONSTRAINT fkrcqk6cnf7bdcmqfnib82q73y2 FOREIGN KEY (id) REFERENCES public.compositemodules(id);

ALTER TABLE ONLY public.wfssearches_featuredatatypes
    ADD CONSTRAINT fkrv3j553w8feudkjndhfwfb04t FOREIGN KEY (wfssearch_id) REFERENCES public.wfssearches(id);

ALTER TABLE ONLY public.maps
    ADD CONSTRAINT fks3lfq3qyklm6m52bcswwseopr FOREIGN KEY (id) REFERENCES public.modules(id);

ALTER TABLE ONLY public.prints
    ADD CONSTRAINT fksfcgotjpi5uvh2crhgq5yvev3 FOREIGN KEY (id) REFERENCES public.modules(id);

ALTER TABLE ONLY public.maps_mapcontrols
    ADD CONSTRAINT fkslk3og54bqlvfwgo957smsc42 FOREIGN KEY (control_id) REFERENCES public.mapcontrols(id);

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT fksvmmkhhkdfyhqogjufd13ln9p FOREIGN KEY (viewport_id) REFERENCES public.compositemodules(id);

ALTER TABLE ONLY public.xyzlayerdatasrc_resolution
    ADD CONSTRAINT fktbxsuxhbddmi3we0s9cc9hmek FOREIGN KEY (xyzlayerdatasrc_id) REFERENCES public.xyzlayerdatasources(id);

ALTER TABLE ONLY public.images
    ADD CONSTRAINT fktf292odwf8e29lesw7bnjh6bw FOREIGN KEY (id) REFERENCES public.modules(id);

\unrestrict b9mHBYjcPGSeBjloOmfdiArYMJl8w4ZyhUT9OKOHXGcKK1WZauLv3dWSLqTOkMd

