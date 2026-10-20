# Testing — slices, Testcontainers wiring, fast suites

Covers the level between a Mockito unit test (`*Should`, `project-setup.md` §4) and a full
`BaseIntegrationTest` IT: Spring **slice** tests, how to wire containers, and how to keep the IT
suite fast. Naming, assertion style and ArchUnit rules from `project-setup.md` still apply.

## Contents
1. Which level
2. Slice tests: `@WebMvcTest`, `@RestClientTest`, `@JsonTest`
3. Testcontainers wiring
4. Keeping the suite fast

## 1. Which level

| Testing… | Level | Name |
|---|---|---|
| business logic, mappers, adapters with mocked JDBC | Mockito unit, no Spring | `*Should` |
| controller mapping, validation, error JSON, security | `@WebMvcTest` slice | `*IT` |
| a `RestClient` adapter against a stubbed partner | `@RestClientTest` slice | `*IT` |
| a request/response record's exact JSON | `@JsonTest` slice | `*IT` |
| the full request path with Oracle and WireMock | `BaseIntegrationTest` | `*IT` |

**Every test that starts a Spring context is named `*IT`**, slices included — Surefire runs only
`*Should`/`*Rule`, so a slice named `*Should` would run without Failsafe's lifecycle and break the
naming rule. Slices are still much faster than a full context: they load one layer only.

## 2. Slice tests

With Boot 4 the slice annotations live in per-technology test modules — add
`spring-boot-starter-webmvc-test` (and the `restclient` test starter for `@RestClientTest`) and let
the IDE resolve imports; `AutoConfigureMockMvc` already moved the same way (`project-setup.md` §6).

### `@WebMvcTest` — one controller

Loads controllers, `@RestControllerAdvice`, filters and converters only. Services and adapters are
**not** loaded: mock the next layer with `@MockitoBean`.

```java
@WebMvcTest(WalletController.class)
@Import(SecurityConfig.class)                       // not picked up automatically → surprise 401s
class WalletControllerIT {

    @Autowired
    private MockMvcTester mockMvc;                   // AssertJ-style, Boot 3.4+

    @MockitoBean
    private WalletService walletService;

    @Test
    void return_problem_detail_when_wallet_does_not_exist() {
        when(this.walletService.find("W-1")).thenThrow(new WalletNotFoundException("W-1"));

        assertThat(this.mockMvc.get().uri("/api/v1/wallets/W-1")
                .headers(h -> h.setBasicAuth("user", "userpwd")))
            .hasStatus(HttpStatus.NOT_FOUND)
            .bodyJson().isLenientlyEqualTo("""
                {"status":404,"title":"Not Found"}
                """);
    }
}
```

Good for: status codes, `@Valid` failures, RFC 9457 bodies from the exception handler
(`problem-details.md`), auth (no credentials → 401, wrong role → 403). Pin the full response shape
with `JsonCompareMode.STRICT` where the contract matters.

### `@RestClientTest` — one outbound adapter

Auto-configures `RestClient.Builder` with a `MockRestServiceServer`: an in-process stub, no port,
no WireMock.

```java
@RestClientTest(PartnerAdapter.class)
class PartnerAdapterIT {

    @Autowired
    private PartnerAdapter partnerAdapter;

    @Autowired
    private MockRestServiceServer server;

    @Test
    void map_partner_error_to_api_exception() {
        this.server.expect(requestTo("/partners/42"))
            .andRespond(withStatus(HttpStatus.SERVICE_UNAVAILABLE));

        assertThatExceptionOfType(PartnerUnavailableException.class)
            .isThrownBy(() -> this.partnerAdapter.find(42L));
        this.server.verify();
    }
}
```

**Gotcha:** it only intercepts clients built from the **injected `RestClient.Builder`**. An
adapter that calls `RestClient.create()` bypasses the stub and makes real calls — inject the
builder. If the adapter needs config (`*Properties`), add it with
`@EnableConfigurationProperties` or `@TestPropertySource`.

Use WireMock in `BaseIntegrationTest` instead when the test spans several components, needs a real
port, or the client is not a Spring `RestClient`.

### `@JsonTest` — one record's wire format

```java
@JsonTest
class WalletResponseJsonIT {

    @Autowired
    private JacksonTester<WalletResponse> json;

    @Test
    void write_amount_as_string_and_omit_nulls() throws Exception {
        assertThat(this.json.write(new WalletResponse("W-1", new BigDecimal("10.50"), null)))
            .isEqualToJson("""
                {"id":"W-1","amount":"10.50"}
                """);
    }
}
```

Use when a field name, date format or null handling is part of a contract. Boot 4 uses Jackson 3
(`tools.jackson.*`); annotations remain `com.fasterxml.jackson.annotation.*`.

## 3. Testcontainers wiring

**`@ServiceConnection` first.** Boot has connection-details factories for JDBC containers (Oracle
included), Kafka, RabbitMQ, Redis, Elasticsearch, Zipkin, OTLP and more. With it you register **no**
datasource properties:

```java
@Container
@ServiceConnection
static OracleContainer oracle = new OracleContainer("gvenzl/oracle-xe:21-slim-faststart");
```

Use the same image and container class as `BaseIntegrationTest`. Decide where every other value
goes:

| The value is… | Put it in |
|---|---|
| connection details of a container with a factory | nowhere — `@ServiceConnection` |
| known only after a container starts (mapped port of a factory-less container, WireMock base URL) | a `DynamicPropertyRegistrar` bean (Boot 3.4+), or `@DynamicPropertySource` with lazy suppliers |
| known when writing the test (feature flags, scheduler off, log levels, test credentials) | `application-test.properties` + `@ActiveProfiles("test")` |

```java
@Bean
DynamicPropertyRegistrar partnerProperties(WireMockServer wireMock) {
    return registry -> registry.add("partner.base-url", wireMock::baseUrl);
}
```

Reject: static values inside `@DynamicPropertySource`; fixed host ports
(`withFixedExposedPorts`, hard-coded `1521`) — they clash in parallel and CI runs.

**No Docker locally:** `@Testcontainers(disabledWithoutDocker = true)` skips instead of failing. In
Jenkins these tests must run — a skipped IT in CI is false confidence.

## 4. Keeping the suite fast

Spring caches an application context and reuses it for every test class with the **same**
configuration. The cache key includes: configuration classes, active profiles, test properties,
and **every `@MockitoBean` / `@MockitoSpyBean`**. Any difference starts a new context.

- Put shared mocks and properties in `BaseIntegrationTest`; a `@MockitoBean` added to one IT class
  forks the cache and pays a full startup again.
- No `@DirtiesContext` — fix the isolation problem (clean tables in `@BeforeEach`) instead.
- **One container per suite**: a `static` container in `BaseIntegrationTest`, not one per class.
  `testcontainers.reuse.enable=true` (SKILL.md) also keeps it across local runs.
- Diagnose cache misses with `logging.level.org.springframework.test.context.cache=DEBUG` — it
  logs hits, misses and the cache size.
- Prefer a slice (§2) over a full-context IT when only one layer is under test.
