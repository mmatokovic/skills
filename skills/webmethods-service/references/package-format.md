# webMethods IS package source — on-disk format

How a Crosig IL package looks in git (`int-webmethods-project/<api>-il/vN/...`), what each
file holds, and which parts are noise. `scripts/wm_inspect.py` already parses all of this. Read
this file when the script's output is unclear, or when you need a file the script does not cover.

## Contents
1. Repository and package layout
2. Namespace → folder
3. Layer naming (api / enterprise / adapter / resources)
4. node.ndf: node types and the signature encoding
5. Java services
6. JDBC adapter services and connections (base64 `IRTNODE_PROPERTY`)
7. REST providers (RAD), consumers, SOAP, triggers
8. Config outside the package: properties files and DB tables
9. Test packages
10. Noise to ignore

## 1. Repository and package layout

```
<api>-il/                       e.g. customer-api-il, aoak-api-il, dms-api-il
  Jenkinsfile                   ant build via ${WM_CI_HOME}/build.xml, VERSION=v1..v4
  vN/
    config/                     environment properties, NOT inside the IS package (§8)
    src/CO<Domain>V<NNN>/       the IS package (some versions have two, e.g. CODMSV003 + CODMSAdapterV003)
    test/CO<Domain>V<NNN>_TEST/ WmTestSuite test package (§9)
```

Inside a package:

| Path | Holds |
|---|---|
| `manifest.v3` | Package flags. `requires` is always empty — dependencies are implicit through invoked services. Startup services only in payment v3 and rva v3 (`...enterprise.priv:bootstrap`) |
| `ns/` | **The source of truth.** One folder per namespace node |
| `code/source/<folder path>.java` | Java services, one class per namespace folder |
| `code/jars/` | Third-party jars the Java services use |
| `config/urlalias.cnf` | URL alias → RAD (`api/customer/v3/identity` → `rad/co.customer.v003.api.restProviders:identity`) |
| `bin/`, `code/classes/` | Compiled classes — ignore |

Shared packages the API packages depend on:
- `utils-il/v1|v2|v3/src/COUtils|COUtilsV2|COUtilsV003` — `co.utils[.v2|.v3].*` (begin/end/errorService, config, error mapping). See `crosig-il-patterns.md`.
- `canonical-data-models-il/v1|v2|v3/src/COCDM*` — `co.cdm.v2.technical:docEnvelope`, `docResult`, and business docs (`co.cdm.v2.business.*`).
- `config-il/assets/IS/COConfig` — JDBC connections `co.config.jdbc:<Alias>` (15 aliases: `OldLegacyCore`, `OldLegacyCorePhase2`, `OldLegacyCoreAPPK`, `ESB_ENV`, `DWH`, `gisdb`, `newCore`, ...).

## 2. Namespace → folder

`ns/co/customer/v003/api/pub/getCustomerIdentifiers/` is the node `co.customer.v003.api.pub:getCustomerIdentifiers`:
every folder below `ns/` is a dot segment, the last folder (the one with `node.ndf`) comes after the colon.
Folder nodes have `node.idf` instead of `node.ndf`.

What sits next to `node.ndf` tells you the node kind at a glance:

| File | Node |
|---|---|
| `flow.xml` | flow service (body — see `flow-semantics.md`) |
| `java.frag` | Java service (signature + base64 body; read `code/source` instead) |
| `openapi` (YAML, no extension) | OpenAPI 3 REST provider descriptor |
| `wsdl0`, `xsd*` | SOAP web service descriptor |
| only `node.ndf` | doc type, adapter service, connection, RAD (swagger 2), resource, trigger, spec |

## 3. Layer naming

Every `*-api-il` package uses the same layers. A REST operation usually passes through all of them.

