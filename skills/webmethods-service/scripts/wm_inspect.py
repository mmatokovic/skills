#!/usr/bin/env python3
"""Read webMethods Integration Server package source and print it in a form a person
(or Claude) can migrate from: signatures, flow.xml as pseudo-code, decoded JDBC adapter
services, Java service bodies, REST descriptors and the call tree of a service.

Read-only. Standard library only (Python 3.9+).

Usage (ROOT = a folder that contains IS packages, e.g. the int-webmethods-project checkout):
  wm_inspect.py --root ROOT find   <text>             # services/doc types whose nsName contains text
  wm_inspect.py --root ROOT rest   [text]             # REST operations: METHOD url -> entry service
  wm_inspect.py --root ROOT show   <nsName|dir>       # one node: signature + body (flow/java/adapter/doc)
  wm_inspect.py --root ROOT trace  <nsName|dir> [--depth N] [--utils]   # call tree
  wm_inspect.py --root ROOT bundle <nsName|dir> [--depth N] [--utils] [-o FILE]
                                                      # show every service in the call tree, one doc
  wm_inspect.py --root ROOT doc    <nsName>           # document type as a field tree
Options: --types  keep ;type;dim markers in field paths; --all-packages  include *_TEST packages.
"""
from __future__ import annotations

import argparse
import base64
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# ----------------------------------------------------------------------------- Values XML


def values_to_py(elem):
    """Convert a webMethods <Values>/<record>/<array> element into dict/list/scalars."""
    tag = elem.tag
    if tag in ("Values", "record"):
        out = {}
        for child in elem:
            out[child.get("name")] = values_to_py(child)
        return out
    if tag == "array":
        return [values_to_py(c) for c in elem]
    if tag == "null":
        return None
    if tag == "Boolean":
        return (elem.text or "").strip().lower() == "true"
    return elem.text if elem.text is not None else ""


def read_values(path: Path):
    try:
        return values_to_py(ET.parse(path).getroot())
    except (ET.ParseError, OSError) as exc:
        return {"_error": f"{path}: {exc}"}


# ----------------------------------------------------------------------------- index


class Index:
    """Maps nsName -> node folder for every package under the roots."""

    def __init__(self, roots, include_tests=False):
        self.nodes: dict[str, list[Path]] = {}
        self.packages: list[Path] = []
        self.node_pkg: dict[Path, Path] = {}
        # Designer generates a sibling '<name>_' folder for every REST/SOAP descriptor.
        self.descriptor_dirs: list[Path] = []
        for root in roots:
            for dirpath, dirnames, filenames in os.walk(root):
                # skip noise
                dirnames[:] = [d for d in dirnames if d not in (".git", "bin", "node_modules", "target")]
                if "manifest.v3" in filenames and "ns" in dirnames:
                    pkg = Path(dirpath)
                    if not include_tests and pkg.name.endswith("_TEST"):
                        dirnames[:] = []
                        continue
                    self.packages.append(pkg)
                    self._index_package(pkg)
                    dirnames[:] = []

    def _index_package(self, pkg: Path):
        ns_root = pkg / "ns"
        for dirpath, dirnames, filenames in os.walk(ns_root):
            self.descriptor_dirs += [Path(dirpath) / d for d in dirnames
                                     if d + "_" in dirnames or Path(dirpath).name == "restProviders"]
            if "node.ndf" in filenames:
                rel = Path(dirpath).relative_to(ns_root).parts
                if not rel:
                    continue
                ns = ".".join(rel[:-1]) + ":" + rel[-1] if len(rel) > 1 else rel[0]
                self.nodes.setdefault(ns, []).append(Path(dirpath))
                self.node_pkg[Path(dirpath)] = pkg

    def resolve(self, target: str) -> Path | None:
        p = Path(target)
        if p.is_dir() and (p / "node.ndf").exists():
            return p
        hits = self.nodes.get(target)
        if hits:
            if len(hits) > 1:
                print(f"# note: {target} exists in {len(hits)} places, using {hits[0]}", file=sys.stderr)
                for h in hits[1:]:
                    print(f"#   also: {h}", file=sys.stderr)
            return hits[0]
        return None


def package_of(node_dir: Path) -> Path:
    for parent in node_dir.parents:
        if (parent / "manifest.v3").exists():
            return parent
    return node_dir


# ----------------------------------------------------------------------------- signatures

