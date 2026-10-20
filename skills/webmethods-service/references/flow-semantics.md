# flow.xml — semantics and how each step becomes Java

`wm_inspect.py show|bundle` prints flow.xml as indented pseudo-code. This file explains what
each printed line means at runtime and what it turns into in Java. The runtime rules matter more
than the syntax: most migration bugs come from pipeline semantics that Java does not have.

## Contents
1. The pipeline (read this first)
2. Reading the script's pseudo-code
3. Step by step: INVOKE, MAP, transformers, SEQUENCE/TRY/CATCH, BRANCH, LOOP, REPEAT, EXIT
4. Values: %var% substitution, global variables, type codes
5. JSON output: what the client really receives
6. Raw XML reference (when you read flow.xml yourself)

## 1. The pipeline

A flow service has no local variables. Every step reads from and writes to one shared map, the
**pipeline**, keyed by name.

- **Anything not dropped stays.** A variable set in step 2 is still visible in step 40.
  Services that do not drop their temporaries leak them into the caller's pipeline.
- **INVOKE without an `in:` map passes the whole pipeline.** The callee picks its inputs by
  name. A field that happens to have the right name is an implicit argument — check the callee's
  signature for inputs the caller never mapped explicitly.
- **Outputs merge back by name and overwrite.** Two calls that both return `result` leave the
  second one's `result`.
- **Copying a document copies the reference.** `a = b` on a Document makes both names point at
  the same object; a later write into `a/x` also changes `b/x`. Java records hide this, so it
  only matters if the flow relies on the aliasing.
- **Field names are authoritative, types are not.** IS resolves paths by name at runtime. The
  `;type;dim;docRef` markers in flow.xml are design-time snapshots and are often stale (the same
  field shows as `;3.7` Long in one MAP and `;3.6` Integer in the next; doc refs point at doc types
  of other services). Take types from node.ndf signatures and from the code that produces the value.

**Translate the data flow, not the pipeline.** Work out, per service, which values come in, which
go out, and which temporaries exist only to pass data between two steps. Those become method
parameters, return values and local variables. Never port the pipeline as a `Map<String,Object>`.

## 2. Reading the script's pseudo-code

```
INVOKE <service>                     a service call (step)
  in:   target = source              input map: pipeline -> callee input
  out:  target = source              output map: callee output -> pipeline
MAP // comment                       a standalone map step
  a/b = c/d                          MAPCOPY (link)
  x := "200"                         MAPSET (set value); [%subst%] = %var% substitution,
                                     [global-vars] = IS global variables, [only-if-null] = OVERWRITE=false
  drop tmp                           MAPDELETE
  transformer <service>              MAPINVOKE inside a MAP, with its own in:/out:
[label] STEP ...                     the step's NAME: a BRANCH case label or an EXIT target
(DISABLED - skip)                    step is switched off — it does not run; leave it out
x[]                                  list (dim 1); x[][] = table (dim 2)
```

Comments after `//` are the developer's step comments in Designer — usually the best summary of intent.

## 3. Step by step

### INVOKE / transformer → method call

`INVOKE svc` with `in:`/`out:` maps is a method call: `in:` lines are arguments, `out:` lines
are assignments from the return value. A transformer (`MAPINVOKE`) is the same call written inside
a MAP step. `TIMEOUT="10"` on an INVOKE is a per-call timeout in seconds — carry it over (JDBC
query timeout, HTTP read timeout).

Built-in `pub.*` services: look up exact inputs/outputs in `assets/wm-service-catalog/<FOLDER>.json`
(grep the service name); the Java equivalents of the common ones are in `spring-mapping.md`.
Crosig `co.utils.*` services: see `crosig-il-patterns.md` — they are infrastructure, not business logic.

### SEQUENCE, TRY / CATCH / FINALLY → try / catch / finally

| Printed as | Runtime behaviour | Java |
|---|---|---|
| `TRY` … `CATCH` (siblings) | CATCH runs if anything in TRY fails | `try { } catch (Exception e) { }` |
| `FINALLY` | always runs | `finally { }` |
| `SEQUENCE exit-on=FAILURE` | run children in order, stop and fail at the first failure | plain block |
| `SEQUENCE exit-on=SUCCESS` | run children until one **succeeds**; fail only if all fail | old-style try/catch: outer SUCCESS holding [inner FAILURE = try, DONE = catch] |
| `SEQUENCE exit-on=DONE` | run every child, ignore failures | each child in its own try/catch that swallows |

