# IL blueprint — how a migrated IL service is written in Spring

The target shape for every wM → Spring migration of an IL service. Team-wide conventions (build,
checkstyle, Error Prone, naming, ArchUnit, unit-test style, Boot 4 controller IT) live in the
spring-boot skill's `references/project-setup.md`; this file adds only what is specific to IL
migrations. Placeholders: `<service>` project/property prefix, `<Feature>` class prefix,
`<feature>` package, `<DOMAIN>` the `E_<DOMAIN>_*` code domain, `<BACKEND>` source system id.

Reference implementation, if checked out: `<repos>/crosig/int-spring-project/household`
(module `household-api`, wM package `COHouseholdV003`, base path `/api/hh/v3`). The examples
below are taken from it:

| wM operation | Controller / service | Port / adapter | Procedure |
|---|---|---|---|
| `GET /household` (getHousehold) | `getHousehold` → 200 | `searchHousehold` | `co4096.cows_kucanstvo.p_pretrazi_kucanstvo` |
| `POST /household` (postHousehold) | `postHousehold` → 201 | `checkHousehold` | `CO4096.COWS_KUCANSTVO.p_provjeri_kucanstvo` |

## Contents
1. Which rule wins
2. New project or new slice
3. Layout and naming
4. Controller and service
5. Records
6. JDBC adapter
7. Error model
8. Web, logging, Jackson, config
9. Deviations from the generic spring-boot skill
10. Tests
11. Checklist

## 1. Which rule wins

- **Per operation, the wM contract wins**: error codes, statuses, `errorDescription`, JSON shape,
  validation messages and response codes (e.g. 201) are ported as the analysis found them.
- **Project-wide infrastructure an existing migrated project already settled is inherited**, not
  re-decided per operation (e.g. timeout → `E_<DOMAIN>_API_504`/504, retry count and back-off,
  unknown backend code → `E_<DOMAIN>_ADAPTER_000`/502). List every inherited difference from wM in
  the analysis so the owner sees it.
- Everything not covered here: spring-boot skill.

## 2. New project or new slice

| Situation | Do |
|---|---|
| Another operation of an already-migrated wM API (same base path, same backend) | add a slice to that project: controller method, service method, port method, adapter method, records, tests |
| A wM package/API not migrated yet | new Maven project copied from an existing migrated one; rename root package `hr.crosig.integration.<service>`, property prefix `<service>.*`, `E_<DOMAIN>_*` codes, `SystemId` backend constant, ArchUnit package strings, `src/test/resources/openapi.json`; keep the generic infra |

Generic infra to copy unchanged apart from the package:
- `infra/web`: `CoEnvelopeInterceptor`, `WebConfig`, `ApiProperties`, `OpenAPIConfig`
- `infra/logging`: `HttpLoggingFilter`, `HttpLoggingProperties`, `HttpLoggingUtils`
- `infra/jackson`: `JacksonConfig`, `ObjectMapperUtils`
- `infra/error`, `infra/exception`: `ErrorResponse`, `ErrorHandler`, `AdapterException`, `ApiException`
  (`ErrorCodesEnum` keeps its shape, the constants are per project)
- `infra/jdbc`: `JdbcProperties`, `JdbcRetryConfig`, `ResultMapper` (only if the backend returns
  the same validation STRUCT layout — `CO4096.HH_TP_R_VALIDATION`: `T`/`F`, code, description,
  source-info array)
- `domain/common/Result`, `archunit/*Rule`, `contract/ContractFreezeIT`, build files,
  `checkstyle.xml`, `lombok.config`, `.editorconfig`, `.mvn/jvm.config`, `Dockerfile`,
  `logback-spring.xml`, `CLAUDE.md` (adapt the names)

## 3. Layout and naming