PATH_SEG = re.compile(r"^([^;]*);([\d.]+);(\d+)(?:;(.*))?$")
TYPE_CODES = {
    "1": "String", "2": "Document", "3": "Object", "3.1": "Boolean", "3.2": "Byte",
    "3.3": "Character", "3.4": "Double", "3.5": "Float", "3.6": "Integer", "3.7": "Long",
    "3.8": "Short", "3.9": "Date", "3.10": "byte[]", "3.11": "BigDecimal", "3.12": "BigInteger",
    "4": "DocRef",
}


def clean_path(path: str, keep_types=False) -> str:
    """'/a;2;0/b;4;1;x.y:Doc/c;1;0' -> 'a/b[]/c' (field names are what IS resolves at runtime)."""
    if not path:
        return path
    if keep_types:
        return path.lstrip("/")
    out = []
    for seg in path.strip("/").split("/"):
        m = PATH_SEG.match(seg)
        if m:
            name, _t, dim, _ref = m.groups()
            # 'name(1)' marks a second declaration of the same field (object vs document); IS
            # resolves by name, so drop the suffix.
            out.append(re.sub(r"\(\d+\)$", "", name) + ("[]" * int(dim)))
        else:
            out.append(seg)
    return "/".join(out)


def field_type(f: dict) -> str:
    ft = f.get("field_type")
    dim = int(f.get("field_dim") or 0)
    if ft == "string":
        base = "String"
    elif ft == "recref":
        base = f"Doc<{f.get('rec_ref')}>"
    elif ft == "record":
        base = "Doc"
    elif ft == "object":
        wt = f.get("wrapper_type") or "Object"
        base = wt.split(".")[-1] if wt != "IData" else "Doc"
    else:
        base = ft or "?"
    return base + "[]" * dim


def render_fields(fields, indent=0, out=None, depth=0):
    out = [] if out is None else out
    for f in fields or []:
        if not isinstance(f, dict):
            continue
        opt = "" if f.get("field_opt") in (True, "true") else "  (required)"
        name = f.get("field_name")
        out.append("  " * indent + f"- {name}: {field_type(f)}{opt}")
        if f.get("field_type") == "record" and depth < 12:
            render_fields(f.get("rec_fields"), indent + 1, out, depth + 1)
    return out


def render_signature(ndf: dict) -> list[str]:
    sig = ndf.get("svc_sig") or {}
    lines = ["input:"]
    lines += render_fields((sig.get("sig_in") or {}).get("rec_fields")) or ["  (none)"]
    lines.append("output:")
    lines += render_fields((sig.get("sig_out") or {}).get("rec_fields")) or ["  (none)"]
    return lines


# ----------------------------------------------------------------------------- flow.xml


def data_value(mapset) -> str:
    data = mapset.find("DATA")
    if data is None:
        return "?"
    values = data.find("Values")
    if values is None:
        return (data.text or "").strip()
    for child in values:
        if child.get("name") == "xml":
            v = values_to_py(child)
            if isinstance(v, str):
                return '"' + v.replace("\n", "\\n") + '"'
            return repr(v)
    return "null"


