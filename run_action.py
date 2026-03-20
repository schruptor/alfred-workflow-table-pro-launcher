#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
from pathlib import Path

HELP_TITLE = "TablePro Launcher Help"


def eprint(msg):
    print(msg, file=sys.stderr)


def candidate_apps():
    env_path = os.environ.get("TABLEPRO_APP_PATH")
    if env_path:
        yield Path(env_path).expanduser()
    for p in [
        Path("/Applications/TablePro.app"),
        Path.home() / "Applications/TablePro.app",
        Path("/Applications/Setapp/TablePro.app"),
    ]:
        yield p


def locate_tablepro_app():
    for p in candidate_apps():
        if p.exists():
            return p
    mdfind = shutil.which("mdfind")
    if mdfind:
        queries = [
            'kMDItemFSName == "TablePro.app"',
            'kMDItemDisplayName == "TablePro" && kMDItemContentType == "com.apple.application-bundle"',
        ]
        for query in queries:
            try:
                out = subprocess.check_output([mdfind, query], text=True).splitlines()
            except Exception:
                continue
            for line in out:
                p = Path(line.strip())
                if p.name == "TablePro.app" and p.exists():
                    return p
    return None


def apple_script(app_path: Path, url: str) -> str:
    app_posix = str(app_path).replace("\\", "\\\\").replace('"', '\\"')
    app_name = app_path.stem.replace("\\", "\\\\").replace('"', '\\"')
    safe_url = url.replace("\\", "\\\\").replace('"', '\\"')
    return f'''
set targetURL to "{safe_url}"
set appPOSIXPath to "{app_posix}"
set appName to "{app_name}"

tell application appPOSIXPath
    launch
    activate
end tell

set maxWait to 180
repeat with i from 1 to maxWait
    tell application "System Events"
        if (name of processes) contains appName then
            exit repeat
        end if
    end tell
    delay 0.1
end repeat

delay 1.25

do shell script "/usr/bin/open -a " & quoted form of appPOSIXPath & space & quoted form of targetURL

tell application appPOSIXPath
    activate
end tell
'''


def show_help_overlay(help_text: str):
    escaped = help_text.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
set helpText to "{escaped}"
display dialog helpText with title "{HELP_TITLE}" buttons {{"OK"}} default button "OK" with icon note
'''
    subprocess.run(["/usr/bin/osascript", "-e", script], check=True)


def open_in_tablepro(url):
    app = locate_tablepro_app()
    if not app:
        raise RuntimeError("TablePro.app was not found. Install TablePro or set TABLEPRO_APP_PATH.")
    subprocess.run(["/usr/bin/osascript", "-e", apple_script(app, url)], check=True)


def open_in_browser(url):
    subprocess.run(["/usr/bin/open", url], check=True)


def copy_to_clipboard(value):
    proc = subprocess.Popen(["/usr/bin/pbcopy"], stdin=subprocess.PIPE)
    proc.communicate(value.encode("utf-8"))
    if proc.returncode != 0:
        raise RuntimeError("pbcopy failed.")


def main():
    action = os.environ.get("action", "tablepro").strip()
    arg = sys.argv[1].strip() if len(sys.argv) > 1 and sys.argv[1].strip() else ""
    if not arg:
        eprint("No argument provided.")
        sys.exit(1)
    try:
        if action == "browser":
            open_in_browser(arg)
        elif action in {"copy_browser_url", "copy_tablepro_url"}:
            copy_to_clipboard(arg)
        elif action == "help_overlay":
            show_help_overlay(arg)
        else:
            open_in_tablepro(arg)
    except subprocess.CalledProcessError as exc:
        eprint(f"Action failed with exit code {exc.returncode}.")
        sys.exit(exc.returncode)
    except Exception as exc:
        eprint(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