| Namespace | Role | Typical migration target |
|---|---|---|
| `api.restProviders:<rad>` | REST API descriptor: base path, operations, params, responses | the OpenAPI contract to freeze |
| `api.restProviders.<rad>_.services:<op>` | Generated REST entry flow: headers → envelope, calls `api.pub`, sets HTTP status/headers | `@RestController` method + interceptor |
| `api.restProviders.<rad>_.docTypes:*` | Request/response bodies as the client sees them | API DTO records |
| `api.pub:<op>` / `api.priv:*` / `api.doc:*` | Request validation, mapping API → enterprise | controller validation + application service |
| `enterprise.pub:<op>` / `.priv` / `.doc` | Business layer; often a pass-through | application service (merge it away if it only copies) |
| `adapter.<system>.pub:<op>` / `.doc` | One backend call: build params, call resource, map errors | infra adapter implementing a domain port |
| `adapter.<system>.resources.jdbc.<grp>:<name>Adapter` | JDBC adapter service | `JdbcTemplate` / `JdbcClient` call (see §6) |
| `adapter.<system>.resources.jdbc.<grp>:<name>` | Java service doing the real PL/SQL call (ExecuteService) | the body of that `JdbcTemplate` call |
| `adapter.<sys>.resources.<name>_.connectors:*` | Generated REST consumer connector (`pub.client:restClient`) | `RestClient` call |
| `adapter.<sys>.resource(s).soap.<name>_.connectors:*` | Generated SOAP connector | Spring WS / JAX-WS client |
| `doc` (package root) | Shared doc types | records |

`<system>` names the backend: `oldLegacyCore`, `oldLegacyCorePhase2`, `idit`, `jomologia`, `cvh`, `huo`, `crosig`, ...
A name ending in `Adapter` is the adapter service; the same name without the suffix is its Java service.

## 4. node.ndf

### Node kinds (from `svc_type`/`svc_subtype`, or `node_type`)

| Value | Count in repo | Meaning |
|---|---|---|
| `flow` / `default`, `unknown` | ~2200 | Flow service |
| `flow` / `restConsumer` | 236 | Generated REST connector |
| `flow` / `webservice` | 18 | SOAP connector or provider operation |
| `java` | ~370 | Java service |
| `AdapterService` | 322 | JDBC adapter service |
| `spec` | 6 | Specification (signature only) |
| `restDescriptor` (`restv2Descriptor` / `openAPIProvider` / `consumerDescriptor`) | 70 | REST descriptor |
| `restResource` | 134 | REST resource (url template → service) |
| `ConnectionData` | 15 | Adapter connection |
| `webServiceDescriptor` | 8 | SOAP WSD |
| `webMethods/trigger` | 1 | JMS trigger |
| root `<record name="record">` | many | Document type |

### Signature encoding

`svc_sig/sig_in` and `svc_sig/sig_out` hold `rec_fields`; doc types hold `rec_fields` directly.

```xml
<record javaclass="com.wm.util.Values">
  <value name="node_type">field</value>
  <value name="field_name">X-IL-externalTimestamp</value>
  <value name="field_type">object</value>
  <value name="wrapper_type">java.util.Date</value>
  <value name="field_dim">0</value>
  <value name="field_opt">true</value>     <!-- present = optional; ABSENT = required -->
</record>
```

| `field_type` | Java type |
|---|---|
| `string` | `String` |
| `record` | nested record/class (children in `rec_fields`) |
| `recref` | reference to doc type named in `rec_ref` |
| `object` | `wrapper_type`: `java.lang.Long`, `Integer`, `Double`, `Boolean`, `java.util.Date`, `java.math.BigDecimal`, `byte []`, or untyped `Object` |

`field_dim`: `0` scalar, `1` list, `2` table (`String[][]`).
Other keys: `node_comment` (description — read it), `stateless`, `caching`, `audit_level`, `originURI` (swagger the node was generated from).
`node_pkg` inside doc types is sometimes stale (copied from another package) — ignore it.

**Optional vs required matters for migration:** a flow-to-flow INVOKE only checks `field_opt`
when `VALIDATE-IN` is set, and it is `$none` everywhere in this repo — so "required" in a signature
is documentation, not behaviour. What the service really rejects is in the `api.priv:validate*`
flows (and in RAD `isRequired` for headers/params, whose runtime enforcement you should confirm
against a running IS before relying on it). Put `@NotNull`/`@NotBlank` only on what the original
actually rejected, and return the same error code it returned.

