# Error Prone — Setup, Triage, and Common Findings

Error Prone is a javac plugin that plugs into `maven-compiler-plugin`. Findings appear as
compiler errors (`error:`) or warnings (`warning:`) with the format
`[CheckName] ... (see https://errorprone.info/bugpattern/<CheckName>)`.

---

## Setup — adding Error Prone to a project

### Prerequisites
- Runs on JDK 21+. Crosig projects on JDK 25 are fine.
- `-XDaddTypeAnnotationsToSymbol=true` is only needed on JDK 21 — leave it out on JDK 25+.

### Root/parent `pom.xml`

```xml
<properties>
  <error-prone.version>2.50.0</error-prone.version>
</properties>

<build>
  <pluginManagement>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-compiler-plugin</artifactId>
        <configuration>
          <parameters>true</parameters>
          <annotationProcessorPaths>
            <path>
              <groupId>org.springframework.boot</groupId>
              <artifactId>spring-boot-configuration-processor</artifactId>
            </path>
            <path>
              <groupId>org.projectlombok</groupId>
              <artifactId>lombok</artifactId>
            </path>
            <path>
              <groupId>com.google.errorprone</groupId>
              <artifactId>error_prone_core</artifactId>
              <version>${error-prone.version}</version>
            </path>
          </annotationProcessorPaths>
          <compilerArgs>
            <arg>
              -Xplugin:ErrorProne
              -XepAllDisabledChecksAsWarnings
              -Xep:PrivateConstructorForUtilityClass:OFF
              -Xep:Var:OFF
              -Xep:IdentifierName:OFF
              -Xep:VarWithPrimitive:OFF
              -Xep:Java8ApiChecker:OFF
              -Xep:AddNullMarkedToClass:OFF
              -Xep:ImmutableMemberCollection:OFF
              -Xep:UnnecessarySemicolon:OFF
            </arg>
            <arg>-XDcompilePolicy=simple</arg>
            <arg>--should-stop=ifError=FLOW</arg>
            <!-- Remove this line on JDK 25+, only needed on JDK 21 -->
            <arg>-XDaddTypeAnnotationsToSymbol=true</arg>
          </compilerArgs>
        </configuration>
      </plugin>
    </plugins>
  </pluginManagement>
</build>
```

Put it in the root/parent POM — don't duplicate per module. If `compilerArgs` already exist
(e.g. `-parameters`), keep them.

### Annotation processors — the most common cause of a broken build

Once `annotationProcessorPaths` exists, javac **stops** discovering processors on the
classpath. Every processor must be listed explicitly, otherwise the build fails with
"cannot find symbol" (missing Lombok getters, MapStruct mappings, etc.).

| Dependency present | Add to `annotationProcessorPaths` |
|---|---|
| `org.projectlombok:lombok` | `lombok` (version managed by Spring Boot parent) |
| `org.mapstruct:mapstruct` | `mapstruct-processor` — **after** Lombok |
| Lombok + MapStruct together | also `lombok-mapstruct-binding` |
| `spring-boot-configuration-processor` | same artifact |
| `hibernate-jpamodelgen` | same artifact |

Order: Lombok before MapStruct. Error Prone can go anywhere in the list.

### `.mvn/jvm.config`

Create at the project root (next to `pom.xml`) and **commit it** — CI needs it too.
Symptom it's missing: `IllegalAccessError ... does not export com.sun.tools.javac...`.

```
--add-exports jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED
--add-exports jdk.compiler/com.sun.tools.javac.file=ALL-UNNAMED
--add-exports jdk.compiler/com.sun.tools.javac.main=ALL-UNNAMED
--add-exports jdk.compiler/com.sun.tools.javac.model=ALL-UNNAMED
--add-exports jdk.compiler/com.sun.tools.javac.parser=ALL-UNNAMED
--add-exports jdk.compiler/com.sun.tools.javac.processing=ALL-UNNAMED
--add-exports jdk.compiler/com.sun.tools.javac.tree=ALL-UNNAMED
--add-exports jdk.compiler/com.sun.tools.javac.util=ALL-UNNAMED
--add-opens jdk.compiler/com.sun.tools.javac.code=ALL-UNNAMED
--add-opens jdk.compiler/com.sun.tools.javac.comp=ALL-UNNAMED
```

