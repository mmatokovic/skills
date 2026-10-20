---
name: wiki
description: Search and structurally lint this LLM wiki vault (wiki/, raw/). Use when asked to find something in the wiki, check for broken links/orphans/missing index entries, or list raw files not yet ingested.
---
Operating rules live in the vault-root `CLAUDE.md`; this skill only bundles the helper scripts.
Run them from the vault root (stdlib-only Python 3).

- Search: `python .claude/skills/wiki/scripts/search.py "<query>" [--raw] [-n 20] [--json]`
  (`--serve` starts a local web UI on port 8765 whose results open in Obsidian)
- Lint: `python .claude/skills/wiki/scripts/lint.py [--uningested] [--json]`

`assets/web-clipper-template.json` is the Obsidian Web Clipper template (import it in the browser
extension; clips land in `raw/articles/`).