class FlowRenderer:
    def __init__(self, keep_types=False):
        self.keep_types = keep_types
        self.invoked: list[str] = []
        self.lines: list[str] = []

    def p(self, path):
        return clean_path(path, self.keep_types)

    def emit(self, depth, text):
        self.lines.append("  " * depth + text)

    def render(self, root):
        for child in root:
            self.step(child, 0)
        return self.lines

    @staticmethod
    def comment(el):
        c = el.find("COMMENT")
        return (c.text or "").strip() if c is not None and c.text else ""

    def head(self, el, text):
        label = el.get("NAME")
        bits = []
        if label is not None:
            bits.append(f"[{label}]")
        bits.append(text)
        if el.get("DISABLED") == "true":
            bits.append("(DISABLED - skip)")
        if el.get("TIMEOUT"):
            bits.append(f"timeout={el.get('TIMEOUT')}s")
        cm = self.comment(el)
        if cm:
            bits.append(f"// {cm}")
        return " ".join(bits)

    def step(self, el, d):
        tag = el.tag
        if tag in ("COMMENT", "MAPTARGET", "MAPSOURCE"):
            return
        if tag == "SEQUENCE":
            form = el.get("FORM")
            kind = form if form in ("TRY", "CATCH", "FINALLY") else f"SEQUENCE exit-on={el.get('EXIT-ON')}"
            self.emit(d, self.head(el, kind))
        elif tag == "INVOKE":
            svc = el.get("SERVICE")
            self.invoked.append(svc)
            self.emit(d, self.head(el, f"INVOKE {svc}"))
        elif tag == "MAP":
            mode = el.get("MODE")
            if mode == "STANDALONE":
                self.emit(d, self.head(el, "MAP"))
            else:
                label = {"INPUT": "in:", "OUTPUT": "out:", "INVOKEINPUT": "in:", "INVOKEOUTPUT": "out:"}.get(mode, mode)
                if not any(c.tag in ("MAPCOPY", "MAPSET", "MAPDELETE", "MAPINVOKE") for c in el):
                    return
                self.emit(d, label)
        elif tag == "MAPINVOKE":
            svc = el.get("SERVICE")
            self.invoked.append(svc)
            self.emit(d, self.head(el, f"transformer {svc}"))
        elif tag == "MAPCOPY":
            self.emit(d, f"{self.p(el.get('TO'))} = {self.p(el.get('FROM'))}" + (" (DISABLED)" if el.get("DISABLED") == "true" else ""))
            return
        elif tag == "MAPSET":
            flags = []
            if el.get("VARIABLES") == "true":
                flags.append("%subst%")
            if el.get("GLOBALVARIABLES") == "true":
                flags.append("global-vars")
            if el.get("OVERWRITE") == "false":
                flags.append("only-if-null")
            fl = f"  [{', '.join(flags)}]" if flags else ""
            self.emit(d, f"{self.p(el.get('FIELD'))} := {data_value(el)}{fl}")
            return
        elif tag == "MAPDELETE":
            self.emit(d, f"drop {self.p(el.get('FIELD'))}")
            return
        elif tag == "BRANCH":
            if el.get("LABELEXPRESSIONS") == "true":
                self.emit(d, self.head(el, "BRANCH on expressions (first true child wins)"))
            else:
                self.emit(d, self.head(el, f"BRANCH switch {el.get('SWITCH')}"))
        elif tag == "LOOP":
            out = f" collect-into {el.get('OUT-ARRAY')}" if el.get("OUT-ARRAY") else ""
            self.emit(d, self.head(el, f"LOOP over {el.get('IN-ARRAY')}{out}"))
        elif tag == "RETRY":
            self.emit(d, self.head(el, f"REPEAT count={el.get('COUNT')} repeat-on={el.get('LOOP-ON')} back-off={el.get('BACK-OFF') or 0}s"))
        elif tag == "MAPFOREACH":
            self.emit(d, self.head(el, f"FOREACH {el.get('IN-ARRAY')} -> {el.get('OUT-ARRAY')} mode={el.get('COPYMODE')}"))
        elif tag == "EXIT":
            msg = el.get("FAILURE-MESSAGE")
            msg = f' message="{msg}"' if msg else ""
            self.emit(d, self.head(el, f"EXIT from={el.get('FROM')} signal={el.get('SIGNAL')}{msg}"))
            return
        elif tag == "DATA":
            return
        else:
            self.emit(d, f"<{tag} {dict(el.attrib)}>")
        for child in el:
            self.step(child, d + 1)


def render_flow(flow_xml: Path, keep_types=False):
    try:
        root = ET.parse(flow_xml).getroot()
    except ET.ParseError as exc:
        return [f"(cannot parse {flow_xml}: {exc})"], []
    r = FlowRenderer(keep_types)
    lines = r.render(root)
    return lines, r.invoked


# ----------------------------------------------------------------------------- adapter blobs


def decode_irt(blob_b64: str) -> list[str]:
    """Best-effort decode of IRTNODE_PROPERTY (binary IData): returns the string tokens in order.

    Strings are tag 0x04 + 1-byte length or 0x84 + 4-byte length, followed by UTF-16BE chars.
    Repeated values are stored as back-references and are NOT recovered: a list can come out
    shorter than its siblings (e.g. colTypes 'IN' with no 'OUT'). Cross-check with node.ndf.
    """
    b = base64.b64decode(blob_b64)
    out, i = [], 0
    while i < len(b):
        t = b[i]
        if t in (0x04, 0x84):
            ln = 1 if t == 0x04 else 4
            n = int.from_bytes(b[i + 1:i + 1 + ln], "big")
            s = b[i + 1 + ln:i + 1 + ln + 2 * n]
            if n > 0 and len(s) == 2 * n:
                try:
                    out.append(s.decode("utf-16-be"))
                    i += 1 + ln + 2 * n
                    continue
                except UnicodeDecodeError:
                    pass
        i += 1
    return out


def after(toks, key):
    """Value token that follows a key token, or None."""
    return toks[toks.index(key) + 1] if key in toks[:-1] else None