**Exception:** if the compiler plugin uses `<fork>true</fork>` or `maven-toolchains-plugin`,
`jvm.config` doesn't reach the compiler. Add the same options to `compilerArgs` with a
`-J` prefix: `<arg>-J--add-exports=jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED</arg>`.

### Severity and turning checks off

Syntax: `-Xep:<CheckName>[:OFF|WARN|ERROR]`, inside the same `<arg>` as `-Xplugin:ErrorProne`.
Turning a check off globally is a last resort. Always add a POM comment with reason and ticket:

```xml
<!-- JavaUtilDate: legacy Oracle DAO layer, ticket ASW-123 -->
-Xep:JavaUtilDate:OFF
```

### Patching (bulk automatic fixes)

For mechanical findings, Error Prone can apply its own suggestions without editing the POM:

```bash
# Generate a patch file for review
mvn -q clean compile test-compile \
  -Derrorprone.args="-XepPatchChecks:MissingOverride,DefaultCharset -XepPatchLocation:$(pwd)"
# review error-prone.patch, then: patch -p0 -u -i error-prone.patch

# Or apply directly in source
mvn -q clean compile test-compile \
  -Derrorprone.args="-XepPatchChecks:MissingOverride -XepPatchLocation:IN_PLACE"
```

Always review `git diff` before committing. For `DefaultCharset`, verify UTF-8 is correct
at that boundary.

---

## Triage — fixing findings

Run `mvn -q clean compile test-compile` to collect findings. Group by `[CheckName]` —
the same check usually has the same fix everywhere.

For each group, decide:

- **Fix** — the default. Apply `Did you mean` only if correct in context. For `DeadException`
  it suggests `throw new RuntimeException(...)` — use a custom exception instead
  (`BusinessException`, `ResourceNotFoundException`).
- **Suppress** — only for proven false positives (JPA, Spring, Jackson reflection). At the
  narrowest scope (method or field, **never class**) and always with a reason:
  ```java
  @SuppressWarnings("UnusedMethod") // called by Spring via @Scheduled
  ```
- **Escalate** — if the fix changes behavior (public API, data format, time zone, charset
  at a system boundary), propose and ask before applying.

Never turn a check off globally without explicit agreement. Record the reason in a POM comment.

### Report format

```
[DefaultCharset] 4× warning — fixed: StandardCharsets.UTF_8 (DocumentService, ZipExporter)
[UnusedMethod] 1× warning — suppressed: onStartup() is called by Spring (@EventListener)
[FutureReturnValueIgnored] 2× warning — needs decision: see below

Open:
- ConversionScheduler:88 — result of @Async call is ignored; log the error or wait for it?
```

---

## Common findings in Spring Boot code

Default severities per errorprone.info 2.50.0.

### Errors — build fails

**DeadException** — exception created but not thrown. Add `throw`, using a custom exception
(`BusinessException`, `ResourceNotFoundException`), not `RuntimeException`.

**EqualsHashCode** — `equals` without `hashCode`. Add `hashCode` over the same fields
(`Objects.hash(...)`). For DTOs consider a `record`. For JPA entities, don't generate
`equals/hashCode` over all fields (lazy collections, mutable ID).

**BoxedPrimitiveEquality** — `==` on `Integer`/`Long` etc. Works for small values
(cache −128..127), fails in production. Replace with `Objects.equals(a, b)` or unbox if
null isn't possible.

**ReturnValueIgnored / CheckReturnValue** — ignored result of a side-effect-free method
(`str.trim()`, `optional.map(...)`, `BigDecimal.add`). Almost always a real bug: assign or
use the result.

### Warnings

