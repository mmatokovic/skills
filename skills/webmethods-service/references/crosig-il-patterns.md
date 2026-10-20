# Crosig IL patterns — what the shared code does and what it becomes

Almost every IL service is wrapped in the same scaffolding from `co.utils[.v2|.v3].runtime.pub:*`
(`utils-il`). Recognise it, translate it **once** as cross-cutting Spring infrastructure, and keep
it out of the business code. The business logic of a service is what is left after removing it.

v1 (`co.utils.*`), v2 (`co.utils.v2.*`) and v3 (`co.utils.v3.*`) are near copies with the same
names. Check which one the service calls — error mapping differs slightly between them.

**The summaries below are a map, not the truth.** Whenever a shared service decides what the
client gets — the `result`, the error code, the HTTP status, which fields survive — read its
real body: `wm_inspect.py show <nsName>` with a checkout, or the `flow` / `invokes` entries in
`assets/custom-service-catalog/co.utils[.v2|.v3].json` without one (generated from source).

## Contents
1. Shared services cheat sheet
2. Envelope and X-IL headers
3. Error model: result, error codes, HTTP status
4. REST entry service pattern
5. JDBC call with ORA-04068 retry pattern
6. External REST call pattern
7. Async: JMS store-and-forward (vehicle v3)

## 1. Shared services cheat sheet

| Service | What it does | Spring equivalent |
|---|---|---|
| `runtime.pub:beginService` | sets `serviceName`, clones/creates `envelope` (generates `flowID` if missing, sets `flowName`), logs input JSON when `logLevel` is FULL/INFO, then **clears the pipeline** down to `inputFields` + `envelope` | header validation (interceptor) + request log (`HttpLoggingFilter`); nothing in business code |
| `runtime.pub:endService` | logs depending on `logLevel` (FULL, INFO, ERRFULL, INFO_ERRFULL, ERRINFO) and `result/errorCode`, then **clears the pipeline and returns only the contents of `outputFields` plus `result`** — on success and on error alike. What the caller receives is exactly what the flow mapped into `outputFields` | response logging filter; the returned value = what was in `outputFields` |
| `runtime.pub:errorService` | after `pub.flow:getLastError` in CATCH: logs the error (optionally mails it; knobs from `<flowName>.logPipeline/.sendErrorMail/.limitStackTrace` config), then **always overwrites `result`** with `isSuccess=false`, `errorCode = E_<seg1>_<seg3>_100` (upper-cased namespace segments 1 and 3 of the failing service: `co.aoak.v4.adapter...` → `E_AOAK_ADAPTER_100`), `errorDescription = lastError/error`. Any `result` set earlier (e.g. by `mapSourceErrorToResult`) is lost | global exception handler → generic technical error code |
| `runtime.pub:mapSourceErrorToResult` | turns a backend error (`sourceSystem`, `sourceErrorCode`, `sourceErrorDescription`) into `result` with the domain error code, by looking up `ERROR_CODES_V2` keyed by (sourceSystem, sourceErrorCode, **calling service**) | an enum of error codes (§3) + throwing a domain exception |
| `runtime.pub:getHttpResponseCode` | `result/errorCode` → HTTP status from `ERRORS_TO_HTTP_CODES` keyed by (REST service, error code); **default 500** | HTTP status carried by the error-code enum |
| `runtime.pub:getConfigParameter` | `name` → `value` from table `CONFIG_PARAMETERS` | `@ConfigurationProperties` record |
| `runtime.pub:convertHeadersToEnvelope` | reads `X-IL-flowID` / `X-IL-flowName` from request headers | interceptor |
| `runtime.pub:mapLastErrorToResult` (v1 `...2`) | lastError → result; validation errors (`/(valid)\|(walid)/`) → `E_<LAYER>_<DOMAIN>_99` | exception handler |
| `<dom>.api.priv:setResponseHeaders`, `co.utils.runtime.priv:setResponseHeaders` | set `X-IL-flowID`, `X-IL-flowName` on the response | interceptor `postHandle`/filter |
| `flow:getNull` | returns null (to blank a field) | `null` |
| `string:stringToLong/Integer/Double`, `objectToString`, `bool:stringToBoolean` | type conversion; check how they treat empty/invalid input before relying on `Long.valueOf` | parse helpers / Jackson binding |
| `date[.pub]:javaUtilDateToString`, `formatDateTimeString` | date formatting with a pattern | `DateTimeFormatter` with the same pattern |

`logLevel` and similar knobs come from `getConfigParameter` or global variables — they are
operational settings, not behaviour to port. Logging in Spring follows the spring-boot skill.

## 2. Envelope and X-IL headers

`co.cdm.v2.technical:docEnvelope` travels through every layer: flowID, flowName, correlationID,
externalID, processName, processID, sourceSystem, sourceType, sourceEndpoint, customerID, userID,
language, internalTimestamp, externalTimestamp, attributes[].

