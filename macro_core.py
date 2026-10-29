#!/usr/bin/env python3
"""Persistence and X11 shortcut integration for Text Macros (no GUI dependency)."""

import argparse
import base64
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time


APP_ID = "text-macros"
BEGIN = "# BEGIN text-macros (managed by Text Macros)"
END = "# END text-macros"
SLOT_COUNT = 5
TYPE_DELAY_MS = 100


class MacroError(Exception):
    """An actionable error that can be presented directly to the user."""


def config_dir():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_ID


def settings_path():
    return config_dir() / "macros.json"


def bindings_path():
    return Path.home() / ".xbindkeysrc"


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def atomic_write(path, text):
    """Keep user text private and leave the old file intact on write failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def shortcut_slot(binding):
    """Recognize only Ctrl+F1..F5, leaving other modifiers/mouse bindings alone."""
    tokens = [token.strip().lower() for token in binding.split("#", 1)[0].split("+")]
    tokens = [token for token in tokens if token != "release"]
    if len(tokens) != 2:
        return None
    for number in range(1, SLOT_COUNT + 1):
        if sorted(tokens) in (["control", f"f{number}"], ["ctrl", f"f{number}"]):
            return number
    return None


def command_pairs(text):
    """Find xbindkeys command/key pairs, including intervening comments."""
    lines = text.splitlines(keepends=True)
    index = 0
    while index < len(lines):
        command = lines[index].strip()
        if command.startswith('"') and command.endswith('"'):
            next_index = index + 1
            while next_index < len(lines) and (
                not lines[next_index].strip() or lines[next_index].lstrip().startswith("#")
            ):
                next_index += 1
            if next_index < len(lines) and not lines[next_index].lstrip().startswith('"'):
                yield index, next_index, command[1:-1], shortcut_slot(lines[next_index])
                index = next_index
        index += 1


def default_settings():
    slots = [{"text": "", "press_enter": False} for _ in range(SLOT_COUNT)]
    # Import the old helper's encoded text as data; never execute its command.
    legacy = read_text(bindings_path()) or read_text(Path(__file__).with_name("dot_xbindkeysrc"))
    for _, _, command, number in command_pairs(legacy):
        encoded = re.search(r"\bMACRO_B64=([A-Za-z0-9+/=]+)", command)
        if number is not None and encoded:
            try:
                text = base64.b64decode(encoded[1], validate=True).decode("utf-8")
                if "\x00" not in text:
                    slots[number - 1] = {
                        "text": text,
                        "press_enter": bool(re.search(r"\bkey\s+Return\b", command)),
                    }
            except (ValueError, UnicodeDecodeError):
                pass
    return {"version": 1, "slots": slots}


def validate_settings(data):
    if not isinstance(data, dict) or data.get("version") != 1:
        raise MacroError("Unsupported macro settings format.")
    slots = data.get("slots")
    if not isinstance(slots, list) or len(slots) != SLOT_COUNT:
        raise MacroError("The settings file must contain exactly five macro slots.")
    for slot in slots:
        if not isinstance(slot, dict) or not isinstance(slot.get("text"), str):
            raise MacroError("Each macro slot must contain text.")
        if type(slot.get("press_enter")) is not bool:
            raise MacroError("Each macro slot must have an Enter setting.")
        if "\x00" in slot["text"]:
            raise MacroError("Macro text cannot contain a NUL character.")
    return data


def load_settings():
    try:
        return validate_settings(json.loads(settings_path().read_text(encoding="utf-8")))
    except FileNotFoundError:
        return default_settings()
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise MacroError(f"Cannot read {settings_path()}: {error}. Restore or repair this file.") from error


def save_settings(data):
    validate_settings(data)
    atomic_write(settings_path(), json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def managed_bindings():
    runner = str(Path(__file__).resolve())
    if "\n" in runner or "\r" in runner:
        raise MacroError("The application path must not contain line breaks.")
    lines = [BEGIN]
    for number in range(1, SLOT_COUNT + 1):
        command = shlex.join([sys.executable, runner, "--run", str(number)])
        lines.extend([f'"{command}"', f"  Control + F{number}", ""])
    return "\n".join([*lines, END]) + "\n"


def merge_bindings(existing):
    """Replace our block and legacy Ctrl+Fn keys; preserve all unrelated lines."""
    if existing.count(BEGIN) != existing.count(END) or existing.count(BEGIN) > 1:
        raise MacroError("The managed section in ~/.xbindkeysrc is damaged. Restore its backup first.")
    if BEGIN in existing:
        start, end = existing.index(BEGIN), existing.index(END)
        if end < start:
            raise MacroError("The managed section in ~/.xbindkeysrc is damaged.")
        existing = existing[:start] + existing[end + len(END):].lstrip("\r\n")
    lines = existing.splitlines(keepends=True)
    removed = set()
    for command_index, binding_index, _, number in command_pairs(existing):
        if number is not None:
            removed.update((command_index, binding_index))
    preserved = "".join(line for index, line in enumerate(lines) if index not in removed)
    return preserved.rstrip("\r\n") + "\n\n" + managed_bindings()


def check_desktop():
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or (
        os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("XDG_SESSION_TYPE")
    ):
        raise MacroError("Global text macros require an X11 session. Log in using Ubuntu on Xorg.")
    if not os.environ.get("DISPLAY"):
        raise MacroError("No X11 display found. Open Text Macros from your desktop session.")
    missing = [name for name in ("xbindkeys", "xdotool") if not shutil.which(name)]
    if missing:
        raise MacroError("Install the missing tools: sudo apt install " + " ".join(missing))
    if bindings_path().with_suffix(".scm").exists():
        raise MacroError("~/.xbindkeysrc.scm overrides text bindings. Move it aside before enabling Text Macros.")


def matching_daemons():
    """Only reload this user's xbindkeys using the default file on this display."""
    found = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid() or (proc / "comm").read_text().strip() != "xbindkeys":
                continue
            args = (proc / "cmdline").read_bytes().split(b"\0")
            if any(arg in (b"-f", b"--file", b"-fg", b"--file-guile") for arg in args):
                continue
            env = dict(item.split(b"=", 1) for item in (proc / "environ").read_bytes().split(b"\0") if b"=" in item)
            if env.get(b"DISPLAY") == os.fsencode(os.environ.get("DISPLAY", "")) and env.get(b"HOME") == os.fsencode(Path.home()):
                found.append(int(proc.name))
        except (OSError, ValueError):
            continue
    return found