SECRET_KEYS = re.compile(r"password|passwd|pwd|secret", re.I)


def render_adapter(ndf_text: str) -> list[str]:
    m = re.search(r'name="IRTNODE_PROPERTY">([^<]+)<', ndf_text)
    if not m:
        return ["(no IRTNODE_PROPERTY)"]
    toks = decode_irt(m.group(1))
    lines, prev = [], ""
    for t in toks:
        if t == "com.wm.data.ISMemDataImpl":
            continue
        # A connection node stores the real password right after its key; an adapter service
        # stores a pipeline reference there (overrideCredentials.$dbPassword), which is harmless.
        if SECRET_KEYS.fullmatch(prev) and not t.startswith("overrideCredentials"):
            lines.append("    ******** (secret value hidden)")
            prev = t
            continue
        prev = t
        if "\n" in t:
            lines.append("  ---")
            lines += ["    " + ln for ln in t.splitlines()]
            lines.append("  ---")
        else:
            lines.append(f"  {t}")
    summary = []
    tmpl = next((t for t in toks if t.startswith("com.wm.adapter.wmjdbc.services.")), None)
    conn = after(toks, "connectionName")
    if tmpl:
        summary.append(f"template: {tmpl.rsplit('.', 1)[-1]}")
    if conn:
        summary.append(f"connection: {conn}")
    if "javaService" in toks:
        summary.append(f"executes Java service: {toks[toks.index('javaService') + 1]}")
    return summary + ["decoded properties (lossy - repeated values are dropped):"] + lines


# ----------------------------------------------------------------------------- java


def java_body(node_dir: Path, ns: str) -> list[str]:
    pkg = package_of(node_dir)
    folder, _, name = ns.partition(":")
    src = pkg / "code" / "source" / (folder.replace(".", "/") + ".java")
    if src.exists():
        text = src.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"// --- <<IS-START\(" + re.escape(name) + r"\)>> ---(.*?)// --- <<IS-END>> ---", text, re.S)
        lines = [f"source: {src}"]
        if m:
            lines += m.group(1).strip("\n").splitlines()
        else:
            lines.append("(method markers not found - read the file)")
        if "<<IS-START-SHARED>>" in text:
            lines.append(f"(the class also has shared helpers between IS-START-SHARED/IS-END-SHARED in {src.name})")
        return lines
    frag = node_dir / "java.frag"
    if frag.exists():
        data = read_values(frag)
        body = data.get("body") or ""
        try:
            return ["source: java.frag (base64 body, no code/source file found)"] + base64.b64decode(body).decode("utf-8", "replace").splitlines()
        except ValueError:
            return ["(java.frag body not decodable)"]
    return ["(no Java source found)"]


# ----------------------------------------------------------------------------- nodes


def node_kind(ndf: dict) -> str:
    if "_error" in ndf:
        return "error"
    if ndf.get("svc_type"):
        sub = ndf.get("svc_subtype")
        return ndf["svc_type"] + (f"/{sub}" if sub and sub not in ("default", "unknown") else "")
    if ndf.get("node_type"):
        return ndf["node_type"] + (f"/{ndf.get('node_subtype')}" if ndf.get("node_subtype") else "")
    if isinstance(ndf.get("record"), dict):
        return "document"
    return "?"


def show_node(index: Index, target: str, keep_types=False, header_level="##") -> tuple[list[str], list[str]]:
    node_dir = index.resolve(target)
    if node_dir is None:
        return [f"{header_level} {target}", "(not found under --root; built-in pub.* or a package that is not checked out)"], []
    ndf_path = node_dir / "node.ndf"
    ndf_text = ndf_path.read_text(encoding="utf-8", errors="replace")
    ndf = read_values(ndf_path)
    ns = target if ":" in target else (ndf.get("node_nsName") or (ndf.get("record") or {}).get("node_nsName") or target)
    kind = node_kind(ndf)
    lines = [f"{header_level} {ns}", f"kind: {kind}", f"folder: {node_dir}"]
    comment = ndf.get("node_comment")
    if comment:
        lines.append(f"comment: {comment.strip()}")
    invoked: list[str] = []
    if kind == "document":
        lines.append("fields:")
        lines += render_fields(ndf["record"].get("rec_fields"))
        return lines, invoked
    if "svc_sig" in ndf:
        lines += ["", "signature:"] + ["  " + ln for ln in render_signature(ndf)]
    if kind.startswith("flow") and (node_dir / "flow.xml").exists():
        body, invoked = render_flow(node_dir / "flow.xml", keep_types)
        lines += ["", "flow:", "```"] + body + ["```"]
    elif kind.startswith("java"):
        lines += ["", "java:", "```java"] + java_body(node_dir, ns) + ["```"]
    elif kind.startswith("AdapterService") or "IRTNODE_PROPERTY" in ndf_text:
        lines += ["", "adapter:"] + render_adapter(ndf_text)
        m = re.search(r'name="IRTNODE_PROPERTY">([^<]+)<', ndf_text)
        java_svc = after(decode_irt(m.group(1)), "javaService") if m else None
        if java_svc:
            invoked.append(java_svc)
    elif kind.startswith("restDescriptor"):
        ops = rad_operations(ndf) or resource_operations(index, ns, None)
        lines += ["", "operations:"] + ["  " + ln for ln in ops]
        spec = node_dir / "openapi"
        if spec.exists():
            lines.append(f"OpenAPI spec file: {spec}")
    elif kind.startswith("webMethods/trigger"):
        t = ndf.get("trigger") or {}
        lines.append(f"trigger: {t}")
    return lines, invoked