| Direction | Headers |
|---|---|
| Inbound (RAD params) | `X-IL-sourceSystem` (required), `X-IL-externalTimestamp` (required, date-time), `X-IL-correlationID`, `X-IL-externalID`, `X-IL-processName`, `X-IL-processID`, `X-IL-customerID`, `X-IL-userID`, `X-IL-language`, `X-IL-attributes` (csv list); some APIs add `X-IL-partnerId` |
| Outbound | `X-IL-flowID` (incoming one, or a generated UUID), `X-IL-flowName` (the `api.pub` service name unless the caller sent one) |

In Spring the envelope is not a parameter passed down every layer: the standard
`CoEnvelopeInterceptor` (`il-blueprint.md` §8) only validates the required headers. The X-IL
values are not put into MDC — `HttpLoggingFilter` logs all request headers (except the blacklisted
ones) and sets only `request.id`. The interceptor does **not** generate a flowID or set the
response headers — if consumers read `X-IL-flowID` (the B2B log analysis does), add that, or note
the gap explicitly.
Business code reads an envelope value (e.g. `userID`, `language`) only when the flow actually uses it.

## 3. Error model

`co.cdm.v2.technical:docResult`: `isSuccess` (Boolean), `errorCode`, `errorDescription`,
`errorDetails[]`, `sourceErrorDetails[]` / `sourceInfo[]` (systemId, code, description).

- **Errors are values.** Each layer catches everything and returns `result`; callers branch on
  `/result/isSuccess`. Do not port that as `if (!result.isSuccess()) return result;` chains —
  throw a domain exception at the adapter and map it once in the exception handler.
- **The error code comes from configuration.** `mapSourceErrorToResult` looks up
  `vN/config/ERROR_CODES_V2.properties` (`SOURCE_SYSTEM|SOURCE_ERROR_CODE|ENDPOINT|ERROR_CODE=DESC`).
  ENDPOINT is the service that *called* mapSourceErrorToResult. Fallbacks: `ESB|0` row, then
  `E_UNKNOWN_0` "Failed to determine cause of an error".
- **`errorDescription` is the configured text, not the backend message.** `mapSourceErrorToResult`
  sets `errorDescription` to the `ERROR_CODES_V2` description (`...|E_X_ADAPTER_134=Forbidden` ->
  "Forbidden"); the backend's own message (e.g. the Oracle text) travels in `sourceInfo`. Port both:
  a description per error-code constant, the backend message into `sourceInfo`.
- **The HTTP status comes from configuration.** `ERRORS_TO_HTTP_CODES.properties`
  (`<REST service nsName>.<ERROR_CODE>=<status>`), default **500** when there is no row. Many
  services have no rows at all — then every business error (even "not found") really returns 500
  today. Keep or fix that consciously and write the decision in the analysis; do not silently
  "improve" a 500 into a 404 that consumers do not expect.
- **The response body is the IL envelope**, `{"<payload>": ..., "result": {...}}`, not
  RFC 9457. Consumers parse it. Keep it (`il-blueprint.md` §9 records the
  deviation from the ProblemDetail standard) — unless the story says the contract changes.

