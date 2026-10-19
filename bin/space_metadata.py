#!/usr/bin/env python3
"""Per-space metadata (links and notes) for Herdr. Stdlib only.

  space_metadata.py open   action: find the focused space, open the overlay pane
  space_metadata.py ui     pane: curses list to browse, open, add, edit, delete entries

An entry is {"label", "value"}. A value that is an http(s) URL is a link and enter
opens it; anything else is a note and enter shows it in full. Entries live in
$HERDR_PLUGIN_CONFIG_DIR/metadata.json, keyed by "<git remote>#<directory name>" so
the same checkout shares its list across machines. Directories without a git remote
fall back to their absolute path.
"""
import curses
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
from urllib.parse import urlparse

URL_RE = re.compile(r"https?://\S+$")
SOURCE = "space-metadata"
TOKEN = "meta"


def herdr_bin():
    return os.environ.get("HERDR_BIN_PATH") or "herdr"


def store_path():
    d = os.environ.get("HERDR_PLUGIN_CONFIG_DIR") or os.path.expanduser("~/.config/herdr-space-metadata")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "metadata.json")


def load():
    try:
        with open(store_path()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(data):
    path = store_path()
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def git(directory, *args):
    try:
        out = subprocess.run(["git", "-C", directory, *args], capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def space_key(directory):
    """Stable key for a space: git remote plus directory name, else the path itself."""
    if not os.path.isdir(directory):
        return directory
    remote = git(directory, "remote", "get-url", "origin")
    if not remote:
        return directory
    remote = re.sub(r"^[a-z+]+://", "", remote)  # scheme
    remote = re.sub(r"^[^@/]+@", "", remote)  # user@
    remote = remote.replace(":", "/", 1)  # scp-style host:path
    remote = re.sub(r"(\.git)?/*$", "", remote)
    return f"{remote}#{os.path.basename(directory.rstrip('/'))}"


def cmd_open():
    ctx = {}
    try:
        ctx = json.loads(os.environ.get("HERDR_PLUGIN_CONTEXT_JSON") or "{}")
    except ValueError:
        pass
    workspace = os.environ.get("HERDR_WORKSPACE_ID") or ctx.get("workspace_id") or ""
    directory = ctx.get("workspace_cwd") or ctx.get("focused_pane_cwd") or workspace
    plugin_id = os.environ.get("HERDR_PLUGIN_ID") or "momer.space-metadata"
    cmd = [herdr_bin(), "plugin", "pane", "open", "--plugin", plugin_id,
           "--entrypoint", "metadata", "--placement", "overlay", "--focus",
           "--env", f"SPACE_METADATA_DIR={directory}",
           "--env", f"SPACE_METADATA_WORKSPACE={workspace}"]
    sys.exit(subprocess.call(cmd))


def is_link(value):
    return bool(URL_RE.match(value))


def default_label(value):
    if not is_link(value):
        return value.splitlines()[0][:22] if value else ""
    m = re.search(r"[A-Z][A-Z0-9]+-\d+", value)  # Jira key
    if m:
        return m.group(0)
    host = urlparse(value).netloc
    if "sentry" in host:
        m = re.search(r"issues/(\d+)", value)
        return f"Sentry {m.group(1)}" if m else "Sentry"
    if "chat.google" in host:
        return "Google Chat"
    return host or value


def clipboard_url():
    for cmd in (["wl-paste", "-n"], ["xclip", "-o", "-selection", "clipboard"], ["pbpaste"]):
        if shutil.which(cmd[0]):
            try:
                out = subprocess.run(cmd, capture_output=True, text=True, timeout=1).stdout.strip()
            except (OSError, subprocess.SubprocessError):
                return ""
            return out if is_link(out) else ""
    return ""


def copy_to_clipboard(text):
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["pbcopy"]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, input=text, text=True)
            return True
    return False


def open_url(url):
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, url], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def report_sidebar(entries):
    """Push a short summary to the space's sidebar row (use $meta in ui.sidebar.spaces)."""
    workspace = os.environ.get("SPACE_METADATA_WORKSPACE")
    if not workspace:
        return
    links = sum(is_link(e["value"]) for e in entries)
    notes = len(entries) - links
    summary = " ".join(s for s in (f"{links}↗" if links else "", f"{notes}✎" if notes else "") if s)
    cmd = [herdr_bin(), "workspace", "report-metadata", workspace, "--source", SOURCE]
    cmd += ["--token", f"{TOKEN}={summary}"] if summary else ["--clear-token", TOKEN]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
    except (OSError, subprocess.SubprocessError):
        pass


def prompt(scr, label, initial=""):
    """One-line editor on the bottom row. Returns the text, or None on Esc."""
    h, w = scr.getmaxyx()
    buf, pos = list(initial), len(initial)
    curses.curs_set(1)
    try:
        while True:
            text = "".join(buf)
            shown = (label + text)[-(w - 1):]
            scr.move(h - 1, 0)
            scr.clrtoeol()
            scr.addstr(h - 1, 0, shown, curses.A_BOLD)
            scr.move(h - 1, min(len(label) + pos, w - 1))
            ch = scr.get_wch()
            if ch in ("\n", "\r"):
                return text.strip()
            if ch == "\x1b":
                return None
            if ch in (curses.KEY_BACKSPACE, "\x7f", "\b"):
                if pos:
                    del buf[pos - 1]
                    pos -= 1
            elif ch == curses.KEY_LEFT:
                pos = max(0, pos - 1)
            elif ch == curses.KEY_RIGHT:
                pos = min(len(buf), pos + 1)
            elif ch == "\x15":  # ctrl+u
                buf, pos = [], 0
            elif isinstance(ch, str) and ch.isprintable():
                buf.insert(pos, ch)
                pos += 1
    finally:
        curses.curs_set(0)