| Package | Classes (household) |
|---|---|
| `api/` | `<Feature>Controller` (`HouseholdController`) |
| `app/<feature>/` | `<Feature>Service` + `<Feature>ServiceImpl` — methods named after the **API operation** (`getHousehold`, `postHousehold`) |
| `domain/common/` | `Result` (the IL `docResult`) |
| `domain/<feature>/` | port `<Feature>Repository`; `*Request` (`HouseholdSearchRequest`, `CreateHouseholdRequest`), `*Response` (`HouseholdSearchResponse`, `HouseholdDetailsResponse`), payload records (`HouseholdDetails`) |
| `infra/jdbc/` | `<Feature>Adapter` (`@Repository`, implements the port) — methods named after the **procedure** (`p_pretrazi_kucanstvo` → `searchHousehold`, `p_provjeri_kucanstvo` → `checkHousehold`); `<Feature>StructMapper`, `ResultMapper`; `JdbcProperties`, `JdbcRetryConfig` |
| `infra/error/`, `infra/exception/` | `ErrorCodesEnum`, `ErrorHandler`, `ErrorResponse`; `AdapterException`, `ApiException` |
| `infra/web/`, `infra/jackson/`, `infra/logging/` | generic infra (§8) |

Collapse the wM layers: `api.pub` → `enterprise.pub` → `adapter.pub` with three sets of identical
doc types become one service method, one adapter method and one set of records. One service
operation may call several adapter methods; the names stay operation vs. procedure.

## 4. Controller and service

```java
@RestController
@Tag(name = "Household management")
@RequestMapping("/household")                      // RAD resource path only
@RequiredArgsConstructor
public class HouseholdController {

    private final HouseholdService householdService;

    @GetMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<HouseholdSearchResponse> getHousehold(@Valid @ParameterObject HouseholdSearchRequest params) {
        return ResponseEntity.ok().body(householdService.getHousehold(params));
    }

    @PostMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<HouseholdDetailsResponse> postHousehold(@Valid @ParameterObject CreateHouseholdRequest params) {
        return ResponseEntity.status(HttpStatus.CREATED).body(householdService.postHousehold(params));
    }
}
```

- Path = RAD resource path; base path = urlalias/RAD `basePath` in `<service>.api.base-path`
  (`/api/hh/v3`), added by `WebConfig` — never in `@RequestMapping`.
- Where the RAD defines **query** params, bind one `@Valid @ParameterObject` record — also on a
  POST when wM took them as query params (`postHousehold`). Path variables → `@PathVariable`; a
  real body → `@Valid @RequestBody`. X-IL headers are handled by the interceptor, not method
  parameters.
- Return `ResponseEntity` with the status wM set (`setResponseCode`): `ok()` or
  `status(HttpStatus.CREATED)` when the flow sets 201.
- Service: the validation and orchestration the `api.pub` / `api.priv:validate*` / `enterprise.pub`
  flows did beyond copying.
  - Unconditional required params → Bean Validation with the wM message on the record component
    (`@NotNull(message = "snkId is mandatory") Long snkId`, `@NotBlank(message = "searchType is mandatory parameter")`).
  - Value normalisation wM did (e.g. upper-casing) → the record's compact constructor.
  - Allowed-value checks → a nested enum in the request record (`SearchTypeEnum.isSupported`) and
    `throw new ApiException("Wrong searchType parameter")` in the service with the wM message.
- `@Transactional` belongs to the adapter, not the service.

## 5. Records

- Field names = JSON names of the wM response / CLOB / Java service keys, unchanged.
- `*Response` = payload + `Result result` (`HouseholdSearchResponse(List<HouseholdDetails> households, Result result)`).
- Nested doc types become nested records inside the payload record
  (`HouseholdDetails.HouseholdMember`, `.HouseholdParty`, `.HouseholdMemberAddress`, …).
- Reuse an existing payload record when the RAD doc type has the same fields (`HouseholdDetails`
  is returned by both `getHousehold` and `postHousehold`).