Spring shape (`il-blueprint.md` §7): one enum per service with
`(oracleCode, appCode, httpStatus, systemId, description)` built from the two properties files,
one global source-code lookup shared by all endpoints (add constants, don't scope per endpoint);
`AdapterException.check(result)` / `from(result)` in the adapter; an `@RestControllerAdvice` that
returns `{"result": Result}` with the enum's status and description. Validation errors map to the code the
original `validate*` flow produced (`ESB|400|...validate...|E_<DOMAIN>_API_603`).

## 4. REST entry service pattern

`api.restProviders.<rad>_.services:<op>` (generated, then hand-edited), in order:

1. `pub.flow:getTransportInfo` → request headers; `getCurrentDateString` (`yyyy-MM-dd'T'HH:mm:ss.SSS`) → `internalTimestamp`
2. `convertHeadersToEnvelope`; `BRANCH /flowID [$null]` → generate UUID; `BRANCH /flowName [$null]` → the `api.pub` service name
3. type conversions of query params (e.g. Integer → String)
4. call `api.pub:<op>` with `envelope` (from X-IL-* headers) + `<op>Request` (from params/body)
5. map `<op>Response` and `result` into `_generatedResponse`
6. `setResponseHeaders` (X-IL-flowID, X-IL-flowName); `documentToJSONString` + `setResponse2` (application/json, UTF-8)
7. `BRANCH /_generatedResponse/result/isSuccess`: `true` → 200; `false` → `getHttpResponseCode` → `setResponseCode`
8. CATCH → `getLastError` → `errorService` → result into `_generatedResponse/result`. In
   several services the CATCH does not set a status or write the body, so an unexpected
   exception returns whatever IS defaults to — confirm against the running IS before encoding it.

→ Controller method (params/body binding), interceptor (steps 1–2, 6 headers), service call
(4–5), exception handler (7–8). Only step 3–5 is service-specific.

`api.pub:<op>`: beginService → TRY { validate (`api.priv:validate*`) → call `enterprise.pub` → map
response } CATCH { errorService } → endService. `enterprise.pub` is frequently a pure
pass-through — collapse it. `adapter.<sys>.pub` holds the backend call and the backend → result mapping.

## 5. JDBC call with ORA-04068 retry pattern (103+ flows, e.g. aoak v4)

```
JDBCTimeout: getConfigParameter("<svc>.JDBCTimeout") in some packages, an IS global variable
             (MAPSET [global-vars], not in git) in others, e.g. aoak v4 — check the flags; retry := True
REPEAT count=10 repeat-on=SUCCESS
  TRY   call <x>Adapter (targetServiceInput/timeout := %JDBCTimeout%); retry := False
  CATCH getLastError; BRANCH on nested error message:
          /^ORA-04068.*/  -> debugLog Warn, retry := True          (package state discarded)
          /^ORA-01013.*/  -> mapSourceErrorToResult(ESB, 408, ...)  (query timeout), retry := False
          $default        -> retry := False
  [%retry% == "false" && %lastError% != $null] EXIT $parent FAILURE
  [%retry% == "true"]                          EXIT $iteration (try again)
  [$default]                                   EXIT $loop (done)
BRANCH /targetServiceOutput [$null] -> mapSourceErrorToResult(ESB, 500, "OLDLEGACYCORE is currently unable...")
BRANCH /targetServiceOutput/error/errorCode [$null] success mapping | [$default] mapSourceErrorToResult(OLDLEGACYCORE, ...)
```

**What it does depends on how the loop is exited — check the EXIT steps in your flow.** The
variant below (`EXIT $parent FAILURE` with `lastError` left in the pipeline) behaves as follows;
flows that leave with `EXIT $loop SUCCESS` / `EXIT from="<named TRY>" SUCCESS` keep their mapped
`result`. Trace it through `errorService` (§1):

- The failing `EXIT $parent FAILURE` leaves the REPEAT with a failure, so the service's outer
  CATCH runs → `errorService` **overwrites `result`** with `E_<DOMAIN>_ADAPTER_100`. The ORA-01013
  → ESB 408 mapping set in the inner CATCH is therefore lost: a timeout reaches the client as the
  generic `_100` code (and its HTTP mapping, usually the default 500), not 408.
- `lastError` is never dropped. If ORA-04068 is followed by a successful call, the next check sees
  `retry == "false"` **and** `lastError != $null` → EXIT FAILURE → `_100` error, although the
  retry worked.

Confirm both on the running IS ([VERIFY]) before deciding. Porting "what the code meant"
(retry success = success, timeout = 408) is a behaviour change — reasonable, but record it as a
decision in the analysis, because consumers see different codes afterwards.

→ `JdbcTemplate` callable with `setQueryTimeout(props.timeout())`, wrapped in a `RetryTemplate`
that retries on ORA-04068/04061/04065/06508 found by walking the cause chain (spring-boot skill,
`references/jdbc-procedures.md`; `JdbcRetryConfig` in `il-blueprint.md` §6). ORA-01013 → timeout error code
(504/408 per the error table). An `error/errorCode` returned by the procedure → domain exception
with the mapped code. Only retry idempotent / read-only calls.

The procedure's own error output (`error{errorCode,errorMessage}`, or an Oracle
`*_TP_R_MESSAGE` / `*_TP_R_VALIDATION` STRUCT) is set by the Java service; on a Java exception it
usually sets `errorCode = "-1"`. Keep the code mapping (`OLDLEGACYCORE|-1|...`) intact.

## 6. External REST call pattern (`pub.client:http`, e.g. customer v3 idit)

`getConfigParameter` for url/basePath/username/password → `pub.client:http` (`loadAs=stream`,
headers) → `BRANCH /header/status`: `200` → `jsonStreamToDocument` → map; `$default` → parse the
error body (if any) → `mapSourceErrorToResult(<SYSTEM>, ...)`.

→ `RestClient` adapter with base URL/credentials from properties (secrets from the environment),
`.onStatus(...)` translating non-2xx into the domain exception with the same source-system codes,
timeouts set explicitly. Generated REST connectors (`pub.client:restClient`) map the same way.

## 7. Async: JMS store-and-forward (vehicle v3, the only trigger)

`adapter.oldLegacyCore.pub:insertVehicleDetails` calls the DB with `INVOKE TIMEOUT="10"`. On
failure, it disables the JMS trigger and parks the request on queue `insertVehicleDetailsQueue`
(`pub.jms:send`). `checkOldLegacyCorePhase2_LTConnection` (scheduled on the IS, not in git)
re-enables the trigger when the DB connection is healthy; the trigger replays the queue through
`pubSubInsertVehicleDetails`.

→ Spring: a JMS (or outbox table) listener container that is stopped while the DB is unhealthy
(health indicator + `JmsListenerEndpointRegistry` start/stop), or a Spring Batch/Quartz retry job.
Agree the design before writing code — it changes the operational behaviour.
