# Migration analysis — template

Write this before any code, save it next to the Spring project (e.g. `docs/migration/<operation>.md`)
or wherever the user asks. Fill every section; write "none" rather than deleting one, so a reviewer
can see it was checked. Facts come from the bundle (`wm_inspect.py bundle`) and the config files —
cite the nsName or file for each. Mark anything you could not confirm from source as
**[VERIFY]** with what would settle it (a test call, a DB row, a question to the DB owner).

```markdown
# <METHOD> <public URL> — migration analysis

## 1. Summary
One paragraph: what the operation does for the caller, which backend it touches, how big the port is.

## 2. Source
| | |
|---|---|
| Package | `<api>-il/vN/src/<Package>` |
| REST entry service | `<ns>` |
| Call chain | api.pub → enterprise.pub → adapter.<sys>.pub → <adapter> (<template> @ <connection>) → <Java service / SQL> |
| Shared utils version | co.utils.v2 / v3 |
| Test package | `<Package>_TEST` — N cases for this operation / none |

## 3. Contract
- Request: path/query/header params (type, required as enforced), body.
- Response: JSON shape **as produced at runtime** (absent vs null, string vs number), example.
- Response headers.
- Status codes: success, each error code → status (from ERRORS_TO_HTTP_CODES; default 500).

## 4. Behaviour
Numbered steps in plain language, one per meaningful flow step. Include every branch and what
triggers it, conversions (types, date patterns), defaults, loops, and what is dropped from the response.

## 5. Backend calls
Per call: procedure/SQL text, connection alias, parameters in order with types and NULL rules,
OUT params / Oracle types and how attributes map to fields, timeout, retry rules, error output.

## 6. Errors
| Source system | Source code | Condition | App error code | HTTP | Description |
Fallbacks (ESB|0, E_UNKNOWN_0). Unexpected exceptions (what IS returns today).

## 7. Config
| wM key / global variable | Purpose | Spring property | Secret? |

## 8. Spring design
Classes to create (controller, service, port, adapter, records, error enum, config), and which
existing IL infrastructure (interceptor, error handler, retry, logging — `il-blueprint.md` §2) is reused or copied.

## 9. Behaviour changes and decisions
Each item from spring-mapping.md §6 that applies, with the decision taken (keep / change + who agreed).

## 10. Tests
List of test cases (from section 4/6 and the WmTestSuite), and the contract/fixture sources.

## 11. Open questions
Everything marked [VERIFY] above, as questions with an owner.
```