## 5. Java services

- `node.ndf`: `svc_type=java`, `svc_sigtype=java 3.5`.
- `java.frag`: flat signature (`[i] field:0:required name`, nested `[o] - field:0:required x`) and a base64 `body`.
- **Read the class instead**: `code/source/<ns folder as path>.java`, e.g.
  `co.customer.v003.adapter.oldLegacyCore.resources.jdbc.customeridentifiers:callProcedureGetCustomerIdentifiers` →
  `code/source/co/customer/v003/adapter/oldLegacyCore/resources/jdbc/customeridentifiers.java`.
  Each service is `public static final void <name>(IData pipeline)` between
  `// --- <<IS-START(<name>)>> ---` and `// --- <<IS-END>> ---`. Imports are between
  `IS-START-IMPORTS`/`IS-END-IMPORTS`, helper classes between `IS-START-SHARED`/`IS-END-SHARED`
  (often the POJOs that read Oracle STRUCTs — read them too).
- Pipeline access: `IDataUtil.getString(cursor, "x")` = input, `IDataUtil.put(cursor, "x", v)` = output.
- DB Java services get their connection from the pipeline: `(Connection) IDataUtil.get(cursor, "$db_service_connection")`, injected by the ExecuteService adapter (§6).
- Logging: `com.wm.util.JournalLogger.log(...)` → plain SLF4J.

## 6. JDBC adapter services and connections

The signature is plain XML; **everything else is in `IRTNODE_PROPERTY`, a base64 binary IData**
(strings are UTF-16BE). `wm_inspect.py show <adapter>` decodes it. The decoding is lossy:
a repeated value is stored as a back-reference and does not come out, so a list may look shorter
than its sibling lists (e.g. `colTypes` shows `IN` once for two columns). Cross-check parameter
directions and types with the adapter's node.ndf signature, the calling flow's MAP, and the PL/SQL
package spec — in the `integration-database-objects` repo if it is checked out (in this team usually
`<repos>/crosig/integration/integration-database-objects`; `LEGACY/Scripts/co4096/packages/*.pks`
for packages, Oracle object types also under `IDIT/`). Not every package is there; grep for the
procedure or type name and say so when it is missing.

| Template (`serviceTemplateName`) | ~Count | Where the logic is | Spring target |
|---|---|---|---|
| `ExecuteService` | 180 | Only lends a pooled connection; the PL/SQL call is hand-written in the Java service named by `javaService` | Port that Java body to `JdbcTemplate.execute(CallableStatementCreator, CallableStatementCallback)` |
| `Select` | 85 | `tables.*`, `select.expression`, `where.*`, `results[].COL` | `JdbcClient` query + record row mapper |
| `CustomSQL` | 19 | literal `sql` with `?` binds, `inputJDBCType`/`inputField`, `outputField`/`resultField` | same SQL in `JdbcClient` with named params |
| `Insert` / `Update` / `Delete` / `Batch*` | 32 | table + column mapping | `JdbcClient.update` / `batchUpdate` |
| `StoredProcedure` | 3 | `procedure.schemaName`, `procedure.procedureName`, `params.paramName/paramJDBCType/paramInOutType` | `SimpleJdbcCall` or `JdbcTemplate` callable |
| `StoredProcedureWithSignature` | 6 | `procedureSignature.procedureName`, `colNames`, `colSQLTypes`, `colTypes(IN/OUT)` | same |
| `DynamicSQL` | 7 | SQL assembled at runtime from pipeline strings | rebuild with bind params — watch for SQL injection in the original |

Common fields: `connectionName` (`co.config.jdbc:<Alias>` → which datasource), `queryTimeOut`
(`-1` = none), `maxRow`. Callers can override the timeout through `targetServiceInput/timeout`.

**Connections** (`co.config.jdbc:<Alias>`, `ConnectionData`): decoded properties show
`datasourceClass`, `serverName`, `databaseName`, `portNumber`, `user`, `transactionType`
(`NO_TRANSACTION` / `LOCAL_TRANSACTION`), pool sizes. Values are dev defaults overridden per
environment. The blob also holds a password — the script masks it; never copy credentials into
code, properties, tests or docs.

