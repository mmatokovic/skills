---
name: spring-boot
description: >
  Use when writing, reviewing, debugging, or setting up any Java backend service
  in the Crosig integration team. Covers REST controllers, JPA entities and
  repositories, Spring Batch 6 jobs, domain models and value objects, RFC 9457
  error responses, hexagonal architecture, Maven commands, local dev with Docker
  Compose, and unit or integration tests. Use even when "Spring Boot" is not
  mentioned — if the task involves a Java service, REST endpoint, JPA query,
  batch job, or code review in the integration team, this skill applies.
---

# Spring Boot — Crosig Integration Team

> Conventions for the integration team. Follow https://12factor.net/

## Reference Files

Load on demand — only when the task involves the specific topic:

| Load when… | File |
|---|---|
| Designing package structure, layer boundaries, or ports & adapters | `references/architecture.md` |
| Reviewing code, checking API contracts, or before merging a PR | `references/code-quality.md` |
| Working with aggregates, value objects, domain events, or DDD patterns | `references/domain-driven-design.md` |
| Writing or reviewing JPA entities, repositories, queries, or pagination | `references/jpa-patterns.md` |
| Implementing error handling, exception mappers, or error response format | `references/problem-details.md` |
| Building batch jobs, ETL pipelines, scheduled imports, or chunk processing | `references/spring-batch.md` |
| Reviewing code or writing Java in a project with Error Prone enabled, setting it up, or fixing `[CheckName]` findings | `references/error-prone.md` |
| Calling Oracle stored procedures with `JdbcTemplate`, CLOB/STRUCT out-params, or retrying on ORA- codes | `references/jdbc-procedures.md` |
| Setting up a project, fixing checkstyle/ArchUnit failures, naming classes, unit-testing a JDBC adapter, or writing a Boot 4 controller IT | `references/project-setup.md` |
| Writing slice tests (`@WebMvcTest`, `@RestClientTest`, `@JsonTest`), wiring Testcontainers (`@ServiceConnection`, dynamic properties), or speeding up a slow IT suite | `references/testing.md` |

## Local Development

Start infrastructure before running the app:

```bash
docker-compose -f docker/compose.yaml up
```

Brings up: Oracle DB, Keycloak, Zipkin, Prometheus, Grafana, OpenTelemetry collector. Start the app separately via IDE or Maven.

Add `testcontainers.reuse.enable=true` to `~/.testcontainers.properties` to speed up repeated local test runs.

## Package Layout

Projects use **CQRS at the API layer**. Standard layout under the root package:

| Package | Responsibility |
|---|---|
| `api/` | REST controllers |
| `app/` | Application services, MapStruct mappers |
| `domain/` | JPA entities, repository interfaces, DTOs |
| `infra/` | Error handling, security, logging, scheduling, external adapters, validation, web config |

Test packages mirror production packages exactly.

## Standard Stack

| Concern | Technology |
|---|---|
| Database | Oracle + Spring Data JPA/Hibernate + Liquibase migrations |
| Batch / scheduling | Spring Batch + Quartz (JDBC-backed) |
| External APIs | `RestClient` adapters + MapStruct |
| Logging | Logback + Logstash encoder (structured JSON) |
| Observability | OpenTelemetry → Zipkin (traces), Prometheus + Grafana (metrics) |
| Validation | Custom `ConstraintValidator` annotations |

## Testing

| Type | Pattern |
|---|---|
| Unit | `*Should.java` with behaviour method names, so class + method read as a sentence (`HouseholdAdapterShould.free_clob_when_procedure_returns_error`) — no `should_` prefix, no `*Test` suffix; name the class under test in full (`householdAdapter`, not `sut`/`adapter`). `@ExtendWith(MockitoExtension.class)`, never `@SpringBootTest` |
| Slice | `*IT.java` — `@WebMvcTest` for one controller, `@RestClientTest` for one outbound adapter, `@JsonTest` for one record's JSON. Faster than a full context; see `references/testing.md` |
| Integration | `*IT.java` — extend `BaseIntegrationTest` (Oracle XE Testcontainer + WireMock). Anything that starts a Spring context (`@SpringBootTest`, slices, `contextLoads`) is an IT, never `*Tests.java` |
| Architecture | ArchUnit in `src/test/.../archunit/` — enforce layering, naming, annotation rules |
| Contract | `ContractFreezeIT` — run before any change to controller response shapes or status codes |

**Gotchas:**
- Always add explicit `verify()` for `void` methods — lenient Mockito won't catch missing invocations
- End every unit test with `verifyNoMoreInteractions(mocks...)`, or `verifyNoInteractions(mock)` when the path must not touch it (e.g. validation fails before the repository is called)
- No shared fixtures: build request/response objects inside each test, not in fields set by `@BeforeEach`. Only `@Mock` / `@InjectMocks` live at class level
- Assert the whole object (`assertThat(response).isEqualTo(expected)`, records have `equals`), not property by property
- Never delete an ArchUnit rule to get the build green. If a rule must be off (e.g. `noDisabledTestRule` while `ContractFreezeIT` is `@Disabled`), comment it out with the reason and re-enable both together
- Provide HTTP Basic Auth on every IT request: `.headers(h -> h.setBasicAuth("user", "userpwd"))`
- Clean tables with `JdbcTemplate` in `@BeforeEach` — do not rely on transaction rollback

## Dependency Management

All versions declared in root `pom.xml`. Before adding anything:
1. Check for existing transitive dep: `./mvnw dependency:tree`
2. Verify Spring Boot compatibility via the official coordinates matrix