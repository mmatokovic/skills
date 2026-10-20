# Project setup — build, naming, ArchUnit, test techniques

Team-wide conventions every Spring service follows, so code passes `./mvnw clean verify` the first
time. Error Prone details are in `error-prone.md`; procedure calls in `jdbc-procedures.md`.

## Contents
1. Build and tooling
2. Naming rules
3. ArchUnit rule set
4. Unit tests
5. Unit-testing a JDBC adapter without a database
6. Controller integration test (Boot 4)

## 1. Build and tooling

- `spring-boot-starter-parent` 4.x, Java 25, groupId `hr.crosig.integration`; multi-module when a
  batch or second deployable is expected (`<service>-api`, `<service>-batch`).
- `maven-compiler-plugin`: `<parameters>true</parameters>`; annotation processors
  spring-boot-configuration-processor, lombok, Error Prone (`error-prone.md`).
- Surefire runs `**/*Should.java` and `**/*Rule.java` (unit + ArchUnit); Failsafe runs `**/*IT.java`.
- Checkstyle (root `checkstyle.xml`) runs at the **compile** phase and fails the build on main
  sources: no star/unused/redundant imports, no tabs, no trailing whitespace, newline at EOF,
  `FinalClass`, `HideUtilityClassConstructor`, `NeedBraces`, `DeclarationOrder`,
  `EmptyLineSeparator` (no double blank lines), `MutableException`, `HiddenField`, `RequireThis`
  (only for overlapping names), naming checks. Suppress a single case with
  `@SuppressWarnings("checkstyle:<CheckName>")`.
- `.editorconfig`: LF, 4 spaces, lines ≤ 150, no import collapsing.
  `lombok.config`: `lombok.addLombokGeneratedAnnotation = true`.
- Jackson 3 with Boot 4: databind is `tools.jackson.*`; annotations stay
  `com.fasterxml.jackson.annotation.*`. Don't mutate `ObjectNode` trees (`fieldNames()` is gone,
  `asText()` deprecated).
- `application.properties`; every environment-specific value as `${ENV_VAR}` **without a default
  for secrets**.
- Layered jar (`spring-boot-maven-plugin` layers) and a two-stage `eclipse-temurin:25` Dockerfile
  (`-Djarmode=tools extract --layers --launcher`, then `JarLauncher`).

## 2. Naming rules

| Kind | Rule |
|---|---|
| Controller | `*Controller`, `@RestController`, in `api/`, methods return `ResponseEntity` |
| Use case | `*Service` interface + `*ServiceImpl` in the **same** package (no `impl/` package) |
| Port / persistence | `*Repository` (domain interface); its JDBC/external implementation `*Adapter` with `@Repository` |
| Request/response | `*Request`, `*Response` records — never `*DTO`, `*Params` |
| Mapper | `*Mapper`, final utility class, private constructor |
| Configuration | `*Properties` = record with `@ConfigurationProperties`; `*Config` = `@Configuration(proxyBeanMethods = false)` |
| Enum | ends in `Enum`; non-static fields private final |
| Utility | `*Utils`, only static methods, private constructor; no `*Util`, no `*Helper` |
| Exception | `*Exception` extends `RuntimeException`, immutable fields |
| Interfaces | no `I*` prefix, no `*Interface` suffix |
| Fields | full names of the type (`walletRepository`, not `repo`) |

## 3. ArchUnit rule set

One class per concern in `src/test/java/<root>/archunit/`, each `ArchRule` a `public static final`
field, `@AnalyzeClasses(packagesOf = <App>Application.class)`:

| Class | Enforces |
|---|---|
| `ArchitectureRule` | domain depends on nothing else; app not on api; infra not on api; every class in api/app/domain/infra; no `impl`/`utils` packages; `@RestController` only in `api` |
| `NamingRule` | the table in §2, plus test classes named `*Should` or `*IT` |
| `AnnotationRule` | `*Controller` is `@RestController`; no `@Controller` |
| `GeneralRule` | no `System.out/err`, no generic exceptions, no Joda-Time, no java.util.logging; controller methods return `ResponseEntity`; static fields final |
| `ProxyRule` | `@Transactional` methods public, no self-invocation |
| `TestClassRule` | test classes/methods package-private; no JUnit `Assertions` (AssertJ only); no `@Transactional` on test classes; no `@Disabled` (may be parked with a comment while a contract test is disabled — re-enable both together) |
| `EnumClassRule`, `ExceptionClassRule`, `UtilityClassRule`, `DeprecatedRule` | as their names say |

Never delete a rule to get green.

## 4. Unit tests

- `<ClassUnderTest>Should`, package-private class and methods, snake_case behaviour names without
  a `should_` prefix (`throw_api_exception_when_type_is_unsupported`).
- given / when / then separated by blank lines; AssertJ only; whole-object asserts on records.
- `@ExtendWith(MockitoExtension.class)`, `@Mock` + `@InjectMocks`; finish with `verify(...)` +
  `verifyNoMoreInteractions(...)` or `verifyNoInteractions(...)`; `this.` on test fields.
- Exceptions: `assertThatExceptionOfType(X.class).isThrownBy(...).withMessage(...)`;
  `.isSameAs(error)` when the original must be rethrown.

## 5. Unit-testing a JDBC adapter without a database

Mock `JdbcTemplate`, `Connection`, `CallableStatement` and the `Struct`s; build the adapter by
hand with real properties and a real retry template (delays `Duration.ZERO`); make the mocked
`execute` run the adapter's own creator and callback:

```java
when(this.jdbcTemplate.execute(any(CallableStatementCreator.class), any(CallableStatementCallback.class)))
    .thenAnswer(invocation -> {
        CallableStatementCreator creator = invocation.getArgument(0);
        CallableStatementCallback<Object> callback = invocation.getArgument(1);
        return callback.doInCallableStatement(creator.createCallableStatement(this.connection));
    });
```

Then verify every JDBC call exactly (call string, `setQueryTimeout`, each bind,
`registerOutParameter` with type names, `execute`); capture STRUCT attributes with
`ArgumentCaptor.forClass(Object[].class)`; use `javax.sql.rowset.serial.SerialClob` for CLOB
content or `mock(Clob.class)` to verify `free()`. Simulate Oracle errors as
`new UncategorizedSQLException("CallableStatementCallback", "<call>", new SQLException(msg, "72000", 4068))`,
and add one whose `SQLException` has a non-SQL cause (see `jdbc-procedures.md`, retry).

## 6. Controller integration test (Boot 4)

Pins the raw JSON and status codes, which record-equality unit tests cannot see.

```java
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;   // moved in Boot 4
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.json.JsonCompareMode;

@SpringBootTest
@AutoConfigureMockMvc
class WalletControllerIT {
    @Autowired private MockMvc mockMvc;
    @MockitoBean private WalletRepository walletRepository;     // mock the port, not the service
    // mockMvc.perform(get(url)...).andExpect(status().isOk())
    //     .andExpect(content().json("""{...}""", JsonCompareMode.STRICT));
}
```

A `@SpringBootTest` context still configures the datasource: make sure the test profile does not
need a reachable database, rather than adding real connection defaults to `application.properties`.