def rad_operations(ndf: dict) -> list[str]:
    out = []
    base = (ndf.get("generalInfo") or {}).get("basePath") or ""
    for path, res in (ndf.get("restResources") or {}).items():
        for method, op in ((res or {}).get("operations") or {}).items():
            op = op or {}
            params = []
            for pname, p in (op.get("parameters") or {}).items():
                p = p or {}
                req = "*" if p.get("isRequired") else ""
                params.append(f"{pname}{req}({(p.get('source') or '').lower()}:{(p.get('type') or '').lower()}{'[]' if p.get('isArray') else ''})")
            resp = ",".join((op.get("responses") or {}).keys())
            out.append(f"{method} {base}{path} -> {op.get('nsName')}")
            if params:
                out.append(f"    params: {' '.join(params)}   (* = required)")
            if resp:
                out.append(f"    responses: {resp}")
    return out


def resource_operations(index, rad_ns: str, alias: str | None) -> list[str]:
    """OpenAPI 3 providers keep no restResources in the RAD: read the generated restResource
    nodes (<folder>.<rad>_.resources:*) and point at the sibling `openapi` spec for params."""
    folder, _, name = rad_ns.partition(":")
    prefix = f"{folder}.{name}_.resources:"
    base = f"/{alias}" if alias else ""
    out = []
    for ns, dirs in sorted(index.nodes.items()):
        if not ns.startswith(prefix):
            continue
        res = read_values(dirs[0] / "node.ndf")
        for op in res.get("operations") or (res.get("restResource") or {}).get("operations") or []:
            for method in op.get("httpMethods") or []:
                out.append(f"{method} {base}{op.get('urlTemplate')} -> {op.get('serviceName')}")
    if out:
        spec = index.resolve(rad_ns)
        out.append(f"    params/responses: see {spec / 'openapi' if spec else 'the openapi file next to the RAD'}")
    return out


# ----------------------------------------------------------------------------- commands

SKIP_PREFIXES = ("pub.", "wm.", "co.utils.")


def is_leafish(ns: str, include_utils: bool) -> bool:
    if ns.startswith(("pub.", "wm.")):
        return True
    return not include_utils and ns.startswith("co.utils.")


def cmd_trace(index, target, depth, include_utils, collect=None):
    seen = set()
    lines = []

    def walk(ns, d, prefix):
        node_dir = index.resolve(ns)
        if node_dir is None:
            lines.append(f"{prefix}{ns}  [{'built-in' if ns.startswith(('pub.', 'wm.')) else 'not found'}]")
            return
        ndf = read_values(node_dir / "node.ndf")
        kind = node_kind(ndf)
        extra = ""
        ndf_text = (node_dir / "node.ndf").read_text(encoding="utf-8", errors="replace")
        if "IRTNODE_PROPERTY" in ndf_text and kind.startswith("AdapterService"):
            toks = decode_irt(re.search(r'IRTNODE_PROPERTY">([^<]+)<', ndf_text).group(1))
            tmpl = next((t.rsplit(".", 1)[-1] for t in toks if t.startswith("com.wm.adapter.wmjdbc.services.")), "?")
            conn = after(toks, "connectionName") or "?"
            extra = f" {tmpl} @ {conn}"
            if "javaService" in toks:
                child = toks[toks.index("javaService") + 1]
                lines.append(f"{prefix}{ns}  [{kind}{extra}]")
                if collect is not None:
                    collect.append(ns)
                if ns not in seen:
                    seen.add(ns)
                    walk(child, d + 1, prefix + "    ")
                return
        if ns in seen:
            lines.append(f"{prefix}{ns}  [{kind}] (see above)")
            return
        seen.add(ns)
        lines.append(f"{prefix}{ns}  [{kind}{extra}]")
        if collect is not None:
            collect.append(ns)
        if kind.startswith("flow") and (node_dir / "flow.xml").exists() and d < depth:
            _body, invoked = render_flow(node_dir / "flow.xml")
            done = []
            for svc in invoked:
                if svc in done:
                    continue
                done.append(svc)
                if is_leafish(svc, include_utils):
                    lines.append(f"{prefix}    {svc}")
                else:
                    walk(svc, d + 1, prefix + "    ")

    walk(target, 0, "")
    return lines


