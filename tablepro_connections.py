#!/usr/bin/env python3
import json
import os
import plistlib
import re
import sys
import urllib.parse
from pathlib import Path

CONNECTIONS_KEY = "com.TablePro.connections"
TAGS_KEY = "com.TablePro.tags"
GROUPS_KEY = "com.TablePro.groups"
DEFAULT_PREFS = Path.home() / "Library/Preferences/com.TablePro.plist"
HELP_TOKENS = {"help", "--help", "-h"}

SCHEME_MAP = {
    "MySQL": "mysql",
    "MariaDB": "mariadb",
    "PostgreSQL": "postgresql",
    "SQLite": "sqlite",
    "MongoDB": "mongodb",
    "Redis": "redis",
    "Redshift": "redshift",
    "SQL Server": "mssql",
    "DuckDB": "duckdb",
    "Cassandra": "cassandra",
    "ScyllaDB": "scylladb",
    "Oracle": "oracle",
    "ClickHouse": "clickhouse",
    "Cloudflare D1": "d1",
    "etcd": "etcd",
}

FILE_TYPES = {"SQLite", "DuckDB"}

HELP_TEXT = """TablePro Launcher Help\n\nKeyword\n• tpro\n\nSearch\n• Any free text matches name, type, host, database, username, SSH host, group, tag, and browser target\n\nFilters\n• tag:production\n• group:backend\n• group:backend tag:production postgres\n• group:analytics redis\n\nShortcuts on a connection\n• Enter → Open the connection in TablePro\n• Command+Enter → Open the SSH host or normal host in your default browser\n• Option+Enter → Copy the SSH host or normal host URL\n• Control+Enter → Copy the generated TablePro connection URL\n• Shift+Enter → Show this help overlay\n\nNotes\n• Browser actions prefer sshHost when SSH is enabled\n• TablePro is launched via AppleScript first, then the selected connection is opened\n• If you type help, --help, or -h, the help overlay is available at the top of the results\n"""

def alfred(items, variables=None):
    payload = {"items": items}
    if variables:
        payload["variables"] = variables
    print(json.dumps(payload, ensure_ascii=False))

def item(title, subtitle, arg=None, valid=True, uid=None, mods=None, variables=None,
         autocomplete=None, icon_path=None, quicklookurl=None):
    data = {"title": title, "subtitle": subtitle, "valid": valid}
    if arg is not None:
        data["arg"] = arg
    if uid is not None:
        data["uid"] = uid
    if mods:
        data["mods"] = mods
    if variables:
        data["variables"] = variables
    if autocomplete:
        data["autocomplete"] = autocomplete
    if icon_path:
        data["icon"] = {"path": icon_path}
    if quicklookurl:
        data["quicklookurl"] = quicklookurl
    return data

def load_json_bytes(raw, label):
    if raw is None:
        return []
    if not isinstance(raw, (bytes, bytearray)):
        raise ValueError(f"Unexpected format for {label}")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Could not decode {label}: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError(f"Decoded {label} is not a list")
    return payload

def load_state():
    prefs_path = Path(os.environ.get("TABLEPRO_PREFS_PATH", DEFAULT_PREFS)).expanduser()
    if not prefs_path.exists():
        return None, f"TablePro preferences not found: {prefs_path}"
    try:
        with prefs_path.open("rb") as f:
            prefs = plistlib.load(f)
    except Exception as exc:
        return None, f"Could not read TablePro preferences: {exc}"

    try:
        connections = load_json_bytes(prefs.get(CONNECTIONS_KEY), CONNECTIONS_KEY)
        tags = load_json_bytes(prefs.get(TAGS_KEY), TAGS_KEY)
        groups = load_json_bytes(prefs.get(GROUPS_KEY), GROUPS_KEY)
    except Exception as exc:
        return None, str(exc)

    tag_map = {str(t.get("id", "")): t for t in tags if isinstance(t, dict)}
    group_map = {str(g.get("id", "")): g for g in groups if isinstance(g, dict)}
    return {"connections": connections, "tags": tag_map, "groups": group_map}, None

def percent_userinfo(value):
    return urllib.parse.quote(str(value), safe="")

def encode_name(name):
    encoded = urllib.parse.quote(str(name).replace(" ", "+"), safe="+")
    return encoded.replace("&", "%26").replace("=", "%3D")