- Types: from the code that produces the value, not the doc type. `NUMBER` → `Long`/`BigDecimal`
  (amounts always `BigDecimal`); timestamps `OffsetDateTime`, dates `LocalDate`; a value wM passes
  through from CLOB JSON untouched may stay `String` to keep its exact format.
- No Jackson annotations on records; omission rules go into `JacksonConfig`
  (`withConfigOverride(<Type>.class, NON_NULL/NON_EMPTY)`). wM leaves out fields it never set —
  the struct mapper returns `null` (not an empty list) for an empty collection; record in the
  analysis whether a shared record emits `null` instead of omitting the field.

## 6. JDBC adapter

```java
@Override
@Transactional(readOnly = true)                    // writing procedure: @Transactional (see below)
public HouseholdSearchResponse searchHousehold(HouseholdSearchRequest params) {
    logCall(SEARCH_HOUSEHOLD_PROCEDURE, params);
    return jdbcRetryTemplate.invoke(() -> jdbcTemplate.execute(
        conn -> {                                  // create STRUCTs/ARRAYs, prepare, bind, register OUT
            var parametersStruct = conn.createStruct(SEARCH_HOUSEHOLD_STRUCT_TYPE, new Object[]{ ... });
            var cs = conn.prepareCall(SEARCH_HOUSEHOLD_PROCEDURE);
            cs.setQueryTimeout(properties.timeout());
            cs.setObject(1, parametersStruct);
            cs.registerOutParameter(1, Types.STRUCT, SEARCH_HOUSEHOLD_STRUCT_TYPE);
            cs.registerOutParameter(2, Types.CLOB);
            cs.registerOutParameter(3, Types.STRUCT, MESSAGE_TYPE);
            return cs;
        },
        (CallableStatementCallback<HouseholdSearchResponse>) cs -> {
            var startNanos = System.nanoTime();
            cs.execute();
            var durationNanos = System.nanoTime() - startNanos;
            var result = ResultMapper.fromStruct((Struct) cs.getObject(3));
            var clob = cs.getClob(2);
            try {
                var json = clob != null ? clob.getSubString(1, (int) clob.length()) : null;
                logReturned(SEARCH_HOUSEHOLD_PROCEDURE, durationNanos, result);
                AdapterException.check(result);    // before mapping the payload
                var households = Objects.requireNonNullElse(
                    ObjectMapperUtils.readField(json, "households", new TypeReference<>() { }),
                    List.<HouseholdDetails>of());
                return new HouseholdSearchResponse(households, result);
            } finally {
                if (clob != null) {
                    clob.free();
                }
            }
        }));
}
```

Port the wM Java service into this shape:
- **Same call** — procedure string, parameter order, Oracle type names as `private static final`
  constants, exactly as wM has them (household: `HH_TP_A_KARTICE` / `HH_TP_R_KARTICA` without the
  `CO4096.` prefix), NULL rules (`setNull`, "0 means null"), nested STRUCT/ARRAY inputs — even
  the empty placeholder structs wM sends (`conn.createStruct(ADDRESS_TYPE, new Object[11])`).
- **Oracle collections** need `conn.unwrap(OracleConnection.class).createOracleArray(type, items)`
  (Oracle has no `createArrayOf`); that requires `ojdbc17` in **compile** scope.
- **LOBs and Arrays**: read once, `free()` in `finally`; STRUCT → record mapping in a
  `<Feature>StructMapper` (final, private constructor, static `fromStruct`) with attribute indexes
  taken from the wM Java service; a private `@FunctionalInterface StructMapping<T>` that throws
  `SQLException` lets one `mapArray` helper serve every nested list while keeping `SQLException`
  for JdbcTemplate's translation. `NUMBER` → `((BigDecimal) v).longValue()`, `DATE` →
  `Timestamp.toLocalDateTime().atZone(ZoneId.of("Europe/Zagreb")).toOffsetDateTime()`.
