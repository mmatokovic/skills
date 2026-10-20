# Tests for a migrated service

The goal of the tests is **"behaves like the wM service did"**, not "behaves like I think it
should". Write tests in the team style (spring-boot `references/project-setup.md`): `<Class>Should` unit
tests with behaviour method names, the adapter tested with mocked JDBC objects running the real
lambdas, ArchUnit rules, `ContractFreezeIT`, `*IT` for Spring-context tests. The
migration-specific cases are listed in `il-blueprint.md` §10. This file
covers where the expected behaviour comes from.

## 1. Sources of truth, in order

1. **The wM test package** — `<api>-il/vN/test/<Package>_TEST/resources/test/setup/WmTestSuite.xml`
   plus `data/*.xml`. Cases the original team already wrote, with mocks and expected outputs.
2. **Captured traffic** — real request/response pairs from the running IS (Kibana / the
   b2b-elastic-logs skill, or a call against TEST). The only reliable source for JSON shape and
   HTTP status.
3. **The analysis** — one test per branch in the flow: every BRANCH label, every error code row
   for the service, every validation rule, the retry path, the null/absent cases.

Many packages have no test package (aoak v4, for one) or none for the operation. Then the tests
come from 2 and 3 only: say so in the analysis, and ask for captured traffic before the contract
tests — tests built only from your own reading of the flow cannot catch a misreading.

## 2. Converting a WmTestSuite case

```xml
<webMethodsTestCase name="TC_getClaimsData_Bad_Request">
  <mock folder="pub.client" name="http">
    <pipeline filename="resources/test/data/getClaimsData_http_Bad_Request.xml"/>
  </mock>
  <service folder="co.crm.v2.api.pub" name="getClaimsData">
    <input><file filename="resources/test/data/co_crm_v2_api_pub_getClaimsData_Bad_Request_input.xml"/></input>
    <expected><file filename="resources/test/data/co_crm_v2_api_pub_getClaimsData_Bad_Request_output.xml"/></expected>
  </service>
</webMethodsTestCase>
```

| WmTestSuite | Spring test |
|---|---|
| `service` under test (`api.pub`/`adapter.pub`) | the class that replaced it (service or adapter) |
| `mock` of an adapter / `pub.client:http` / `mapSourceErrorToResult` | Mockito stub of the port (unit test) or WireMock stub / Testcontainers data (IT). A mocked `mapSourceErrorToResult` means the test pins the error code — assert that code |
| `input` file (`IDataXMLCoder`) | the request record built inside the test |
| `expected` file | the expected response record / `Result`, asserted as a whole object |
| `TC_<name>` | one test method named per the spring-boot skill's unit-test naming rule, describing the behaviour the case pins |

`IDataXMLCoder` reading: `<record name="x">` = object, `<value name="a">` = String,
`<number name="n" type="java.lang.Integer">` = typed number, `<array>` = list, `<null>` = null.

Test packages also invoke `wm.ps.serviceMock:loadMock` / `clearMock` inside flows — same idea:
those are mocks of the named service.

## 3. Contract test

- Put the original OpenAPI (from the `openapi` file of an OpenAPI provider, or exported from the
  RAD / API Gateway) into `src/test/resources/openapi.json` and keep `ContractFreezeIT` green
  (spring-boot skill). Differences in paths, params, required flags or response schemas are
  contract changes — they need a decision, not a quiet fix.
- Add at least one IT per operation that asserts the **raw JSON** of a captured original response
  (`JSONAssert`/`JsonContent` strict on field presence), so absent-vs-null and string-vs-number
  differences fail the build. A record-equality test cannot see them.
- Assert the X-IL response headers and the HTTP status for each error code the service can return.

## 4. Minimum set per migrated operation

- happy path (from WmTestSuite or captured traffic)
- each validation rule the `validate*` flow enforces → its error code + status
- each backend error code row in `ERROR_CODES_V2` for this endpoint → mapped code + status, plus the unknown-code fallback
- backend returns nothing / null output (the `[$null]` branches)
- retry: ORA-04068 retried then success; non-retryable error not retried; with a cause chain like real ojdbc (spring-boot `jdbc-procedures.md`)
- timeout (ORA-01013 / HTTP timeout) → its code
- lists: empty, one, many (LOOP + collect-into)
