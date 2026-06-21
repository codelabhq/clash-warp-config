#!/usr/bin/env python3
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROXIES_DIR = ROOT / "proxies"
CONFIG_DIR = ROOT / "config"

TYPES = {
    "geo": {"file": "geo-endpoint.yaml", "label": "geo-endpoint", "marker": "🌍"},
    "origin": {"file": "origin-endpoint.yaml", "label": "origin-endpoint", "marker": "⭐"},
    "default": {"file": "default-endpoint.yaml", "label": "default-endpoint", "marker": "☁️"},
}

BEGIN = "# === BEGIN WARP PROXIES (auto-generated from proxies/*.yaml — do not edit) ==="
END = "# === END WARP PROXIES ==="

DIRECTIVE_RE = re.compile(r"^#\s*warp-types:\s*(.+)$", re.MULTILINE)
BLOCK_RE = re.compile(
    re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL
)
MERGE_RE = re.compile(r"^\s*<<:\s*\*warp-common\s*$", re.MULTILINE)


def load_nodes(type_key):
    path = PROXIES_DIR / TYPES[type_key]["file"]
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(MERGE_RE.sub("", raw)) or {}
    return data.get("proxies", []) or []


def quote(name):
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render(types):
    lines = []
    for t in types:
        marker = TYPES[t]["marker"]
        lines.append(f"  # ── {TYPES[t]['label']} ──")
        for node in load_nodes(t):
            name = str(node["name"])
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
    return "\n".join(lines)


def process(config_path):
    text = config_path.read_text(encoding="utf-8")
    m = DIRECTIVE_RE.search(text)
    if not m:
        return False
    types = [t for t in m.group(1).split() if t in TYPES]
    if not BLOCK_RE.search(text):
        print(f"  ! {config_path.name}: directive present but no BEGIN/END block", file=sys.stderr)
        return False
    block = f"{BEGIN}\n{render(types)}\n{END}"
    new_text = BLOCK_RE.sub(lambda _: block, text)
    if new_text != text:
        config_path.write_text(new_text, encoding="utf-8")
        print(f"  ~ {config_path.name}: {', '.join(types)}")
        return True
    print(f"  = {config_path.name}: up to date")
    return False


def main():
    changed = False
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        if process(path):
            changed = True
    return 0 if changed or True else 1


if __name__ == "__main__":
    sys.exit(main())