def cmd_rest(index, text):
    aliases = {}
    for pkg in index.packages:
        cnf = pkg / "config" / "urlalias.cnf"
        if cnf.exists():
            for alias, rec in (read_values(cnf) or {}).items():
                if isinstance(rec, dict) and (rec.get("urlPath") or "").startswith("rad/"):
                    aliases[rec["urlPath"][4:]] = alias
    rows = []
    for d in sorted(set(index.descriptor_dirs)):
        if not (d / "node.ndf").exists():
            continue
        ndf = read_values(d / "node.ndf")
        if ndf.get("node_type") != "restDescriptor" or ndf.get("node_subtype") == "consumerDescriptor":
            continue
        ns = ndf.get("node_nsName")
        alias = aliases.get(ns)
        for ln in rad_operations(ndf) or resource_operations(index, ns, alias):
            if " -> " in ln:
                ln += f"   (url alias /{alias}, RAD {ns})" if alias else f"   (RAD {ns}, served at /rad/{ns}/...)"
            rows.append(ln)
    if text:
        keep, last_hit = [], False
        for ln in rows:
            if " -> " in ln:
                last_hit = text.lower() in ln.lower()
            if last_hit:
                keep.append(ln)
        rows = keep
    return rows or ["(no REST provider operations found)"]


def sig_params(fields):
    out = []
    for f in fields or []:
        if not isinstance(f, dict):
            continue
        p = {"name": f.get("field_name"), "type": field_type(f),
             "required": f.get("field_opt") not in (True, "true")}
        if f.get("field_type") == "record" and f.get("rec_fields"):
            p["fields"] = sig_params(f.get("rec_fields"))
        out.append(p)
    return out


def cmd_catalog(index, prefixes, out_dir: Path):
    """One JSON file per prefix, in the shape of assets/wm-service-catalog, plus what each
    service calls and (for flows) its pseudo-code, so behaviour can be read without a checkout."""
    out_dir.mkdir(parents=True, exist_ok=True)
    import json
    for prefix in prefixes:
        services, docs = [], []
        # a longer prefix given in the same run owns its nodes (co.utils. vs co.utils.v3.)
        longer = [o for o in prefixes if o != prefix and o.startswith(prefix)]
        for ns in sorted(n for n in index.nodes if n.startswith(prefix) and not any(n.startswith(o) for o in longer)):
            node_dir = index.nodes[ns][0]
            ndf = read_values(node_dir / "node.ndf")
            kind = node_kind(ndf)
            pkg = index.node_pkg.get(node_dir, package_of(node_dir)).name
            if kind == "document":
                docs.append({"name": ns, "package": pkg,
                             "fields": sig_params(ndf["record"].get("rec_fields"))})
                continue
            if "svc_sig" not in ndf:
                continue
            sig = ndf.get("svc_sig") or {}
            entry = {
                "name": ns, "kind": kind, "package": pkg,
                "public": ".pub" in ns.split(":")[0].split(".")[-1:] or ".pub." in ns or ns.split(":")[0].endswith(".pub"),
                "description": [(ndf.get("node_comment") or "").strip()] if ndf.get("node_comment") else [],
                "input_parameters": sig_params((sig.get("sig_in") or {}).get("rec_fields")),
                "output_parameters": sig_params((sig.get("sig_out") or {}).get("rec_fields")),
            }
            if kind.startswith("flow") and (node_dir / "flow.xml").exists():
                body, invoked = render_flow(node_dir / "flow.xml")
                entry["invokes"] = sorted(set(invoked))
                entry["flow"] = body
            elif kind.startswith("AdapterService"):
                m = re.search(r'name="IRTNODE_PROPERTY">([^<]+)<', (node_dir / "node.ndf").read_text(encoding="utf-8", errors="replace"))
                toks = decode_irt(m.group(1)) if m else []
                entry["adapter"] = {"template": next((t.rsplit(".", 1)[-1] for t in toks if t.startswith("com.wm.adapter.wmjdbc.services.")), None),
                                    "connection": after(toks, "connectionName"),
                                    "sql": next((t for t in toks if "\n" in t or t.upper().startswith(("SELECT", "INSERT", "UPDATE", "DELETE"))), None)}
            elif kind.startswith("java"):
                entry["java_source"] = "code/source/" + ns.split(":")[0].replace(".", "/") + ".java"
            services.append(entry)
        name = re.sub(r"[^\w.-]", "", prefix).strip(".")
        data = {"folder": name, "generated_by": "wm_inspect.py catalog", "total_services": len(services),
                "services": services, "document_types": docs}
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {path} ({len(services)} services, {len(docs)} doc types, {path.stat().st_size // 1024} KB)")


def read_props(path: Path) -> list[tuple[str, str]]:
    """key=value lines (split at the first '='; keys contain ':' and '|', so not java.util.Properties)."""
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "!")) and "=" in line:
            k, _, v = line.partition("=")
            rows.append((k.strip(), v.strip()))
    return rows


