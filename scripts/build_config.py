#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROXIES_DIR = ROOT / "proxies"
CONFIG_DIR = ROOT / "config"
SETTINGS_DIR = ROOT / "settings"
AMNEZIA_FILE = SETTINGS_DIR / "amnezia.yaml"
RULE_PROVIDERS_FILE = SETTINGS_DIR / "rule-providers.json"
PROXY_GROUPS_FILE = SETTINGS_DIR / "proxy-groups.json"
RULES_FILE = SETTINGS_DIR / "rules.json"

DEFAULT_INTERVAL = "*default-interval"

TYPES = {
    "geo": {"file": "geo-endpoint.yaml", "label": "geo-endpoint", "marker": "🌍"},
    "origin": {"file": "origin-endpoint.yaml", "label": "origin-endpoint", "marker": "⭐"},
    "default": {"file": "default-endpoint.yaml", "label": "default-endpoint", "marker": "☁️"},
}

WARP_BEGIN = "# === BEGIN WARP PROXIES (auto-generated from proxies/*.yaml — do not edit) ==="
WARP_END = "# === END WARP PROXIES ==="
AMNEZIA_BEGIN = "# === BEGIN AMNEZIA ANCHORS (auto-generated from settings/amnezia.yaml — do not edit) ==="
AMNEZIA_END = "# === END AMNEZIA ANCHORS ==="
RP_BEGIN = "# === BEGIN RULE-PROVIDERS (auto-generated from settings/rule-providers.json — do not edit) ==="
RP_END = "# === END RULE-PROVIDERS ==="
PG_BEGIN = "# === BEGIN PROXY-GROUPS (auto-generated from settings/proxy-groups.json — do not edit) ==="
PG_END = "# === END PROXY-GROUPS ==="
RULES_BEGIN = "# === BEGIN RULES (auto-generated from settings/rules.json — do not edit) ==="
RULES_END = "# === END RULES ==="

WARP_TYPES_RE = re.compile(r"^#\s*warp-types:\s*(.+)$", re.MULTILINE)
DEVICE_RE = re.compile(r"^#\s*device:\s*(\S+)\s*$", re.MULTILINE)
MERGE_RE = re.compile(r"^\s*<<:\s*\*warp-common\s*$", re.MULTILINE)

ALT_VARIANTS = ["alt1", "alt2", "alt3"]


def block_re(begin_prefix, end):
    return re.compile(re.escape(begin_prefix) + r".*?" + re.escape(end), re.DOTALL)


WARP_RE = block_re("# === BEGIN WARP PROXIES", WARP_END)
AMNEZIA_RE = block_re("# === BEGIN AMNEZIA ANCHORS", AMNEZIA_END)
RP_RE = block_re("# === BEGIN RULE-PROVIDERS", RP_END)
PG_RE = block_re("# === BEGIN PROXY-GROUPS", PG_END)
RULES_RE = block_re("# === BEGIN RULES", RULES_END)


def load_nodes(type_key):
    path = PROXIES_DIR / TYPES[type_key]["file"]
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(MERGE_RE.sub("", raw)) or {}
    return data.get("proxies", []) or []


def load_amnezia():
    data = yaml.safe_load(AMNEZIA_FILE.read_text(encoding="utf-8")) or {}
    return data.get("amnezia", {}) or {}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def in_device(entry, device):
    devices = entry.get("devices")
    return device in devices if devices else True


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


def render_warp(types, amnezia):
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
    lines = ["amnezia-common: &amnezia-common"]
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
    return "\n".join(lines)


def render_rule_providers(providers, device):
    lines = ["rule-providers:"]
    for p in providers:
        if not in_device(p, device):
            continue
        lines.append(f"  {p['name']}:")
        lines.append(f"    type: {p.get('type', 'http')}")
        lines.append(f"    behavior: {p['behavior']}")
        if p.get("format"):
            lines.append(f"    format: {p['format']}")
        lines.append(f"    url: {p['url']}")
        lines.append(f"    path: {p['path']}")
        lines.append(f"    interval: {p.get('interval', DEFAULT_INTERVAL)}")
    return "\n".join(lines)


def emit_field(lines, key, value, indent):
    pad = " " * indent
    if isinstance(value, list):
        lines.append(f"{pad}{key}:")
        for item in value:
            lines.append(f"{pad}  - {item}")
    elif isinstance(value, bool):
        lines.append(f"{pad}{key}: {'true' if value else 'false'}")
    elif key in ("filter", "exclude-filter"):
        lines.append(f'{pad}{key}: "{value}"')
    else:
        lines.append(f"{pad}{key}: {value}")


def render_proxy_groups(groups, device):
    lines = ["proxy-groups:"]
    for g in groups:
        if not in_device(g, device):
            continue
        overrides = g.get("overrides", {}).get(device, {})
        lines.append(f"  - name: {g['name']}")
        for k, v in g.items():
            if k in ("name", "devices", "overrides"):
                continue
            emit_field(lines, k, overrides.get(k, v), 4)
    return "\n".join(lines)


def render_rules(rules, device):
    lines = ["rules:"]
    for r in rules:
        if "comment" in r:
            lines.append("")
            lines.append(f"  # {r['comment']}")
        elif "rule" in r and in_device(r, device):
            lines.append(f"  - {r['rule']}")
    return "\n".join(lines)


def replace_block(text, regex, begin, end, inner):
    if not regex.search(text):
        return text, False
    return regex.sub(lambda _: f"{begin}\n{inner}\n{end}", text), True


def process(config_path, amnezia, providers, groups, rules):
    text = config_path.read_text(encoding="utf-8")
    original = text
    name = config_path.name

    text, ok = replace_block(text, AMNEZIA_RE, AMNEZIA_BEGIN, AMNEZIA_END, render_amnezia_anchors(amnezia))
    if not ok:
        print(f"  ! {name}: no AMNEZIA ANCHORS block", file=sys.stderr)

    warp_match = WARP_TYPES_RE.search(text)
    if warp_match:
        types = [t for t in warp_match.group(1).split() if t in TYPES]
        text, ok = replace_block(text, WARP_RE, WARP_BEGIN, WARP_END, render_warp(types, amnezia))
        if not ok:
            print(f"  ! {name}: warp-types present but no WARP PROXIES block", file=sys.stderr)
    else:
        print(f"  ! {name}: no warp-types directive", file=sys.stderr)

    device_match = DEVICE_RE.search(text)
    if device_match:
        device = device_match.group(1)
        text, _ = replace_block(text, RP_RE, RP_BEGIN, RP_END, render_rule_providers(providers, device))
        text, _ = replace_block(text, PG_RE, PG_BEGIN, PG_END, render_proxy_groups(groups, device))
        text, _ = replace_block(text, RULES_RE, RULES_BEGIN, RULES_END, render_rules(rules, device))
    else:
        print(f"  ! {name}: no device directive — skipped providers/groups/rules", file=sys.stderr)

    if text != original:
        with open(config_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"  ~ {name}: updated")
        return True
    print(f"  = {name}: up to date")
    return False


def main():
    amnezia = load_amnezia()
    providers = load_json(RULE_PROVIDERS_FILE)
    groups = load_json(PROXY_GROUPS_FILE)
    rules = load_json(RULES_FILE)
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        process(path, amnezia, providers, groups, rules)
    return 0


if __name__ == "__main__":
    sys.exit(main())
