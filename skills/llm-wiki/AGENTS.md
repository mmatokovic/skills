# LLM Wiki — operating manual

This vault is a personal knowledge base in the style of Karpathy's "LLM Knowledge Bases":
raw sources go in, an LLM **compiles** them into an interlinked Markdown wiki, and every
question asked against the wiki can be filed back so the knowledge base compounds.

**You (the LLM) own `wiki/` and `outputs/`. The human owns `raw/`.** The human rarely edits
the wiki by hand; keep it correct, linked and tidy so they never have to.

Read this file fully before any operation. Language of the wiki: **English** (translate
Croatian or other sources; keep original product/legal terms in parentheses where useful).

---

## 1. Layout

```
raw/                  immutable sources — NEVER edit, rename or delete anything here
  articles/           web clips (Obsidian Web Clipper → .md)
  papers/             PDFs, papers, slide decks
  repos/              READMEs, code excerpts, repo snapshots
  notes/              the human's own notes, meeting notes, ideas (treat as sources)
  data/               CSV / JSON / datasets
  assets/             images (Obsidian attachment folder)
wiki/                 compiled knowledge — LLM-owned
  index.md            master catalog: every wiki page, one line each
  log.md              append-only operation log
  overview.base       Obsidian Bases table over the wiki (don't edit unless asked)
  topics/             hub pages (maps of content), one per research area
  concepts/           ideas, patterns, mechanisms, techniques
  entities/           concrete things: tools, products, orgs, people, projects, standards
  sources/            exactly one summary page per raw file
outputs/              answers to questions, Marp slides, charts, lint reports
  slides/  charts/  lint/
templates/            page skeletons — the schema for each page type
                      (missing? copy them from the skill's assets/templates/)
```

## 2. Conventions

- **File names**: lowercase kebab-case, unique across the whole vault (`argo-cd.md`,
  `app-of-apps-pattern.md`). The human-readable name goes in `title` and `aliases`.
- **Links**: Obsidian wikilinks with display text: `[[argo-cd|Argo CD]]`. Link the first
  mention of every concept/entity on a page. Never use Markdown `[]()` links for vault files.
- **Frontmatter**: every wiki page starts with YAML frontmatter following its template in
  `templates/`. Required on all: `type`, `title`, `updated` (ISO date). Keep `updated` current.
- **Citations**: every non-trivial claim on a concept/entity/topic page cites the source page
  it came from, inline: `… uses a pull model ([[src-argocd-docs-overview|Argo CD docs]]).`
  Cite `wiki/sources/` pages, not raw files directly.
- **Conflicts**: when sources disagree, keep both and flag it:
  `> [!warning] Conflict` callout naming both sources. Never silently overwrite.
- **Unverified / imputed** data (from web search or your own inference): mark with
  `> [!question] Unverified` and say where it came from.
- **Images**: embed with `![[raw/assets/file.png]]`. Look at images when ingesting.
- **Diagrams**: Mermaid code blocks. **Charts**: matplotlib PNG saved to `outputs/charts/`.
- **Status** of concept/entity/topic pages: `stub` (a few lines) → `draft` → `solid`
  (multiple sources, cross-checked).
- Prefer **updating an existing page** over creating a near-duplicate. Search first
  (`<skill-dir>/scripts/search.py`, `wiki/index.md`, aliases).
- Page granularity: one concept per page; split a page once it exceeds ~1,500 words.

## 3. Workflows

### 3.1 Ingest — "ingest", `/ingest`

Ingest is **supervised**: the human runs it. Before writing pages, give the key takeaways of each
source and ask what to emphasize. The weekly scheduled run never ingests; it only reports how many
raw files are waiting. Batch ingest only when the human explicitly asks for it.

1. Find work: `python <skill-dir>/scripts/lint.py --uningested` lists raw files no source page links to.
   If the human named specific files, do just those.
2. For each raw file (one at a time, fully — including images and PDFs):
   1. Create `wiki/sources/src-<slug>.md` from `templates/source.md`. Its `raw:` field links
      the raw file (`"[[raw/articles/foo.md]]"`). This link is what marks a file as ingested.
   2. Extract the concepts and entities it covers. For each: update the existing page
      (add facts + citation, raise `status`, bump `updated`) or create one from the template.
   3. Add the source and any new pages to the relevant `wiki/topics/` hub(s). Create a new
      hub only when ≥3 pages share a theme no hub covers.
   4. Add new pages to `wiki/index.md` (one line each, correct section).