def edit_in_editor(scr, initial):
    """Edit text in $VISUAL/$EDITOR, then hand the terminal back to curses."""
    editor = shlex.split(os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi")
    fd, path = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w") as f:
        f.write(initial)
    curses.def_prog_mode()
    curses.endwin()
    try:
        subprocess.call([*editor, path])
    finally:
        curses.reset_prog_mode()
        scr.clear()
        scr.refresh()
    try:
        with open(path) as f:
            return f.read().strip()
    finally:
        os.unlink(path)


def show_note(scr, item):
    """Full-screen view of an entry; any key returns."""
    scr.erase()
    h, w = scr.getmaxyx()
    scr.addstr(0, 0, f" {item['label']} "[: w - 1], curses.A_REVERSE)
    lines = []
    for raw in item["value"].splitlines() or [""]:
        lines += textwrap.wrap(raw, max(10, w - 4)) or [""]
    for i, line in enumerate(lines[: h - 3]):
        scr.addstr(2 + i, 2, line)
    scr.addstr(h - 1, 0, "any key to go back"[: w - 1], curses.A_DIM)
    scr.refresh()
    scr.get_wch()


def edit_entry(scr, item=None, use_editor=False):
    """Collect value then label. Returns an entry dict, or None if cancelled."""
    if use_editor or (item and "\n" in item["value"]):
        value = edit_in_editor(scr, item["value"] if item else "")
    else:
        value = prompt(scr, "URL or note: ", item["value"] if item else clipboard_url())
    if not value:
        return None
    label = prompt(scr, "Label: ", item["label"] if item else default_label(value))
    if label is None:
        return None
    return {"label": label or default_label(value), "value": value}


def ui(scr):
    curses.curs_set(0)
    curses.use_default_colors()
    curses.set_escdelay(25)
    directory = os.environ.get("SPACE_METADATA_DIR", "")
    key = space_key(directory)
    title = os.path.basename(directory.rstrip("/")) or directory or "space"
    data = load()
    if directory and key != directory and directory in data and key not in data:
        data[key] = data.pop(directory)  # entries saved under the old path-only key
        save(data)
    entries = data.setdefault(key, [])
    report_sidebar(entries)
    sel, msg, query = 0, "", ""

    def visible():
        q = query.lower()
        return [i for i, e in enumerate(entries) if q in f"{e['label']} {e['value']}".lower()]

    def changed():
        save(data)
        report_sidebar(entries)

    def activate(item):
        if is_link(item["value"]):
            open_url(item["value"])
            return f"opened {item['label']}"
        show_note(scr, item)
        return ""

    while True:
        shown = visible()
        sel = max(0, min(sel, len(shown) - 1))
        scr.erase()
        h, w = scr.getmaxyx()
        head = f" Metadata · {title}" + (f" · filter: {query}" if query else "") + " "
        scr.addstr(0, 0, head[: w - 1], curses.A_REVERSE)
        if not shown:
            hint = "No matches." if query else "Nothing here yet. Press a to add a link, n for a note."
            scr.addstr(2, 2, hint[: w - 3], curses.A_DIM)
        for row_no, i in enumerate(shown[: max(0, h - 4)]):
            item = entries[i]
            num = str(row_no + 1) if row_no < 9 else " "
            mark = "↗" if is_link(item["value"]) else "✎"
            value = item["value"].replace("\n", " ")
            row = f" {num} {mark} {item['label']:<22.22}  {value}"[: w - 1]
            scr.addstr(2 + row_no, 0, row, curses.A_REVERSE if row_no == sel else curses.A_NORMAL)
        footer = msg or "↵/1-9 open · a add · n note · e edit · E editor · / filter · d del · y copy · q"
        scr.addstr(h - 1, 0, footer[: w - 1], curses.A_DIM)
        scr.refresh()
        msg = ""

        ch = scr.get_wch()
        cur = shown[sel] if shown else None
        if ch == "q":
            return
        elif ch == "\x1b":
            if not query:
                return
            query = ""
        elif ch in ("j", curses.KEY_DOWN) and shown:
            sel = (sel + 1) % len(shown)
        elif ch in ("k", curses.KEY_UP) and shown:
            sel = (sel - 1) % len(shown)
        elif ch in ("\n", "\r") and shown:
            msg = activate(entries[cur])
        elif isinstance(ch, str) and ch in "123456789" and int(ch) <= len(shown):
            sel = int(ch) - 1
            msg = activate(entries[shown[sel]])
        elif ch == "/":
            typed = prompt(scr, "Filter: ", query)
            if typed is not None:
                query, sel = typed, 0
        elif ch == "y" and shown:
            msg = "copied" if copy_to_clipboard(entries[cur]["value"]) else "no clipboard tool found"
        elif ch in ("a", "n"):
            new = edit_entry(scr, use_editor=(ch == "n"))
            if new:
                entries.append(new)
                query = ""
                sel = len(entries) - 1
                changed()
        elif ch in ("e", "E") and shown:
            new = edit_entry(scr, entries[cur], use_editor=(ch == "E"))
            if new:
                entries[cur] = new
                changed()
        elif ch == "d" and shown:
            if prompt(scr, f"Delete '{entries[cur]['label']}'? type y: ") == "y":
                del entries[cur]
                changed()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "open":
        cmd_open()
    elif mode == "ui":
        curses.wrapper(ui)
    else:
        sys.exit("usage: space_metadata.py open|ui")