- **Transactions**: wM connections are usually `NO_TRANSACTION` (autocommit per call). With Hikari
  `auto-commit=false`, a writing procedure needs a read-write `@Transactional` (`checkHousehold`)
  or its writes are rolled back; reads use `@Transactional(readOnly = true)` (`searchHousehold`).
- **Retry**: `jdbcRetryTemplate` (Spring Framework 7 `org.springframework.core.retry.RetryTemplate`,
  `RetryPolicy.builder()` from `<service>.jdbc.retry.*`): retries only a `DataAccessException`
  whose cause chain holds an `SQLException` with a code in `ora-codes` (4068, 4061, 4065, 6508);
  a `RetryListener` logs each retry at WARN. Package-state errors fail before execution, so
  writing procedures may use it too — record that decision.
- **Validation result**: match the wM adapter flow's branch, not a generic rule. Household has both:
  - `searchHousehold`: `ResultMapper.fromStruct` — a missing STRUCT is a failure
    (`isSuccess=false`), then `AdapterException.check(result)`;
  - `checkHousehold`: the wM flow branches on `[$default]` — a missing validation object or a
    missing flag is success, only an explicit non-`T` is an error (private `isFailure(Struct)`,
    then `throw AdapterException.from(result)`).
- **Success result**: return what wM returned — `postHousehold` returns only `{"isSuccess": true}`
  (`new Result(true, null, null, null, null)`), not the whole validation STRUCT. A procedure that
  succeeds without the expected OUT payload → `IllegalStateException` (500).
- **Logging**: two private static helpers per adapter so every call logs the same way:

  ```java
  private static void logCall(String procedure, Object params) {
      log.atInfo().addKeyValue("params", params).log("DB procedure call {} ::", procedure);
  }

  private static void logReturned(String procedure, long durationNanos, @Nullable Result result) {
      log.atInfo()
          .addKeyValue("result", result == null || result.isSuccess())
          .addKeyValue("error_code", result != null ? result.errorCode() : null)
          .log("DB procedure response {} :: in {} ms", procedure, durationNanos / 1_000_000);
  }
  ```

  Duration is measured around `cs.execute()` only.

## 7. Error model

- `Result(isSuccess, errorCode, errorDescription, errorDetails, sourceInfo)` with nested
  `SourceInfo(systemId, type, code, description)`; errors leave as `ErrorResponse(Result)` →
  `{"result": {...}}`, never ProblemDetail.