3. Append one log entry per source to `wiki/log.md` (format in §4).
4. Report back briefly: pages created / updated, conflicts found, open questions raised.

### 3.2 Ask — "ask …", `/ask`

1. Navigate: `wiki/index.md` → relevant topic hubs → pages. Use
   `python <skill-dir>/scripts/search.py "<query>"` (add `--raw` to include raw sources) for anything the
   index doesn't surface. Go back to `raw/` only when the wiki lacks detail.
2. Write the answer to a file, not just the chat:
   - default: `outputs/YYYY-MM-DD-<slug>.md` from `templates/output.md`
   - slides when asked or when it's a walkthrough: `outputs/slides/<slug>.md` in Marp format
     (`marp: true` frontmatter, slides separated by `---`)
   - charts: matplotlib script output to `outputs/charts/<slug>.png`, embedded in the answer
   Cite wiki pages throughout. Give a short summary in chat with the file name.
3. **File it back**: if the answer produced new synthesis (a comparison, a decision, a
   connection between concepts), fold it into the relevant concept/topic pages with a
   citation to the output, and set `filed: true` on the output. Log it.

### 3.3 Lint — "lint", "health check", `/lint`

1. Run `python <skill-dir>/scripts/lint.py` and fix every structural issue it reports (broken links,
   missing frontmatter, pages missing from the index, orphans, duplicate names).
2. Then a semantic pass over the wiki:
   - contradictions between pages; claims not backed by a citation
   - stale facts (versions, dates) — check with web search, mark updates `[!question]` if unsure
   - gaps: missing data you can impute (web search, cite the URL as `Unverified`)
   - **concept candidates**: terms mentioned on ≥3 pages without their own page
   - interesting connections between topics → candidate articles
   - 3–5 suggested next questions or sources to clip
   - **near-duplicates**: pages that cover the same idea under different names — merge them
     (§5 redirect) when clearly the same concept, otherwise list them for the human. In the
     unattended weekly run, never merge: only list them for the human.
   - **summaries**: rewrite each topic hub's "Current understanding" from scratch against its
     current pages, instead of appending to it
3. Write the report to `outputs/lint/YYYY-MM-DD.md`, apply the safe fixes, list what needs
   the human's decision, and log it.

### 3.4 File — "file this", `/file`

Take a chat answer, an output file or a pasted snippet and integrate it into the wiki as in
§3.2 step 3. Never write to `raw/` — if something is genuinely new source material, tell the
human so they can add it. Lessons from work in other projects arrive as the human's own notes in
`raw/notes/` and go through §3.1 Ingest like any other source.

**Rule candidates**: when a note or answer contains a rule for how Claude should work (a
preference, a "never/always", a convention), don't only put it on a wiki page — a rule that lives
only in the wiki won't be followed in later sessions. List it in the report as a rule candidate with
the file it belongs in (`~/.claude/CLAUDE.md`, a project `CLAUDE.md`, or memory). The human approves
before it is added there.

## 4. Index and log formats

`wiki/index.md` — sections `## Topics`, `## Concepts`, `## Entities`, `## Sources`,
`## Outputs`; each line: `- [[slug|Title]] — one-sentence summary`. Keep alphabetical within
sections. This is your primary navigation aid; keep it complete and accurate.

`wiki/log.md` — append only, newest at the bottom, one heading per operation so it greps. Never edit
earlier entries, even when a page they link to is merged or deleted (`lint.py` ignores links in the log):

```
## [2026-10-19] ingest | Argo CD — Cluster bootstrapping
- created: [[src-argocd-cluster-bootstrapping]], [[app-of-apps-pattern]]
- updated: [[argo-cd]] (draft → solid), [[openshift-gitops]]
- conflicts: none
```

Operation types: `init`, `ingest`, `ask`, `file`, `lint`, `refactor`.

## 5. Rules

- Never modify `raw/`. Never delete wiki pages — merge them and leave a redirect line
  (`Merged into [[other-page]].`) with `status: merged`, then fix inbound links.
- Don't invent facts. Everything in the wiki traces back to a source page, an output, or a
  clearly marked `Unverified` search result.
- If the human edited a wiki page by hand, treat their edit as authoritative.
- Keep the chat reply short; the work product lives in files.
- If the skill's `scripts/*.py` can't be run in your environment, do the equivalent by reading files
  (e.g. list `raw/` and grep `wiki/sources/` for `raw:` links to find uningested files).
