---
name: llm-wiki
description: Maintain an LLM-compiled Obsidian wiki vault (raw/, wiki/, outputs/). Use to ingest raw sources, ask the wiki a question, search it, lint it (broken links, orphans, missing index entries, uningested files), or file an answer back into it.
---
Operating rules (layout, conventions, ingest / ask / lint / file workflows) are in this skill's
[AGENTS.md](AGENTS.md); read it before any operation. A vault can import it from its `CLAUDE.md`
with `@AGENTS.md` after copying it to the vault root.


Scripts are stdlib-only Python 3 in this skill's `scripts/` folder. Run them from the vault root:

- Search: `python <skill-dir>/scripts/search.py "<query>" [--raw] [-n 20] [--json]`
  (`--serve` starts a local web UI on port 8765 whose results open in Obsidian)
- Lint: `python <skill-dir>/scripts/lint.py [--uningested] [--json]`

`assets/web-clipper-template.json` is the Obsidian Web Clipper template (import it in the browser
extension; clips land in `raw/articles/`).