- `ErrorCodesEnum` constants `(oracleCode, appCode, httpStatus, systemId, description)`, `@Getter`
  + `@RequiredArgsConstructor`, `systemId` from a nested `SystemId` constants class (`ESB`,
  `<BACKEND>` e.g. `HH_BACKEND`):
  - `ESB`-sourced constants with `oracleCode = null`: `VALIDATION` (`_API_301`, 400, "Bad request"),
    `UNEXPECTED` (`_API_500`, 500), `TIMEOUT` (`_API_504`, 504);
  - one constant per `ERROR_CODES_V2` row of the endpoints migrated (bundle section "Config and
    tests"), e.g. `E_120("19", "E_HOUSEHOLD_ADAPTER_120", NOT_FOUND, HH_BACKEND, "Not Found")`;
  - `httpStatus` from `ERRORS_TO_HTTP_CODES`, **500 where there is no row**;
  - `description` = the `ERROR_CODES_V2` text — it is the client's `errorDescription`;
  - `UNKNOWN(null, "E_<DOMAIN>_ADAPTER_000", BAD_GATEWAY, <BACKEND>, "Failed to determine cause of an error")`;
  - **one global** `fromOracleCode(code)` lookup (static map, default `UNKNOWN`) for all endpoints;
    add constants for a new operation, don't scope per endpoint unless the same code means
    different things on two endpoints.
- `AdapterException` (final, private constructor, `errorCode` + `sourceInfos`): `from(Result)` maps
  the code via `fromOracleCode` and keeps the Oracle message as exception message; `check(Result)`
  throws when `!isSuccess()`.
- `ApiException(String description)` → 400, `ESB`, type `Error`, code `"400"`; a five-argument
  constructor for anything else.
- `ErrorHandler` (`@RestControllerAdvice`, extends `ResponseEntityExceptionHandler`). Every
  `sourceInfo` it builds is `(systemId, "Error", "<http status>", message)`:

  | Exception | Status / code | `sourceInfo` description |
  |---|---|---|
  | `AdapterException` | enum status / app code, **enum description** | the backend's `sourceInfo`, or one synthesised from the Oracle message |
  | `ApiException` | its status; `VALIDATION` (4xx) or `UNEXPECTED` (5xx) | the exception's source fields |
  | `MethodArgumentNotValidException` | 400 `VALIDATION` | field messages joined with `"; "` |
  | `MissingServletRequestParameterException` | 400 `VALIDATION` | `"<name> is mandatory parameter"` |
  | `MethodArgumentTypeMismatchException` | 400 `VALIDATION` | `"'x' must be of type 'Long'"` / enum valid values |
  | `QueryTimeoutException` | 504 `TIMEOUT` | `"Request timed out while waiting for the resource to respond"` |
  | `DataAccessException` | 500 `UNEXPECTED` | `"<BACKEND> is currently unable to handle this request"` |
  | `Exception` | 500 `UNEXPECTED` | `"Something went wrong"` |

  `handleExceptionInternal` logs (ERROR with cause for 5xx, DEBUG otherwise; keys `status_code`,
  `error.type`) and converts any framework `ProblemDetail` into the envelope.

## 8. Web, logging, Jackson, config

- `CoEnvelopeInterceptor` (package-private `HandlerInterceptor`) only **validates** the X-IL
  headers the RAD marks required — household: `X-IL-sourceSystem`, `X-IL-partnerId` present,
  `X-IL-externalTimestamp` present and RFC 3339 (`OffsetDateTime.parse`) — throwing
  `ApiException("'<header>' is a required header")`. wM also set the `X-IL-flowID` /
  `X-IL-flowName` response headers — add that or record the gap.
- `WebConfig` (package-private) adds `<service>.api.base-path` via `configurePathMatch` →
  `addPathPrefix` to every `@RestController` under `hr.crosig`, and registers the interceptor on
  `<base-path>/**`. `ApiProperties` is a package-private `@ConfigurationProperties` record,
  constructor injection — no `@Value` fields. No `server.servlet.context-path`: the full wM path
  lives in the base path.
- `OpenAPIConfig`: title/version from `spring.application.name` / `info.app.version`; server URL =
  context path + base path, base path stripped from the documented paths; the required X-IL
  headers added as parameters to every operation.

**Logging** — the format and fields are what Kibana sees, so keep them identical across services:
- **Plain readable lines, no structured format in the app.** Keep the project's
  `logback-spring.xml`: plain pattern ending in `%kvp`, timestamps in `Europe/Zagreb`, console
  only in profile `local`, otherwise console + async rolling gz file. The OpenTelemetry Java agent
  on OpenShift captures each log event with its MDC and exports it; with
  `otel.instrumentation.logback-appender.experimental.capture-key-value-pair-attributes` the
  fluent-API key-values become attributes too.
- **Tracing**: done by the OpenTelemetry Java agent on OpenShift — the application has no tracing
  or metrics-registry dependencies and is unaware of it. The agent creates spans, propagates W3C
  `traceparent` and puts `trace_id` / `span_id` into the Logback MDC. Never parse or echo
  `traceparent` by hand.
- **`HttpLoggingFilter`** (package-private `OncePerRequestFilter`, `HttpLoggingProperties` from
  `integration.logging.http.*`) — the one place for MDC and HTTP logging:
  - `X-Request-Id` taken from the caller or generated (UUID), returned in the response, MDC
    `request.id`, removed in `finally` — the only MDC value the application sets.
  - Request event INFO `"HTTP {method} request :: {uri}"` with `query`, `source`
    (`getRemoteAddr()`), `headers`, `bytes`, `truncated`, `content`; body only for non-GET/DELETE
    JSON or text, cached up to 1 MB.
  - Response event `"HTTP {method} response :: {uri} {status} in {ms} ms"` (INFO, WARN ≥ 400,
    ERROR ≥ 500) with `headers`, `bytes`, `content`; body for JSON/text, always on ≥ 400.
  - Bodies normalised by `HttpLoggingUtils` (compact JSON) and truncated at `max-body-bytes`
    (8192). Headers are **blacklisted** (`excluded-headers`, default authorization /
    proxy-authorization / cookie / set-cookie) — log everything else. `excluded-paths`:
    `actuator,swagger-ui,v3/api-docs`.
  - No own `Observation` (Spring records `http.server.requests`), no IP headers parsed by hand
    (`server.forward-headers-strategy=framework` makes `getRemoteAddr()` correct). A logging
    failure is caught and logged at WARN, never breaks the response.
- **Loggers**: plain `@Slf4j` (the class is the logger name; levels per package) — no topics
  like `db.logger` / `audit.logger`. Fluent API (`log.atInfo().addKeyValue(...)`) everywhere a
  log carries context, including the `ErrorHandler` and the retry listener. No DEBUG defaults in
  `application.properties` (`logging.level.root=${LOG_LEVEL:INFO}`).

- `JacksonConfig` (Jackson 3, `@Configuration(proxyBeanMethods = false)`): **one configuration**,
  static `buildMapper()`, used for the MVC `JsonMapper` bean and for the static mapper in
  `ObjectMapperUtils` (`readField(json, field, TypeReference)` for a wrapped CLOB, `readTree`).
  Never a second mapper with different settings (the einvoice util/bean drift). Settings: lenient
  deserialisation (no fail on unknown/ignored properties, case-insensitive enums, single value as
  array, empty string as null), `OffsetDateTime` as `yyyy-MM-dd'T'HH:mm:ss.SSSXXX` without
  `ADJUST_DATES_TO_CONTEXT_TIME_ZONE`, `Result` `NON_EMPTY`; per-type omission rules from the
  analysis. Dates wM formatted with the IS zone: convert with the same zone (`Europe/Zagreb`) —
  [VERIFY] the IS zone.
- `application.properties`:

  ```properties
  <service>.api.base-path=/api/hh/v3
  <service>.jdbc.timeout=120                      # = wM JDBCTimeout
  <service>.jdbc.retry.max-retries=2
  <service>.jdbc.retry.delay=200ms
  <service>.jdbc.retry.multiplier=2.0
  <service>.jdbc.retry.max-delay=1s
  <service>.jdbc.retry.jitter=50ms
  <service>.jdbc.retry.ora-codes=4068,4061,4065,6508
  server.forward-headers-strategy=framework
  server.shutdown=graceful
  spring.datasource.hikari.auto-commit=false
  spring.datasource.url=${<SERVICE>_DATASOURCE_URL:<test db url>}
  spring.datasource.username=${<SERVICE>_DATASOURCE_USER:<test db user>}
  spring.datasource.password=${<SERVICE>_DATASOURCE_PASS:<test db password>}
  integration.logging.http.max-body-bytes=8192
  integration.logging.http.excluded-paths=actuator,swagger-ui,v3/api-docs
  ```

  Environment values as `${ENV:default}`; the datasource defaults point at the test database.
  Tests get dummy datasource values in `src/test/resources/application-default.properties`.

## 9. Deviations from the generic spring-boot skill

| Topic | spring-boot skill | IL migration | Why |
|---|---|---|---|
| Error body | RFC 9457 `ProblemDetail` | `{"result": Result}` | consumers parse the wM contract |
| Persistence | Spring Data JPA + Liquibase, `UUID` ids | `JdbcTemplate` + stored procedures, backend's `NUMBER` keys as `Long` | the backend is the legacy PL/SQL API; the service owns no tables |
| ArchUnit | rules copied from einvoice | `app`/`infra` packages, `*Adapter` repositories, no JPA rules | layering of §3; reasons in the comments of `archunit/*Rule` |
| Integration tests | `BaseIntegrationTest` (Oracle XE Testcontainer + WireMock) | `@SpringBootTest` ITs with ports `@MockitoBean`; adapters covered by Mockito unit tests | procedures and Oracle types don't exist in a container |

Record these in the project's `CLAUDE.md` ("Deliberate deviations from team standards").

## 10. Tests

Style: spring-boot `project-setup.md` — `<Class>Should`, snake_case behaviour names, Mockito +
AssertJ, `verifyNoMoreInteractions`. Migration-specific cases (see also `testing.md`), with the
household names as examples:
- `<Feature>AdapterShould` — every JDBC call verified (call string, timeout, binds, STRUCT
  attributes via `ArgumentCaptor`, `createOracleArray` type names, OUT registrations), success
  result as wM returned it, each validation branch (explicit failure, missing object), error code
  → enum constant, LOB/Array freed also on error, and retry:
  `retry_and_succeed_on_transient_oracle_error` (4068), `retry_when_root_cause_is_not_sql_exception`
  (ORA code on an `SQLException` whose own cause is not SQL), `rethrow_original_exception_when_retries_are_exhausted`
  (3 calls), `not_retry_non_transient_oracle_error` (942, 1 call).
- `<Feature>StructMapperShould` — full nested mapping, `null` for empty collections, null struct,
  date zones.
- `<Feature>ServiceImplShould` — each validation/orchestration rule, repository exception propagated.
- `ErrorHandlerShould` — envelope for an `AdapterException`: status, app code, enum `description`,
  Oracle message kept in `sourceInfo` / synthesised when the procedure returned none.
- `HttpLoggingUtilsShould` — loggable/binary content types, body normalisation; add
  `HttpLoggingFilterShould` (logback `ListAppender`: excluded headers absent, `request.id` in the
  MDC of both events, excluded paths not logged) when the filter changes.
- `<Feature>ControllerIT` — `@SpringBootTest` + `@AutoConfigureMockMvc`, `@ActiveProfiles("default")`,
  port `@MockitoBean`; full URL with base path, X-IL headers on every request; per operation:
  success status and JSON (`201` with only `isSuccess`), missing X-IL header → 400, validation
  error, a procedure error → its configured status and description, `X-Request-Id` present. Pin
  the raw wM JSON once a captured wM response exists.
- `ContractFreezeIT` — compares `/v3/api-docs` with `src/test/resources/openapi.json` (the wM
  RAD export) via `openapi-diff-core`. It stays `@Disabled` together with
  `TestClassRule.noDisabledTestRule` until every operation of `openapi.json` is migrated; re-enable
  both at once.

## 11. Checklist

- [ ] slice or new project decided; base path, prefixes, `SystemId` set
- [ ] records with wM JSON names; payload records reused where identical
- [ ] port + adapter in the §6 shape; procedure/type names as constants; `ojdbc17` compile scope if collections are built
- [ ] validation branch matches the wM adapter flow (missing STRUCT = failure or success?)
- [ ] transaction mode matches what the procedure does
- [ ] `ErrorCodesEnum` constants (with descriptions) for every new code; no per-endpoint scoping
- [ ] controller returns the wM status (200/201) with `ResponseEntity`
- [ ] adapter logs every call with `logCall` / `logReturned`; environment values as `${ENV:default}`
- [ ] tests from §10; `./mvnw clean verify` green
- [ ] analysis lists every decision and inherited difference
