#!/usr/bin/env python3
"""Naive BM25 search over the wiki (and optionally raw sources). Stdlib only.

  python scripts/search.py "argo cd rbac"            # top 10 wiki hits
  python scripts/search.py "app of apps" --raw -n 20 # include raw/ sources
  python scripts/search.py "image updater" --json    # machine-readable, for the LLM
  python scripts/search.py --serve                   # web UI on http://localhost:8765
"""
import argparse, html, json, math, re, sys, urllib.parse
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path.cwd()
TEXT_EXT = {".md", ".txt", ".csv", ".json"}
TOKEN = re.compile(r"[\w\-]+", re.UNICODE)
K1, B, TITLE_BOOST = 1.5, 0.75, 3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def tokens(text):
    out = []
    for t in TOKEN.findall(text.lower()):
        out.append(t)
        if "-" in t:
            out += [p for p in t.split("-") if p]
    return out


def title_of(path, text):
    m = re.search(r'^title:\s*"?(.+?)"?\s*$', text[:2000], re.M)
    if m:
        return m.group(1)
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else path.stem


def load_docs(include_raw):
    dirs = ["wiki", "outputs"] + (["raw"] if include_raw else [])
    docs = []
    for d in dirs:
        for p in sorted((ROOT / d).rglob("*")):
            if p.suffix.lower() not in TEXT_EXT or not p.is_file():
                continue
            text = p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
            title = title_of(p, text)
            toks = tokens(text) + tokens(f"{title} {p.stem}") * TITLE_BOOST
            docs.append({"path": p.relative_to(ROOT).as_posix(), "title": title,
                         "text": text, "tf": Counter(toks), "len": len(toks)})
    return docs


def search(query, docs, n):
    q = tokens(query)
    if not q or not docs:
        return []
    avg = sum(d["len"] for d in docs) / len(docs)
    df = Counter(t for d in docs for t in set(q) if t in d["tf"])
    scored = []
    for d in docs:
        s = 0.0
        for t in q:
            f = d["tf"].get(t, 0)
            if not f:
                continue
            idf = math.log(1 + (len(docs) - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * d["len"] / avg))
        if s > 0:
            scored.append((s, d))
    scored.sort(key=lambda x: -x[0])
    return [{"score": round(s, 2), "path": d["path"], "title": d["title"],
             "snippet": snippet(d["text"], set(q))} for s, d in scored[:n]]


def snippet(text, q, width=220):
    body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    if not lines:
        return ""
    best = max(lines, key=lambda l: sum(t in q for t in tokens(l)))
    return best[:width] + ("…" if len(best) > width else "")


def serve(include_raw, port):
    vault = urllib.parse.quote(ROOT.name)

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            q = qs.get("q", [""])[0]
            hits = search(q, load_docs(include_raw), 30) if q else []
            rows = "".join(
                f'<li><a href="obsidian://open?vault={vault}&file={urllib.parse.quote(h["path"])}">'
                f'{html.escape(h["title"])}</a> <small>{h["path"]} · {h["score"]}</small>'
                f'<p>{html.escape(h["snippet"])}</p></li>' for h in hits)
            page = f"""<!doctype html><meta charset=utf-8><title>Wiki search</title>
<style>body{{font:15px system-ui;max-width:760px;margin:2rem auto;padding:0 1rem}}
input{{width:100%;font-size:1.1rem;padding:.5rem}}li{{margin:1rem 0}}small{{color:#888}}p{{margin:.2rem 0;color:#444}}</style>
<form><input name=q value="{html.escape(q)}" autofocus placeholder="Search the wiki…"></form><ol>{rows}</ol>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.encode())

        def log_message(self, *a):
            pass

    print(f"Wiki search on http://localhost:{port}  (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", port), H).serve_forever()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="*")
    ap.add_argument("-n", type=int, default=10, help="number of results")
    ap.add_argument("--raw", action="store_true", help="also search raw/ sources")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--serve", action="store_true", help="start the web UI")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    if a.serve:
        return serve(a.raw, a.port)
    if not a.query:
        ap.error("query required (or --serve)")
    hits = search(" ".join(a.query), load_docs(a.raw), a.n)
    if a.json:
        print(json.dumps(hits, ensure_ascii=False, indent=1))
        return
    for i, h in enumerate(hits, 1):
        print(f"{i:>2}. {h['title']}  [{h['path']}]  {h['score']}\n    {h['snippet']}")
    if not hits:
        print("no results")


if __name__ == "__main__":
    main()
