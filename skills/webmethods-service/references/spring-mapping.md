# wM → Spring Boot mapping

Which wM construct becomes which Spring piece. **How** each piece is written — classes, naming,
error model, adapter shape, config, tests — is in `il-blueprint.md`; follow it over any generic rule. The spring-boot skill still applies for everything
the blueprint does not cover (e.g. `references/jdbc-procedures.md`).

## Contents
1. Where each wM piece goes
2. Built-in `pub.*` services → Java
3. Porting a JDBC Java service (ExecuteService)
4. Select / CustomSQL adapters
5. Config, secrets, datasources
6. Things that change behaviour silently

## 1. Where each wM piece goes

Root package `hr.crosig.integration.<service>`; layout `api/`, `app/`, `domain/`, `infra/`.

| wM | Spring | Notes |
|---|---|---|
| RAD / OpenAPI provider (`api.restProviders:<rad>`) | the contract: export it (or take the `openapi` file / original YAML) into `src/test/resources/openapi.json` and freeze it with `ContractFreezeIT` | base path = urlalias, e.g. `/api/customer/v3/identity` → `<service>.api.base-path` property |
| REST entry flow `..._.services:<op>` | `api/<X>Controller` method; query params as a `@ParameterObject` record; X-IL headers via interceptor, not method params (except ones the logic uses) | |
| `api.priv:validate*` | Bean Validation on the request record + the same error code; or explicit checks in the service when rules are conditional (e.g. "all fields required unless `oib` is given") | conditional rules → a custom constraint or service-level check, with a test per branch |
| `api.pub` + `enterprise.pub` | `app/<x>/<X>Service` (interface + `Impl`), method named after the API operation | merge pass-through layers |
| `api.doc`, `enterprise.doc`, `adapter.*.doc`, generated `docTypes` | `domain/<x>/` records. One request + one response record per operation is usually enough; collapse identical layer docs | DTO field names = JSON names of the original response |
| `co.cdm.v2.technical:docResult` | `domain/common/Result` record (isSuccess, errorCode, errorDescription, errorDetails, sourceInfo) | |
| `adapter.<sys>.pub:<op>` | domain port `domain/<x>/<X>Repository` (or `<X>Client`) + `infra/jdbc/<X>Adapter` / `infra/client/<X>Client` | adapter method named after the procedure/endpoint |
| JDBC adapter + Java service | `JdbcTemplate`/`JdbcClient` code in the infra adapter (§3, §4) | |
| `pub.client:http`, REST connectors | `RestClient` bean + adapter | |
| `mapSourceErrorToResult` + `ERROR_CODES_V2` + `ERRORS_TO_HTTP_CODES` | `infra/error/ErrorCodesEnum` (oracleCode, appCode, HttpStatus, systemId, description) + `AdapterException` + `ErrorHandler` (`@RestControllerAdvice`) returning `{"result": Result}` | see `crosig-il-patterns.md` §3 |
| `beginService` / `endService` / `errorService` | interceptor + logging filter + exception handler | nothing in business code |
| `getConfigParameter("x.y")` | `@ConfigurationProperties` record | key names, never secret values |
| global variables `%name%` | property | ask for env values |
| ORA-04068 REPEAT loop | `RetryTemplate` bean (spring-boot `jdbc-procedures.md`) | |
| `INVOKE TIMEOUT` / `JDBCTimeout` | `CallableStatement.setQueryTimeout` / HTTP client timeouts | |
| JMS trigger | `@JmsListener` (+ controlled start/stop) | design first |
| Scheduled IS task (not in git) | Spring Batch + Quartz (spring-boot `spring-batch.md`) | ask for the schedule |

## 2. Built-in `pub.*` services → Java

Exact signatures: `grep -l '"pub.string:padLeft"' assets/wm-service-catalog/*.json`, then read that entry.

| wM | Java |
|---|---|
| `pub.flow:getLastError` | the caught exception |
| `pub.flow:setResponseCode`, `setResponse2`, `setResponseHeader(s)` | `ResponseEntity` status/body/headers (or the interceptor) |
| `pub.flow:getTransportInfo` | `HttpServletRequest` / `@RequestHeader` |
| `pub.flow:debugLog` | `log.atWarn()...` (SLF4J fluent) |
| `pub.flow:clearPipeline` | nothing |
| `pub.json:documentToJSONString` / `jsonStringToDocument` / `jsonStreamToDocument` | Jackson (Spring's `ObjectMapper`/`JsonMapper`; check the project's Jackson major version) |
| `pub.utils:generateUUID` | `UUID.randomUUID().toString()` |
| `pub.date:getCurrentDateString(pattern)` | `DateTimeFormatter.ofPattern(...).format(now)` — convert the pattern (Java `SimpleDateFormat` letters, mostly identical) and the time zone (IS default = server zone) |
| `pub.date:dateTimeFormat` / `dateTimeBuild` | `java.time` parse + format |
| `pub.math:toNumber(convertAs)`, `addInts`, `subtractInts`, `multiplyInts` | parse to the given type; int math is on **strings** in wM — invalid input throws |
| `pub.string:concat`, `replace`, `tokenize`, `substring`, `length`, `toUpper/Lower`, `trim`, `padLeft/Right`, `makeString` | `String` methods / `String.join` |
| `pub.string:base64Encode` / `base64Decode` | `Base64.getEncoder()` (`useNewLine=false` → plain encoder, not MIME) |
| `pub.string:bytesToString` / `stringToBytes` | `new String(bytes, charset)` — keep the encoding parameter |
| `pub.list:appendToDocumentList` / `appendToStringList` / `sizeOfList` | `List.add` / `size()` |
| `pub.document:documentToDocumentList`, `sortDocuments` | map entries / `Comparator` |
| `pub.io:stringToStream` | `InputStream` / just the String |
| `pub.client:http` | `RestClient` |
| `pub.client:soapClient` | Spring WS `WebServiceTemplate` / JAX-WS client generated from the `wsdl0` |
| `pub.jms:send` | `JmsTemplate` |
| `pub.mime:*` | `MimeMessageHelper` / multipart builders |

