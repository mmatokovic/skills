---
name: webmethods-service
description: >
  Migrate webMethods IL services to Spring Boot. Reads IS package source (flow.xml, node.ndf,
  Java services, JDBC adapters, REST descriptors, IL config properties), explains what a flow
  really does, then writes a migration analysis, Spring code following the IL blueprint, and
  tests. Use when porting a service, REST
  operation or package from the integration layer (int-webmethods-project, `*-api-il`,
  `CO*V00N` packages, `co.<domain>.vN.*` namespaces) to Spring; when asked what a flow does,
  which procedure or SQL an IL endpoint calls, or to explain pasted flow.xml / node.ndf. Phrases:
  "migrate this wM service to Spring", "port this operation like the one we already migrated", "what does
  this flow.xml do", "prepiši servis iz webMethodsa u Spring", "što radi ovaj flow". Prefer
  this over spring-boot when the source is a webMethods service. Not for IS installation or
  troubleshooting (webmethods-platform) or Jira stories.
---

# webMethods → Spring Boot migration

Turns an IL webMethods service into (1) a migration analysis, (2) Spring Boot code, (3) tests
that pin the original behaviour. One API operation at a time.

The source is unreadable as-is: a single `flow.xml` can be 400 KB of design-time schema
snapshots around a few dozen real steps, and JDBC adapter SQL is hidden in base64 binary. Use the
bundled script to turn it into readable text first, then reason about that text.

## Reference files

| Read when… | File |
|---|---|
| Interpreting script output, any flow step, pipeline behaviour, JSON output shape | `references/flow-semantics.md` |
| A file or node type the script does not explain; adapters, RAD, config properties, test packages | `references/package-format.md` |
| You meet `co.utils.*` services, envelope/X-IL headers, `result`, error codes, retry loops | `references/crosig-il-patterns.md` |
| Writing any Spring code: project/slice layout, classes, naming, error enum, JDBC adapter, config, tests | `references/il-blueprint.md` |
| Which Spring piece a wM construct becomes; `pub.*` built-in equivalents; Select/CustomSQL adapters | `references/spring-mapping.md` |
| Writing the analysis | `references/analysis-template.md` |
| Writing tests | `references/testing.md` |
| Exact inputs/outputs of a built-in `pub.*` service | `assets/wm-service-catalog/<FOLDER>.json` (grep the service name) |
| Signature and real body of a shared Crosig service (`co.utils*`) or canonical doc (`co.cdm.*.technical`) when no checkout is available | `assets/custom-service-catalog/<prefix>.json` (generated — see its README) |

The Spring side follows `references/il-blueprint.md`, the target shape for every IL migration.
It overrides the generic **spring-boot** skill where they differ (IL `{"result"}` envelope instead
of ProblemDetail, stored procedures instead of JPA, backend keys instead of UUIDs); team-wide
conventions (build, naming, ArchUnit, test style) come from spring-boot `references/project-setup.md`.

## Workflow

### 1. Locate the service

The IL source is the `int-webmethods-project` checkout (one folder per API: `customer-api-il`,
`aoak-api-il`, ... with `vN/src/<Package>`). If you do not know where it is, look next to the
current repo (`../int-webmethods-project`, `../../int-webmethods-project`) and ask if not found.
Point `--root` at the whole checkout so shared packages (`utils-il`, `canonical-data-models-il`,
`config-il`) resolve.

```bash
S=<this skill's directory>/scripts/wm_inspect.py
python "$S" --root <checkout> rest identifiers          # by URL fragment → METHOD url -> entry service
python "$S" --root <checkout> find getCustomerIdentifiers   # by name → nsNames with node kinds
```

Pick the right version (`v003` vs `v2` packages often both exist) — the one the user named, or
ask. If the user only pasted XML, skip the script and read it with `flow-semantics.md` §6.

### 2. Extract everything in one pass

```bash
python "$S" --root <checkout> bundle <entry service nsName> -o <scratchpad>/bundle-<op>.md
```