In CATCH, `pub.flow:getLastError` gives `lastError` (`error` message, `errorType`, `service`,
`nestedErrorInfo/...` — the nested chain holds the root cause such as `ORA-04068: ...`).
`/lastError/nestedErrorInfo/nestedErrorInfo/error` is "the SQLException message two levels down".

### BRANCH → switch / if-else

`BRANCH switch /path` compares the **string value** of the variable against each child's label,
top to bottom; the first match runs, nothing else does.

| Label | Matches |
|---|---|
| `[true]`, `[200]`, `[OK]` | that exact string (a Boolean or number is compared as its string) |
| `[/^ORA-04068.*/]` | regex between the slashes; labels here carry their own `^`/`.*`, so port them with `Pattern.compile(...).matcher(v).find()` keeping the anchors |
| `[$null]` | variable missing or null — **not** an empty string |
| `[$default]` | anything not matched above (put it last in Java) |
| no match and no `$default` | the BRANCH does nothing |

`BRANCH on expressions` (`LABELEXPRESSIONS="true"`): each child's label is a boolean expression;
the first true one runs. `%a/b%` reads a pipeline path, `$null` is null, `==`/`!=` compare as
strings, `&&`/`||`/`!` as usual. `%x% == ""` and `%x% == $null` are different checks — keep both
when the flow has both.

A BRANCH child that is a single EXIT (e.g. `[$null] EXIT from=$parent signal=SUCCESS`) is an
early "skip this part" — usually an `if (x != null) { ... }` around the following code.

### LOOP → for

`LOOP over /a/items collect-into /b/out`:
- Inside the loop, the name `a/items` refers to **the current element**, not the list.
- With `collect-into`, whatever the body writes under `b/out` each iteration is appended to the output list.
- A null or missing input list means zero iterations (no error).
- **Copying out of an empty or missing list** (`out/x[] = in/y[]/x`, or a LOOP with
  `collect-into` that never runs) — whether the target list then exists as `[]`, is absent, or a
  later step fails on it decides between `"documents": []`, no field, and an error response.
  Do not guess: mark it [VERIFY] and settle it with a test call that returns zero rows.

```java
List<Out> out = new ArrayList<>();
for (Item item : nullToEmpty(a.items())) { out.add(map(item)); }
```

### REPEAT (`RETRY` in XML) → retry loop