def build_tablepro_url(conn):
    db_type = str(conn.get("type", "") or "")
    scheme = SCHEME_MAP.get(db_type, db_type.lower().replace(" ", ""))
    database = str(conn.get("database", "") or "")

    if db_type == "SQLite":
        return f"sqlite:///{database[1:]}" if database.startswith("/") else f"sqlite://{database}"
    if db_type == "DuckDB":
        return f"duckdb:///{database[1:]}" if database.startswith("/") else f"duckdb://{database}"

    username = str(conn.get("username", "") or "")
    host = str(conn.get("host", "") or "")
    port = conn.get("port")

    url = f"{scheme}://"
    if username:
        url += f"{percent_userinfo(username)}@"
    url += host
    if port not in (None, "", 0):
        url += f":{port}"
    url += f"/{database}"

    name = str(conn.get("name", "") or "")
    if name:
        url += f"?name={encode_name(name)}"
    return url

def normalize_web_candidate(raw):
    raw = str(raw or "").strip()
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        return raw
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
        return raw
    return f"https://{raw}"

def build_browser_url(conn):
    if conn.get("sshEnabled") and str(conn.get("sshHost", "") or "").strip():
        return normalize_web_candidate(conn.get("sshHost"))
    return normalize_web_candidate(conn.get("host"))

def get_tag_name(conn, tag_map):
    tag_id = str(conn.get("tagId") or "")
    tag = tag_map.get(tag_id)
    return str(tag.get("name") or "") if tag else ""

def get_group_name(conn, group_map):
    group_id = str(conn.get("groupId") or "")
    group = group_map.get(group_id)
    return str(group.get("name") or "") if group else ""

def format_target(conn):
    db_type = str(conn.get("type", "") or "")
    if db_type in FILE_TYPES:
        return str(conn.get("database", "") or "")
    user = str(conn.get("username", "") or "")
    host = str(conn.get("host", "") or "")
    port = conn.get("port")
    database = str(conn.get("database", "") or "")
    target = ""
    if user:
        target += f"{user}@"
    target += host
    if port not in (None, "", 0):
        target += f":{port}"
    if database:
        target += f"/{database}"
    return target

def format_subtitle(conn, tag_name, group_name, browser_url):
    parts = []
    db_type = str(conn.get("type", "") or "")
    target = format_target(conn)
    if db_type:
        parts.append(db_type)
    if target:
        parts.append(target)
    if conn.get("sshEnabled"):
        ssh_host = str(conn.get("sshHost", "") or "")
        ssh_port = conn.get("sshPort")
        ssh_part = f"SSH {ssh_host}" if ssh_host else "SSH"
        if ssh_host and ssh_port not in (None, "", 0):
            ssh_part += f":{ssh_port}"
        parts.append(ssh_part)
    if group_name:
        parts.append(f"Group {group_name}")
    if tag_name:
        parts.append(f"Tag {tag_name}")
    if browser_url:
        parts.append(browser_url)
    return " • ".join([p for p in parts if p])

def parse_query(query):
    tokens = [t for t in query.strip().split() if t]
    groups, tags, text_terms = [], [], []
    mode = None
    for token in tokens:
        lower = token.lower()
        if lower in {"group:", "gruppe:"}:
            mode = "group"
            continue
        if lower in {"tag:", "tags:"}:
            mode = "tag"
            continue
        if lower.startswith(("group:", "gruppe:")):
            groups.append(token.split(":", 1)[1]); mode = None; continue
        if lower.startswith(("tag:", "tags:")):
            tags.append(token.split(":", 1)[1]); mode = None; continue
        if mode == "group":
            groups.append(token); mode = None; continue
        if mode == "tag":
            tags.append(token); mode = None; continue
        text_terms.append(token)
    return {
        "groups": [g.strip().lower() for g in groups if g.strip()],
        "tags": [t.strip().lower() for t in tags if t.strip()],
        "terms": [t.strip().lower() for t in text_terms if t.strip()],
    }

def wants_help(query):
    stripped = query.strip().lower()
    return stripped in HELP_TOKENS

def matches(conn, parsed, tag_name, group_name, browser_url):
    if parsed["tags"] and tag_name.lower() not in parsed["tags"]:
        return False
    if parsed["groups"] and group_name.lower() not in parsed["groups"]:
        return False
    haystack = " ".join([
        str(conn.get("name", "")),
        str(conn.get("type", "")),
        str(conn.get("host", "")),
        str(conn.get("database", "")),
        str(conn.get("username", "")),
        str(conn.get("sshHost", "")),
        tag_name, group_name, browser_url,
    ]).lower()
    return all(term in haystack for term in parsed["terms"])

def help_item():
    return item(
        "Show TablePro Launcher help",
        "Filters, shortcuts, browser actions, and examples",
        arg=HELP_TEXT,
        uid="help-overlay",
        mods={
            "shift": {
                "subtitle": "Show the help overlay",
                "valid": True,
                "arg": HELP_TEXT,
                "variables": {"action": "help_overlay"},
            }
        },
        variables={"action": "help_overlay"},
        icon_path="icon.png",
    )