## 3. Porting a JDBC Java service (ExecuteService)

The Java service already contains the call. Keep the SQL text, parameter order, Oracle type
names and NULL handling **exactly**; change only the plumbing.

| IS Java | Spring |
|---|---|
| `IDataUtil.getString(cursor, "p_x")` | method parameter / request record field |
| `(Connection) IDataUtil.get(cursor, "$db_service_connection")` | `jdbcTemplate.execute(CallableStatementCreator, CallableStatementCallback)` — the template supplies the connection |
| `conn.prepareCall("{call CO4096.PKG.p_x(?,?,...)}")` | same string in the creator |
| `cs.setNull(i, Types.VARCHAR)` when null / `== 0` | keep identical (e.g. customer type `0` means null) |
| `TO_DATE(?, 'YYYY-MM-DD')` built into the call string | keep, or bind a `LocalDate` and remove the TO_DATE — but then test both |
| `conn.createStruct("CO4096.TYPE", attrs)` | same inside the creator |
| `registerOutParameter(n, Types.STRUCT, "CO4096.COWS_TP_R_...")` | same; map attributes by index in a `*Mapper` (`ResultMapper.fromStruct`) |
| `Types.ARRAY` OUT (`CO4096.COWS_TP_A_...`) | `cs.getArray(n)` → `Object[]` of `Struct`; **free the Array in finally** |
| CLOB OUT with JSON | read once with `getSubString`, free in finally, parse with Jackson |
| `catch (Exception e) { errorCode = "-1"; errorMessage = e.getMessage(); }` | let the `DataAccessException` propagate to the handler, which maps it to the same code the `-1` row produced |
| `JournalLogger.log(...)` | `log.atDebug()` |

REF CURSOR: there is no precedent in either codebase. If a procedure returns `SYS_REFCURSOR`,
register `OracleTypes.CURSOR` (or `Types.REF_CURSOR` with a recent ojdbc), read with a
`RowMapper`, close the `ResultSet` in finally; or use `SimpleJdbcCall.returningResultSet`.

`@Transactional(readOnly = true)` on read adapters; write procedures need a deliberate
transaction decision (the IS connection was usually `NO_TRANSACTION` = autocommit per call).
See spring-boot `jdbc-procedures.md` for the commit-vs-rollback behaviour change.

## 4. Select / CustomSQL adapters

Take the SQL from the decoded adapter (`wm_inspect.py show <adapter>`); bind `?` in the order of
`inputField` with the `inputJDBCType` types; output columns from `outputField`/`resultField`.

```java
return jdbcClient.sql("""
        SELECT steta_id, oznaka, broj, status
          FROM isco.ste_vsteta_co_crm_s ste
         WHERE ... steul.snk_id = :snkId AND brand = :brand
        """)
    .param("snkId", snkId)
    .param("brand", brand)
    .query((rs, n) -> new ClaimHeader(rs.getLong("steta_id"), ...))
    .list();
```

`maxRow` > 0 → `FETCH FIRST n ROWS ONLY` or `setMaxRows`. `queryTimeOut` → statement timeout.
Select adapters return `results[]` even for one row — check whether the flow takes `results[0]`.

## 5. Config, secrets, datasources

- One datasource per `co.config.jdbc:<Alias>` the service touches; name properties after the
  alias (`oldlegacycore`, `esb-env`). The URL/user come from env vars per environment.
- `CONFIG_PARAMETERS` keys → typed `@ConfigurationProperties` records with the same meaning
  (`<svc>.JDBCTimeout` → `<service>.jdbc.timeout`). Document the mapping in the analysis.
- Environment values as `${ENV_VAR:default}`, the datasource defaults pointing at the test
  database (as household does). Never copy a password, token or key from
  `CONFIG_PARAMETERS.properties`, the connection blobs or a Java service into code, tests or the
  analysis.

## 6. Things that change behaviour silently

Put each one that applies into the analysis as an explicit decision:

- JSON shape: absent vs null fields; numbers as strings; date formats (`flow-semantics.md` §5).
- HTTP status: config-driven, default 500 — a "fixed" 404 is a contract change.
- Error envelope `{"result": ...}` vs ProblemDetail.
- Validation: what the original really rejected (not what the doc types claim).
- Transactions: IS autocommit per adapter call vs a Spring transaction around several calls.
- Timeouts and retries: `JDBCTimeout` values, ORA-04068 retries, HTTP timeouts.
- Response headers `X-IL-flowID` / `X-IL-flowName`.
- Dropped fields: anything the flow removes from the response before serialising.