`REPEAT count=N repeat-on=FAILURE back-off=S`: on failure, run the body again, up to N more
times (`-1` = unlimited), waiting S seconds between attempts. `repeat-on=SUCCESS`: keep running
the body while it succeeds, until an EXIT stops it or N repeats are done. The Crosig flows use
SUCCESS + EXIT to build a "retry on ORA-04068" loop — see `crosig-il-patterns.md` §5. In Spring this
is a `RetryTemplate` with a predicate (see the spring-boot skill's `jdbc-procedures.md`), not a hand-written loop.

### EXIT → return / break / continue / throw

| `from=` | Leaves | `signal=SUCCESS` | `signal=FAILURE` |
|---|---|---|---|
| `$parent` | the step that contains the EXIT (for an EXIT directly under a BRANCH, the BRANCH) | skip the rest of that step | fail that step → caught by the nearest TRY/CATCH or exit-on rule |
| `$loop` | the nearest LOOP or REPEAT | `break` | `break` + failure |
| `$iteration` | the current loop iteration | `continue` | — |
| `$flow` | the whole service | `return` | `throw` with `message=` text (`%var%` substituted) |
| `"<label>"` | the enclosing step with that NAME | as above | as above |

A failing `EXIT from=$flow` means the service ends with an exception. Whether a TRY/CATCH in the
*same* flow intercepts it is subtle — when it matters, check the original with a test call
before encoding either behaviour.

## 4. Values

- **`:= "literal"`** — a constant. `True`/`False` without quotes are Boolean objects;
  `{...}`/`[...]` are document/list literals.
- **`[%subst%]`** (`VARIABLES="true"`): `"%targetServiceOutput/oib%"` is replaced with the value at
  that path, **as a string**. A Long copied this way becomes a String in the output — which then
  shows up quoted in JSON (§5). `"%url%%basePath%"` is string concatenation.
  If the referenced variable does not exist, check what the original produced before choosing
  null vs empty string.
- **`[global-vars]`** (`GLOBALVARIABLES="true"`): `%name%` comes from IS Global Variables
  (Settings → Global Variables, not in git). → `application.properties` key with `${ENV}` placeholder; ask for the per-environment value.
- **`[only-if-null]`** (`OVERWRITE="false"`): a default — `x = x != null ? x : value`.
- **`drop x`**: pipeline hygiene. No Java equivalent, **except** when it removes a field from the
  response document (§5).

Path type codes (only visible with `--types`): `1` String, `2` Document, `3` Object, `3.1` Boolean,
`3.4` Double, `3.6` Integer, `3.7` Long, `3.9` Date, `3.10` byte[], `3.11` BigDecimal, `4` doc
reference (4th part = doc type). Dim `0`/`1`/`2` = scalar/list/table. `name(1)` = second declaration
of the same field (object vs document) — the script strips the suffix; it is the same variable.

## 5. JSON output: what the client really receives

REST entry services serialise `_generatedResponse` with `pub.json:documentToJSONString` and send it
with `pub.flow:setResponse2`. The JSON follows the **runtime pipeline**, not the doc type:

- A field that was never set (or was dropped) is **absent**, not `null` → configure the omission
  globally in `JacksonConfig` (`withConfigOverride(<Type>.class, NON_NULL/NON_EMPTY)`, the IL blueprint
  pattern — no annotations on records), unless you confirm the original wrote `null`.
- A String holding digits is written **quoted** (`"customerID":"123"`), a Long unquoted. Values
  set through `%subst%` are always Strings. Decide each response field's JSON type from how the
  flow produced it, and confirm with a captured response from the running IS (Kibana / b2b logs / a test call).
- Dates: `java.util.Date` objects serialise in IS's format; most flows format them first with
  `pub.date:*` / `co.utils.*.date:*` and the given pattern — copy the pattern exactly.
- Booleans stored as Boolean objects (`isSuccess := True`) are JSON booleans; set as string `"true"` they are quoted.

Getting these wrong breaks consumers while every test you wrote yourself still passes. Freeze the
contract from a real response (see `testing.md`).

## 6. Raw XML reference

Only needed when reading flow.xml without the script.

```xml
<FLOW VERSION="3.0" CLEANUP="true">
  <SEQUENCE EXIT-ON="FAILURE" FORM="TRY"> ... </SEQUENCE>
  <SEQUENCE EXIT-ON="FAILURE" FORM="CATCH"> ... </SEQUENCE>
  <INVOKE SERVICE="ns:svc" VALIDATE-IN="$none" VALIDATE-OUT="$none" TIMEOUT="">
    <MAP MODE="INPUT"> <MAPCOPY FROM="/a;1;0" TO="/b;1;0"/> </MAP>
    <MAP MODE="OUTPUT"> ... </MAP>
  </INVOKE>
  <MAP MODE="STANDALONE">
    <MAPTARGET>…schema snapshot, ignore…</MAPTARGET> <MAPSOURCE>…ignore…</MAPSOURCE>
    <MAPINVOKE SERVICE="pub.date:getCurrentDateString" INVOKE-ORDER="0">
      <MAP MODE="INVOKEINPUT"> <MAPSET FIELD="/pattern;1;0" VARIABLES="false" OVERWRITE="true">
        <DATA ENCODING="XMLValues"><Values><value name="xml">yyyy-MM-dd</value></Values></DATA></MAPSET></MAP>
      <MAP MODE="INVOKEOUTPUT"> <MAPCOPY FROM="/value;1;0" TO="/today;1;0"/> </MAP>
    </MAPINVOKE>
    <MAPDELETE FIELD="/tmp;1;0"/>
  </MAP>
  <BRANCH SWITCH="/x"> <MAP NAME="$null" .../> </BRANCH>
  <BRANCH LABELEXPRESSIONS="true"> <SEQUENCE NAME="%a% != null" .../> </BRANCH>
  <LOOP IN-ARRAY="/in" OUT-ARRAY="/out"> ... </LOOP>
  <RETRY COUNT="10" BACK-OFF="" LOOP-ON="SUCCESS"> ... </RETRY>
  <EXIT FROM="$flow" SIGNAL="FAILURE" FAILURE-MESSAGE="%msg%"/>
</FLOW>
```

`MAPSET` values are always `ENCODING="XMLValues"` in this repo: the value is the `name="xml"`
entry (`<value>`, `<Boolean>`, `<array>`, `<record>`); the sibling `<record name="type">` only
describes the field. `DISABLED="true"` can appear on any step, MAPCOPY or MAPINVOKE.
