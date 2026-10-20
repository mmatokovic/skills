# Crosig shared service catalog (generated)

Signatures and bodies of the shared IL services and canonical doc types that almost every flow
calls, so the skill can read their real behaviour even without an `int-webmethods-project`
checkout (pasted XML, evals, a machine without the repo).

| File | Source package |
|---|---|
| `co.utils.v3.json` | `utils-il/v3/src/COUtilsV003` |
| `co.utils.v2.json` | `utils-il/v2/src/COUtilsV2` |
| `co.utils.json` | `utils-il/v1/src/COUtils` (v1, excluding v2/v3) |
| `co.cdm.v2.technical.json`, `co.cdm.v3.technical.json` | `canonical-data-models-il` (`docEnvelope`, `docResult`, ...) |

Each service entry: `name`, `kind`, `package`, `description` (node comment), `input_parameters`,
`output_parameters` (with `required` and nested `fields`), and by kind: `invokes` + `flow`
(the same pseudo-code `wm_inspect.py show` prints), `adapter` (template, connection, SQL), or
`java_source` (path inside the package). `document_types` holds the doc types under the prefix.

Look a service up with `grep -n '"name": "co.utils.v3.runtime.pub:errorService"' co.utils.v3.json`
and read the entry, or with the checkout run `wm_inspect.py show <nsName>` (also prints Java bodies).

## Regenerate — do not edit by hand

After a change in `utils-il` or `canonical-data-models-il`, from the skill directory:

```bash
R=<path to int-webmethods-project>
python scripts/wm_inspect.py --root $R/utils-il --root $R/canonical-data-models-il catalog \
  --prefix co.utils.v3. --prefix co.utils.v2. --prefix co.utils. \
  --prefix co.cdm.v2.technical: --prefix co.cdm.v3.technical: \
  -o assets/custom-service-catalog
```

Add another shared package the same way (`--root` to its repo, `--prefix` for its namespace).
Before committing, check the diff for credentials — the generator copies flow literals verbatim,
and a flow that hard-codes a password would put it here.
