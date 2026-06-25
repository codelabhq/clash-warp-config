#!/usr/bin/env python3
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROXIES_DIR = ROOT / "proxies"
CONFIG_DIR = ROOT / "config"
AMNEZIA_FILE = PROXIES_DIR / "amnezia.yaml"

TYPES = {
    "geo": {"file": "geo-endpoint.yaml", "label": "geo-endpoint", "marker": "🌍"},
    "origin": {"file": "origin-endpoint.yaml", "label": "origin-endpoint", "marker": "⭐"},
    "default": {"file": "default-endpoint.yaml", "label": "default-endpoint", "marker": "☁️"},
}

BEGIN = "# === BEGIN WARP PROXIES (auto-generated from proxies/*.yaml — do not edit) ==="
END = "# === END WARP PROXIES ==="
AMNEZIA_BEGIN = "# === BEGIN AMNEZIA ANCHORS (auto-generated from proxies/amnezia.yaml — do not edit) ==="
AMNEZIA_END = "# === END AMNEZIA ANCHORS ==="

DIRECTIVE_RE = re.compile(r"^#\s*warp-types:\s*(.+)$", re.MULTILINE)
BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)
AMNEZIA_BLOCK_RE = re.compile(re.escape(AMNEZIA_BEGIN) + r".*?" + re.escape(AMNEZIA_END), re.DOTALL)
MERGE_RE = re.compile(r"^\s*<<:\s*\*warp-common\s*$", re.MULTILINE)

ALT_VARIANTS = ["alt1", "alt2", "alt3"]


def load_nodes(type_key):
    path = PROXIES_DIR / TYPES[type_key]["file"]
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(MERGE_RE.sub("", raw)) or {}
    return data.get("proxies", []) or []


def load_amnezia():
    data = yaml.safe_load(AMNEZIA_FILE.read_text(encoding="utf-8")) or {}
    return data.get("amnezia", {}) or {}


def quote(name):
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def alt_name(name, n):
    prefix, rest = "", name
    if name.startswith("[") and "] " in name:
        i = name.index("] ") + 2
        prefix, rest = name[:i], name[i:]
    return f"{prefix}(Alt {n}) {rest}"


def emit_node(lines, marker, node, name_override=None, amnezia=None, variant=None):
    name = name_override if name_override is not None else str(node["name"])
    if not name.startswith("["):
        name = f"[{marker}] {name}"
    lines.append(f"  - name: {quote(name)}")
    lines.append("    <<: *warp-common")
    lines.append(f"    server: {node['server']}")
    lines.append(f"    port: {node['port']}")
    for k, v in node.items():
        if k in ("name", "server", "port"):
            continue
        lines.append(f"    {k}: {v}")
    if variant is not None:
        lines.append("    amnezia-wg-option:")
        lines.append("      <<: *amnezia-base")
        lines.append(f"      i1: *i1-{variant}")
        if "i2" in amnezia.get(variant, {}):
            lines.append(f"      i2: *i2-{variant}")


def render(types, amnezia):
    lines = []
    for t in types:
        marker = TYPES[t]["marker"]
        lines.append(f"  # ── {TYPES[t]['label']} ──")
        nodes = load_nodes(t)
        alt_map = {}
        if t == "origin":
            picked = 0
            for idx, node in enumerate(nodes):
                if picked >= len(ALT_VARIANTS):
                    break
                if str(node["name"]).endswith(":4500"):
                    alt_map[idx] = picked
                    picked += 1
        for idx, node in enumerate(nodes):
            emit_node(lines, marker, node)
            if idx in alt_map:
                n = alt_map[idx]
                emit_node(
                    lines,
                    marker,
                    node,
                    name_override=alt_name(str(node["name"]), n + 1),
                    amnezia=amnezia,
                    variant=ALT_VARIANTS[n],
                )
    return "\n".join(lines)


def render_amnezia_anchors(amnezia):
    base = amnezia.get("base", {})
    lines = [AMNEZIA_BEGIN, "amnezia-common: &amnezia-common"]
    for k, v in base.items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    for variant, data in amnezia.items():
        if variant == "base":
            continue
        if "i1" in data:
            lines.append(f"i1-{variant}: &i1-{variant} {data['i1']}")
        if "i2" in data:
            lines.append(f"i2-{variant}: &i2-{variant} {data['i2']}")
    lines.append(AMNEZIA_END)
    return "\n".join(lines)


def process(config_path, amnezia):
    text = config_path.read_text(encoding="utf-8")
    m = DIRECTIVE_RE.search(text)
    if not m:
        return False
    types = [t for t in m.group(1).split() if t in TYPES]
    new_text = text

    if AMNEZIA_BLOCK_RE.search(new_text):
        new_text = AMNEZIA_BLOCK_RE.sub(lambda _: render_amnezia_anchors(amnezia), new_text)
    else:
        print(f"  ! {config_path.name}: no AMNEZIA ANCHORS block", file=sys.stderr)

    if not BLOCK_RE.search(new_text):
        print(f"  ! {config_path.name}: directive present but no BEGIN/END block", file=sys.stderr)
        return False
    block = f"{BEGIN}\n{render(types, amnezia)}\n{END}"
    new_text = BLOCK_RE.sub(lambda _: block, new_text)

    if new_text != text:
        config_path.write_text(new_text, encoding="utf-8")
        print(f"  ~ {config_path.name}: {', '.join(types)}")
        return True
    print(f"  = {config_path.name}: up to date")
    return False


def main():
    amnezia = load_amnezia()
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        process(path, amnezia)
    return 0


if __name__ == "__main__":
    sys.exit(main())