**BooleanParameter** — off by default, but `-XepAllDisabledChecksAsWarnings` turns it on.
It wants `/* name= */` comments on boolean literal arguments (`new Result(/* isSuccess= */false, ...)`).
The team doesn't want those comments in code, so don't add them. Turn the check off in the POM
with a comment: `<!-- BooleanParameter: team doesn't use inline argument comments -->`
`-Xep:BooleanParameter:OFF`.

**DefaultCharset** — `getBytes()`, `new String(bytes)`, `new InputStreamReader(in)`,
`FileReader` without a charset. On OpenShift the container charset isn't guaranteed UTF-8,
breaking Croatian characters (č, ć, ž, š, đ). Add `StandardCharsets.UTF_8` — except at
a boundary with a system that uses a different charset (e.g. legacy windows-1250); ask there.

**StringCaseLocaleUsage** — `toLowerCase()`/`toUpperCase()` without a `Locale`. For
identifiers, keys, enum names, HTTP headers: `Locale.ROOT`. For user-facing text:
`Locale.of("hr", "HR")`.

**JavaTimeDefaultTimeZone** — `LocalDate.now()`, `LocalDateTime.now()` without a zone. In
a container the zone is usually UTC, so "today" just after midnight Zagreb time comes out as
yesterday. In services, inject a `Clock` bean (testable); otherwise
`ZoneId.of("Europe/Zagreb")`. Treat as a behavior change and call it out.

**JavaUtilDate** — legacy `java.util.Date`. In new code, use `java.time`. In existing
DAO/JDBC/SOAP code where the API requires it, don't refactor in passing — suppress locally
with a reason or agree to turn it off for that module.

**CatchAndPrintStackTrace** — `e.printStackTrace()`. Replace with
`log.error("<context>", e)` (`@Slf4j`). Consider whether the exception should propagate
instead of being swallowed.

**EmptyCatch** — empty `catch`. Log, propagate, or if ignoring is intentional explain why
in a comment and name the variable `ignored`.

**FutureReturnValueIgnored** — ignored `Future`/`CompletableFuture` (e.g. result of an
`@Async` method or `executor.submit`). Exceptions disappear silently. Add
`.whenComplete((r, ex) -> { if (ex != null) log.error(..., ex); })`, wait for the result,
or make the method log its own errors.

**IntLongMath** — `int` arithmetic converted to `long`, so overflow happens before the
conversion (e.g. `seconds * 1000`). Make one operand a `long` (`1000L`) or use
`Duration`/`TimeUnit`.

**ReferenceEquality** — `==` on objects that define `equals`. Replace with `Objects.equals`;
for enums `==` is correct (the check doesn't flag them).

**OperatorPrecedence** — mixing `&&`/`||` or bitwise operators without parentheses. Add
parentheses that express the intent; if intent isn't clear it may be a bug — ask.

**MissingOverride** — add `@Override`. Mechanical; good candidate for patch mode.

**UnusedVariable / UnusedMethod** — unused member. Before deleting, check:
- JPA: `protected` no-arg constructors, Hibernate-mapped fields
- Spring: methods with `@Scheduled`, `@EventListener`, `@PostConstruct`, `@Bean`; fields with `@Value`
- Jackson: fields/setters used by (de)serialization
- methods referenced only from SpEL or webMethods/SOAP integration

If truly dead, delete it — the team doesn't want dead code. If used via reflection, suppress
at method/field level with a reason.

---

## Common mistakes

- **Lost annotation processors** — once `annotationProcessorPaths` exists, javac ignores
  processors on the classpath. If Lombok getters vanish after setup, the processor wasn't
  listed.
- **`.mvn/jvm.config` not committed** — works locally, fails on Jenkins/OpenShift.
- **`Did you mean` applied blindly** — `DeadException` suggests `RuntimeException`; team
  requires a custom exception.
- **Class-level `@SuppressWarnings`** — silences all future findings on that class. Always
  suppress at method or field scope.
- **Global check disable without a comment** — `-Xep:CheckName:OFF` always needs a POM
  comment with reason and ticket.