## 7. REST providers, consumers, SOAP, triggers

**RAD (swagger 2)** — `api.restProviders:<rad>/node.ndf`, `node_subtype=restv2Descriptor`:
`generalInfo/basePath`, `restResources/<path>/operations/<METHOD>` with `nsName` (entry service),
`parameters/<name>` (`source` HEADER/QUERY/PATH/BODY, `type`, `isRequired`, `isArray`),
`responseParam/refDefinition` (response doc type), `responses/<code>`. `restDefinitions` repeats
the doc types in swagger terms. `sourceUri` points at the original YAML on someone's laptop.
**OpenAPI 3 provider** (`openAPIProvider`) keeps the spec in a sibling `openapi` file — use it
directly; its operations are in the generated `<rad>_.resources:*` nodes (`restResource/operations`).
Newer resources carry `originUri` pointing at the team's spec repo
(`integration/openapi/specs/API_<NAME>_V00N_*.yaml`) — the best contract source when it exists.

Public URL = urlalias key + resource path: `GET /api/customer/v3/identity/identifiers`.
Generated entry services receive headers and query params as **top-level pipeline fields named
exactly like the parameter** (`X-IL-correlationID`, `firstName`), the body as its doc, and return
`_generatedResponse`.

**REST consumer** — `consumerDescriptor` + `<name>_/connectors:<op>` flows calling `pub.client:restClient`.
**SOAP** — `webServiceDescriptor`; `inbound=true` is a provider, `false` a consumer (`portAddress`, operations). Connectors call `pub.client:soapClient`.
**Trigger** — only `vehicle v3 ...adapter.priv:insertVehicleDetailsJMSTrigger`: JMS queue `insertVehicleDetailsQueue` → `pubSubInsertVehicleDetails`. There are no DB/file pollers or adapter notifications in the repo; schedules live on the IS, not in git.

## 8. Config outside the package

`<api>-il/vN/config/` (loaded into `ESB_ENV` tables, read at runtime by `co.utils.*`):

| File | Format | Runtime table |
|---|---|---|
| `CONFIG_PARAMETERS.properties` | `co.customer.v003.adapter.idit.url=https://...`; `<service>.JDBCTimeout=30` | `CONFIG_PARAMETERS(NAME, VALUE, IS_ACTIVE)` |
| `ERROR_CODES_V2.properties` | `SOURCE_SYSTEM\|SOURCE_ERROR_CODE\|SOURCE_ENDPOINT\|ERROR_CODE=DESC` | `ERROR_CODES_V2` |
| `ERRORS_TO_HTTP_CODES.properties` | `<rest service nsName>.<ERROR_CODE>=<http>` | `ERRORS_TO_HTTP_CODES(SERVICE_NAME, ERROR_CODE, HTTP_CODE)` |
| `ACL_MAP.properties` | `<rest service nsName>=<ACL>` | IS ACLs |

These files are the migration's input for error codes, HTTP statuses and config keys. They
contain plaintext credentials in places — take key names, never values. The DB tables can hold
rows the files do not; say so in the analysis when a lookup has no file entry.

## 9. Test packages

`vN/test/<Package>_TEST/resources/test/`:
- `setup/WmTestSuite.xml` — `webMethodsTestCase`s: the `service` under test, `input` file,
  `expected` file, and `mock`s (`folder` + `name` of the mocked service, `pipeline` file with its output).
- `data/*.xml` — `IDataXMLCoder` documents: `<record>`, `<value name>`, `<number type="java.lang.Integer">`.

These are behaviour already pinned down by the original team — convert them (see `testing.md`).

## 10. Noise to ignore

`*.bak` (1,749 `flow.xml.bak`), `bin/`, `code/classes/`, `designerOutput.log`, `.project`,
`.classpath`, `pub/index.html`, and the `MAPTARGET`/`MAPSOURCE` blocks inside `flow.xml`
(design-time schema snapshots — they are most of the file size).