def config_section(index, order: list[str], entry: str, bundle_lines: list[str]) -> list[str]:
    """Everything outside flow.xml that decides behaviour, for the services in the call tree:
    error-code rows, HTTP codes (with the default-500 gaps), ACL, config keys (never values),
    global variables, and WmTestSuite cases."""
    services = set(order)
    version_dirs = []
    for ns in order:
        d = index.resolve(ns)
        if d is None:
            continue
        vdir = index.node_pkg.get(d, package_of(d)).parent.parent   # <api>-il/vN/src/<Package> -> vN
        if (vdir / "config").is_dir() and vdir not in version_dirs:
            version_dirs.append(vdir)
    out = ["## Config and tests outside flow.xml (generated)", ""]
    if not version_dirs:
        return out + ["(no vN/config folder next to the packages in the tree)", ""]
    for vdir in version_dirs:
        cfg = vdir / "config"
        out += [f"### {vdir}", ""]
        rows = []
        for k, v in read_props(cfg / "ERROR_CODES_V2.properties") + read_props(cfg / "ERROR_CODES.properties"):
            parts = k.split("|")
            if len(parts) >= 4 and parts[2] in services:
                rows.append((parts[2], parts[0], parts[1], parts[3], v))
        out.append("ERROR_CODES (endpoint: source system|source code -> app code = description):")
        if rows:
            for ep in sorted({r[0] for r in rows}):
                ep_rows = [r for r in rows if r[0] == ep]
                out.append(f"  {ep}")
                out += [f"    {r[1]}|{r[2]} -> {r[3]} = {r[4]}" for r in ep_rows]
                if not any(r[1] == "ESB" and r[2] == "0" for r in ep_rows):
                    out.append("    (no ESB|0 row: any other source code -> E_UNKNOWN_0 'Failed to determine cause of an error')")
        else:
            out.append("  (no rows for these services -> every mapped error becomes E_UNKNOWN_0)")
        app_codes = {r[3] for r in rows}
        http = {k.rsplit(".", 1)[1]: v for k, v in read_props(cfg / "ERRORS_TO_HTTP_CODES.properties")
                if k.rsplit(".", 1)[0] in services}
        out += ["", f"ERRORS_TO_HTTP_CODES for {entry}:"]
        for code in sorted(set(http) | app_codes):
            out.append(f"  {code} -> {http[code]}" if code in http else f"  {code} -> 500 (no row, default)")
        out.append("  any other error code (errorService _100, E_UNKNOWN_0, ...) -> 500 (default)")
        acl = [f"  {k} = {v}" for k, v in read_props(cfg / "ACL_MAP.properties") if k in services]
        out += ["", "ACL_MAP:"] + (acl or ["  (none)"])
        keys = [k for k, _v in read_props(cfg / "CONFIG_PARAMETERS.properties")
                if any(k.startswith(sv + ".") for sv in services)]
        out += ["", "CONFIG_PARAMETERS keys (values deliberately not shown):"] + ([f"  {k}" for k in keys] or ["  (none)"])
        out.append("")
    gvars = sorted({m for ln in bundle_lines if "[global-vars]" in ln for m in re.findall(r"%([\w.]+)%", ln)})
    if gvars:
        out += ["Variables set with [global-vars] (IS global variables, values not in git):"]
        out += [f"  {g}" for g in gvars] + [""]
    cases = []
    for vdir in version_dirs:
        test_dir = vdir / "test"
        suites = sorted(test_dir.glob("*/resources/test/setup/*.xml")) if test_dir.is_dir() else []
        for suite in suites:
            try:
                root = ET.parse(suite).getroot()
            except ET.ParseError:
                continue
            for tc in root.iter("webMethodsTestCase"):
                svc = tc.find("service")
                if svc is None or f"{svc.get('folder')}:{svc.get('name')}" not in services:
                    continue
                mocks = [f"{m.get('folder')}:{m.get('name')}" for m in tc.findall("mock")]
                files = [f.get("filename") for f in tc.iter("file")]
                cases.append(f"  {tc.get('name')}: service={svc.get('folder')}:{svc.get('name')} mocks={mocks} files={files}")
    out += ["WmTestSuite cases for these services:"]
    out += cases or ["  (none - tests come from captured traffic and the flow branches)"]
    return out + [""]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", action="append", help="folder containing IS packages (repeatable); default: cwd")
    ap.add_argument("--types", action="store_true", help="keep ;type;dim markers in field paths")
    ap.add_argument("--all-packages", action="store_true", help="include *_TEST packages")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("find"); s.add_argument("text")
    s = sub.add_parser("rest"); s.add_argument("text", nargs="?")
    s = sub.add_parser("show"); s.add_argument("target")
    s = sub.add_parser("doc"); s.add_argument("target")
    s = sub.add_parser("catalog", help="write JSON catalogs of shared services/doc types (e.g. co.utils.*)")
    s.add_argument("--prefix", action="append", required=True, help="nsName prefix, e.g. co.utils.v3. (repeatable)")
    s.add_argument("-o", "--output-dir", required=True)
    for name in ("trace", "bundle"):
        s = sub.add_parser(name); s.add_argument("target")
        s.add_argument("--depth", type=int, default=8)
        s.add_argument("--utils", action="store_true", help="also descend into co.utils.* shared services")
        if name == "bundle":
            s.add_argument("-o", "--output")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    roots = [Path(r) for r in (args.root or [os.getcwd()])]
    index = Index(roots, include_tests=args.all_packages)

    if args.cmd == "find":
        hits = sorted(ns for ns in index.nodes if args.text.lower() in ns.lower())
        for ns in hits:
            ndf = read_values(index.nodes[ns][0] / "node.ndf")
            print(f"{ns}  [{node_kind(ndf)}]")
        if not hits:
            print("(no match)")
    elif args.cmd == "rest":
        print("\n".join(cmd_rest(index, args.text)))
    elif args.cmd in ("show", "doc"):
        lines, _ = show_node(index, args.target, args.types)
        print("\n".join(lines))
    elif args.cmd == "catalog":
        cmd_catalog(index, args.prefix, Path(args.output_dir))
    elif args.cmd == "trace":
        print("\n".join(cmd_trace(index, args.target, args.depth, args.utils)))
    elif args.cmd == "bundle":
        order: list[str] = []
        tree = cmd_trace(index, args.target, args.depth, args.utils, collect=order)
        out = [f"# Bundle: {args.target}", "", "## Call tree", "```"] + tree + ["```", ""]
        docs = set()
        for ns in order:
            lines, _ = show_node(index, ns, args.types)
            out += lines + [""]
            for ln in lines:
                docs.update(re.findall(r"Doc<([\w.]+:\w+)>", ln))
        # follow doc references transitively (a Result doc referencing SourceInfo, ...)
        pending, seen_docs, doc_sections = sorted(docs), set(), []
        while pending:
            d = pending.pop(0)
            if d in seen_docs or index.resolve(d) is None:
                continue
            seen_docs.add(d)
            lines, _ = show_node(index, d, args.types, header_level="###")
            doc_sections.append((d, lines))
            for ln in lines:
                pending += [r for r in re.findall(r"Doc<([\w.]+:\w+)>", ln) if r not in seen_docs]
        local_docs = [d for d, _ in sorted(doc_sections)]
        if doc_sections:
            out += ["## Document types referenced by the signatures above (transitively)", ""]
            for _d, lines in sorted(doc_sections):
                out += lines + [""]
        out += config_section(index, order, args.target, out)
        text = "\n".join(out)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            print(f"wrote {args.output} ({len(text.splitlines())} lines, {len(order)} services, {len(local_docs)} doc types)")
        else:
            print(text)


if __name__ == "__main__":
    main()