def reload_shortcuts():
    daemons = set(matching_daemons())
    # xbindkeys reloads Xlib/Guile state inside its SIGHUP handler. This can
    # deadlock a live listener. Always start a fresh process when applying.
    for pid in daemons:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 2
    while daemons.intersection(matching_daemons()):
        if time.monotonic() >= deadline:
            raise MacroError("Could not restart the old shortcut listener. Close it and click Save & Apply again.")
        time.sleep(0.02)
    log_path = config_dir() / "listener.log"
    atomic_write(log_path, "")
    with log_path.open("a", encoding="utf-8") as log:
        listener = subprocess.Popen(
            ["xbindkeys", "-n"], stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
    try:
        listener.wait(timeout=0.2)
    except subprocess.TimeoutExpired:
        # Reap the child if it exits while the editor remains open, while
        # allowing it to outlive the editor or the login-startup helper.
        threading.Thread(target=listener.wait, daemon=True).start()
        return
    raise MacroError(read_text(log_path).strip() or "Could not start xbindkeys.")


def apply_settings(data):
    check_desktop()
    validate_settings(data)
    path = bindings_path()
    previous = read_text(path)
    updated = merge_bindings(previous)
    # Preserve the first pre-app configuration for an easy manual rollback.
    backup = path.with_name(path.name + ".before-text-macros")
    if path.exists() and not backup.exists():
        atomic_write(backup, previous)
    save_settings(data)
    if updated != previous:
        atomic_write(path, updated)
    reload_shortcuts()


def run_slot(number):
    data = load_settings()
    slot = data["slots"][number - 1]
    if not slot["text"]:
        return
    check_desktop()
    config_dir().mkdir(parents=True, exist_ok=True)
    # Ignore overlapping repeats rather than interleave two macros' characters.
    with (config_dir() / "typing.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        time.sleep(0.08)
        # Pass literal text via stdin, and send line breaks/tabs as real keys.
        # Explicit Return avoids xdotool's Linefeed key being ignored by editors.
        try:
            for part in re.split(r"(\r\n|[\n\r\t])", slot["text"]):
                if not part:
                    continue
                if part in ("\n", "\r", "\r\n", "\t"):
                    key = "Tab" if part == "\t" else "Return"
                    subprocess.run(
                        ["xdotool", "key", "--clearmodifiers", "--delay", str(TYPE_DELAY_MS), key],
                        check=True, timeout=5,
                    )
                else:
                    subprocess.run(
                        ["xdotool", "type", "--clearmodifiers", "--delay", str(TYPE_DELAY_MS), "--file", "-"],
                        input=part, text=True, check=True,
                        timeout=max(120, len(part) * TYPE_DELAY_MS / 1000 + 10),
                    )
        finally:
            # If Ctrl was physically released while text was being typed,
            # --clearmodifiers may have restored it. Never leave it stuck down.
            subprocess.run(["xdotool", "keyup", "Control_L", "Control_R"], check=True, timeout=5)
        if slot["press_enter"]:
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers", "--delay", str(TYPE_DELAY_MS), "Return"],
                check=True, timeout=5,
            )


def main():
    parser = argparse.ArgumentParser(description="Text Macros shortcut helper")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--run", type=int, choices=range(1, SLOT_COUNT + 1), metavar="1..5")
    action.add_argument("--start-shortcuts", action="store_true", help="Restore saved shortcuts at X11 login")
    args = parser.parse_args()
    try:
        if args.run is not None:
            run_slot(args.run)
        elif settings_path().exists():
            apply_settings(load_settings())
    except (MacroError, OSError, subprocess.SubprocessError) as error:
        print(f"Text Macros: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
