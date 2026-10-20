#!/usr/bin/env python3
"""Structural health checks for the wiki. Stdlib only. Semantic checks are the LLM's job.

  python .claude/skills/wiki/scripts/lint.py               # full report (Markdown)
  python .claude/skills/wiki/scripts/lint.py --uningested  # just raw files that have no source page yet
  python .claude/skills/wiki/scripts/lint.py --json        # machine-readable
"""
import argparse, json, re, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
WIKI, RAW = ROOT / "wiki", ROOT / "raw"
SPECIAL = {"index", "log"}
REQUIRED = ("type", "title", "updated")
LINK = re.compile(r"!?\[\[([^\]|#^]+)(?:[#^][^\]|]*)?(?:\|[^\]]*)?\]\]")
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.S)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    return {k: v.strip() for k, v in re.findall(r"^([\w-]+):\s*(.*)$", m.group(1), re.M)}


def files(base, exts=None):
    return [p for p in base.rglob("*") if p.is_file() and not p.name.startswith(".")
            and (exts is None or p.suffix.lower() in exts)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uningested", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    all_files = [p for p in files(ROOT) if ".obsidian" not in p.parts and ".claude" not in p.parts]
    by_stem, by_path = defaultdict(list), {}
    for p in all_files:
        rel = p.relative_to(ROOT).as_posix()
        by_path[rel.lower()] = by_path[rel.lower().rsplit(".md", 1)[0]] = rel
        by_stem[(p.stem if p.suffix == ".md" else p.name).lower()].append(rel)

    def resolve(target):
        t = target.strip().lower()
        return by_path.get(t) or by_path.get(t + ".md") or (by_stem.get(t) or by_stem.get(t.rsplit("/", 1)[-1]) or [None])[0]

    md = [p for p in all_files if p.suffix == ".md" and "templates" not in p.relative_to(ROOT).parts]
    wiki_pages = [p for p in md if WIKI in p.parents]
    inbound, broken, missing_fm, no_sources = defaultdict(set), [], [], []
    for p in md:
        rel = p.relative_to(ROOT).as_posix()
        text = p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        for tgt in LINK.findall(CODE.sub("", text)):
            r = resolve(tgt)
            if r:
                inbound[r].add(rel)
            elif RAW not in p.parents:
                broken.append((rel, tgt))
        if p in wiki_pages and p.stem not in SPECIAL:
            fm = frontmatter(text)
            miss = [k for k in REQUIRED if not (fm or {}).get(k)]
            if miss:
                missing_fm.append((rel, miss))
            if fm and fm.get("type") in ("concept", "entity") and fm.get("sources", "[]") in ("", "[]"):
                no_sources.append(rel)

    raw_files = [p.relative_to(ROOT).as_posix() for p in files(RAW) if "assets" not in p.relative_to(RAW).parts]
    source_pages = {p.relative_to(ROOT).as_posix() for p in (WIKI / "sources").rglob("*.md")}
    uningested = sorted(r for r in raw_files if not (inbound.get(r, set()) & source_pages))
    if a.uningested:
        print("\n".join(uningested) or "nothing to ingest")
        return

    index = "wiki/index.md"
    content = [p.relative_to(ROOT).as_posix() for p in wiki_pages if p.stem not in SPECIAL]
    not_in_index = sorted(r for r in content if index not in inbound.get(r, set()))
    orphans = sorted(r for r in content if not (inbound.get(r, set()) - {index, "wiki/log.md"}))
    dupes = {k: v for k, v in by_stem.items() if len(v) > 1 and not k.startswith(".")}
    stubs = sorted(p.relative_to(ROOT).as_posix() for p in wiki_pages
                   if (frontmatter(p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")) or {}).get("status") == "stub")

    report = {"broken_links": broken, "missing_frontmatter": missing_fm, "not_in_index": not_in_index,
              "orphans": orphans, "duplicate_names": dupes, "uningested_raw": uningested,
              "concepts_without_sources": no_sources, "stubs": stubs}
    if a.json:
        print(json.dumps(report, indent=1, ensure_ascii=False))
        return
    print(f"# Wiki lint — {len(wiki_pages)} wiki pages, {len(raw_files)} raw files\n")
    for name, items in report.items():
        print(f"## {name.replace('_', ' ').capitalize()} ({len(items)})")
        rows = items.items() if isinstance(items, dict) else items
        for it in rows:
            print(f"- {it[0]} → {it[1]}" if isinstance(it, tuple) else f"- {it}")
        print()


if __name__ == "__main__":
    main()