def make_mods(browser_url, tablepro_url):
    return {
        "cmd": {
            "subtitle": "Open host or SSH URL in your browser",
            "valid": bool(browser_url),
            "arg": browser_url or "",
            "variables": {"action": "browser"},
        },
        "alt": {
            "subtitle": "Copy host or SSH URL",
            "valid": bool(browser_url),
            "arg": browser_url or "",
            "variables": {"action": "copy_browser_url"},
        },
        "ctrl": {
            "subtitle": "Copy the TablePro connection URL",
            "valid": True,
            "arg": tablepro_url,
            "variables": {"action": "copy_tablepro_url"},
        },
        "shift": {
            "subtitle": "Show the workflow help overlay",
            "valid": True,
            "arg": HELP_TEXT,
            "variables": {"action": "help_overlay"},
        },
    }

def suggestion_items(state, parsed):
    items = []
    if not parsed["groups"]:
        groups = sorted({str(v.get("name") or "") for v in state["groups"].values() if str(v.get("name") or "").strip()})
        for group in groups[:6]:
            items.append(item(
                f"Filter by group: {group}",
                "Autocomplete the group filter",
                valid=False,
                autocomplete=f"group:{group}",
                icon_path="icons/group.png",
            ))
    if not parsed["tags"]:
        tags = sorted({str(v.get("name") or "") for v in state["tags"].values() if str(v.get("name") or "").strip()})
        for tag in tags[:6]:
            prefix = (" ".join(parsed["terms"]) + " ") if parsed["terms"] else ""
            items.append(item(
                f"Filter by tag: {tag}",
                "Autocomplete the tag filter",
                valid=False,
                autocomplete=(prefix + f"tag:{tag}").strip(),
                icon_path="icons/tag.png",
            ))
    return items[:6]

def connection_icon(conn):
    if conn.get("sshEnabled"):
        return "icons/ssh.png"
    db_type = str(conn.get("type", "") or "")
    if db_type in {"SQLite", "DuckDB"}:
        return "icons/filedb.png"
    return "icons/database.png"

def main():
    query = sys.argv[1] if len(sys.argv) > 1 else ""
    if wants_help(query):
        alfred([help_item()])
        return

    state, error = load_state()
    if error:
        alfred([item("TablePro data could not be loaded", error, valid=False, icon_path="icons/error.png")]); return
    connections = state["connections"]
    if not connections:
        alfred([item("No TablePro connections found", "Create at least one connection in TablePro first.", valid=False, icon_path="icons/error.png")]); return

    parsed = parse_query(query)
    filtered = []
    for conn in connections:
        if not isinstance(conn, dict):
            continue
        tag_name = get_tag_name(conn, state["tags"])
        group_name = get_group_name(conn, state["groups"])
        tablepro_url = build_tablepro_url(conn)
        browser_url = build_browser_url(conn)
        if matches(conn, parsed, tag_name, group_name, browser_url):
            filtered.append((conn, tag_name, group_name, tablepro_url, browser_url))

    if not filtered:
        items = [
            help_item(),
            item("No matching connections", "Try tag:<name>, group:<name>, or combine them with free text.", valid=False, icon_path="icons/error.png")
        ]
        items.extend(suggestion_items(state, parsed))
        alfred(items)
        return

    filtered.sort(key=lambda row: (
        str(row[2] or "").lower(),
        str(row[1] or "").lower(),
        str(row[0].get("name") or row[0].get("database") or row[0].get("host") or "").lower(),
    ))

    items = [help_item()] if not query.strip() else []
    for conn, tag_name, group_name, tablepro_url, browser_url in filtered:
        title = str(conn.get("name") or conn.get("database") or conn.get("host") or "Untitled connection")
        uid = str(conn.get("id") or title)
        items.append(item(
            title,
            format_subtitle(conn, tag_name, group_name, browser_url),
            arg=tablepro_url,
            uid=uid,
            mods=make_mods(browser_url, tablepro_url),
            variables={"action": "tablepro"},
            icon_path=connection_icon(conn),
            quicklookurl=browser_url or None,
        ))

    if not query.strip():
        items.insert(1, item(
            "Search your TablePro connections",
            "Enter opens in TablePro. Command opens the host or SSH URL in your browser.",
            valid=False,
            autocomplete="tag:production ",
            icon_path="icon.png",
        ))
    alfred(items)

if __name__ == "__main__":
    main()