The bundle holds the call tree, then for every service in it: signature, flow as pseudo-code,
decoded adapter (template, connection, SQL/procedure), Java service body, every doc type the
signatures reference, and a generated "Config and tests" section: the `ERROR_CODES_V2` rows per
endpoint (with the fallback when there is no `ESB|0` row), `ERRORS_TO_HTTP_CODES` with the
default-500 gaps marked, the `ACL_MAP` row, `CONFIG_PARAMETERS` key names, `[global-vars]`
variables and the WmTestSuite cases. Read it fully — it replaces grepping the config files. `show <nsName>` prints one node; `trace` prints only the
tree; `--utils` also descends into `co.utils.*`. The shared services are infrastructure, but several
of them decide what the client gets (`errorService` overwrites `result`, `endService` returns only
`outputFields` + `result`, `getHttpResponseCode` defaults to 500). When the error path or response
shape depends on one, `show` it rather than trusting a summary.

Only open the source files the bundle points to when something is unclear, e.g. a WmTestSuite
input/expected file, or the PL/SQL package spec or Oracle type when a procedure's parameters are
unclear — grep the
  `integration-database-objects` checkout (usually `<repos>/crosig/integration/integration-database-objects`,
  `LEGACY/` and `IDIT/`); not every package is there.

### 3. Write the migration analysis

Follow `references/analysis-template.md`. This is the step that catches the expensive mistakes,
so do it even when the user asked "just for the code" — keep it short then, but keep sections
3 (contract), 6 (errors) and 9 (behaviour changes). Present it and point out the decisions and
[VERIFY] items. If the user asked for code in the same request, continue with the
contract-preserving default for each decision and list them in the final message.

### 4. Write the Spring code

Follow `references/il-blueprint.md` — it is the definition of done for code. First decide
(blueprint §2): another operation of an already-migrated API → a new slice in that project; a new
wM package → a new project copied from an existing migrated one, with its generic infra files
copied rather than retyped. In an existing project, read the matching class before writing each
new one and follow what is there.

The order that works: records (from the doc types, wM JSON names) → `ErrorCodesEnum` constants
(from the properties files) → port + `<X>Adapter` in the blueprint adapter shape (from the Java
service / decoded SQL) → service (from api/enterprise flows) → controller (from the RAD) →
properties. `references/spring-mapping.md` says which wM construct lands where. Apply the
spring-boot `project-setup.md` rules (checkstyle, Error Prone, ArchUnit naming) while writing so
`./mvnw clean verify` passes first time.

### 5. Write the tests

Follow `references/testing.md` for *what* to test (WmTestSuite cases, one test per branch and per
error-code row, a raw-JSON contract check), blueprint §10 for the migration-specific cases, and
spring-boot `project-setup.md` for *how* (`<X>AdapterShould` with mocked JDBC running the real
lambdas, `*Should` naming, ArchUnit, `ContractFreezeIT`).

## What goes wrong most often

- **Porting the scaffolding as logic.** `beginService`, `endService`, `errorService`,
  `getLastError`, `mapSourceErrorToResult`, `getHttpResponseCode`, `setResponse*`, MAPDELETEs and
  `clearPipeline` are infrastructure. A 300-line flow is often 20 lines of Java.
- **Layers kept 1:1.** `api.pub → enterprise.pub → adapter.pub` with three sets of identical doc
  types become one service + one adapter + one set of records.
- **Errors as return values.** wM passes `result` up and branches on `isSuccess`; Spring throws
  at the adapter and maps once in the exception handler.
- **Silent contract changes.** Absent vs null fields, numbers serialised as strings, date
  formats, the `{"result": ...}` envelope, status codes that default to 500, X-IL response
  headers. Preserve them unless a decision says otherwise (`flow-semantics.md` §5).
- **Trusting declared types and required flags.** Path type codes in flow.xml are stale snapshots;
  `field_opt` is not enforced. Use node.ndf signatures, the producing code and the validate flows.
- **Disabled steps.** Anything marked `(DISABLED - skip)` does not run — leave it out.
- **Lossy adapter decode.** Repeated values (e.g. a second `OUT`) are not recovered from
  `IRTNODE_PROPERTY`; confirm parameter directions from the signature, the calling MAP or the PL/SQL spec.
- **Secrets.** Config properties, connection blobs and some Java services contain plaintext
  credentials. Reference them as `${ENV_VAR}`; never paste a value into code, YAML defaults,
  tests, the analysis or chat.
- **Unverifiable runtime state.** Global variables, DB rows in `ESB_ENV` tables, IS scheduler
  tasks and what IS returns on an unhandled exception are not in git — mark them [VERIFY].
