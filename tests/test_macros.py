import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import macro_core as core


@contextmanager
def isolated_home():
    with tempfile.TemporaryDirectory(prefix="text-macros-test-") as directory:
        home = Path(directory)
        with patch.dict(os.environ, {
            "HOME": str(home), "XDG_CONFIG_HOME": str(home / "config"),
            "XDG_DATA_HOME": str(home / "data"), "XDG_SESSION_TYPE": "x11",
        }):
            yield home


def settings():
    return {"version": 1, "slots": [{"text": "", "press_enter": False} for _ in range(5)]}


class SettingsTests(unittest.TestCase):
    def test_round_trip_preserves_literal_text_and_whitespace(self):
        with isolated_home():
            data = settings()
            data["slots"][0] = {"text": "  --hello '$HOME' `id` $(id) \\\n你好\n\n", "press_enter": True}
            core.save_settings(data)
            self.assertEqual(core.load_settings(), data)
            self.assertEqual(core.settings_path().stat().st_mode & 0o777, 0o600)

    def test_imports_legacy_macro_without_running_it(self):
        with isolated_home() as home:
            encoded = base64.b64encode("legacy\ntext\n".encode()).decode()
            (home / ".xbindkeysrc").write_text(
                f'"env MACRO_B64={encoded} bash -lc dangerous; xdotool key Return"\n  control + F1\n'
            )
            imported = core.load_settings()
            self.assertEqual(imported["slots"][0], {"text": "legacy\ntext\n", "press_enter": True})
            self.assertEqual(imported["slots"][1:], settings()["slots"][1:])

    def test_corrupt_settings_are_never_overwritten(self):
        with isolated_home():
            core.atomic_write(core.settings_path(), "broken json")
            with self.assertRaises(core.MacroError):
                core.load_settings()
            self.assertEqual(core.settings_path().read_text(), "broken json")

    def test_invalid_settings(self):
        for data in ([], {}, {"version": 1, "slots": []}):
            with self.subTest(data=data), self.assertRaises(core.MacroError):
                core.validate_settings(data)
        data = settings()
        data["slots"][1]["text"] = "a\x00b"
        with self.assertRaises(core.MacroError):
            core.validate_settings(data)

    def test_literal_text_uses_stdin_and_enter_is_optional(self):
        with isolated_home(), patch.object(core, "check_desktop"), patch.object(core.subprocess, "run") as run, patch.object(core.time, "sleep"):
            data = settings()
            text = '--file /etc/passwd; $(touch /tmp/never)\n"quoted"\n'
            data["slots"][2] = {"text": text, "press_enter": True}
            core.save_settings(data)
            core.run_slot(3)
            typed = [call.kwargs["input"] for call in run.call_args_list if "input" in call.kwargs]
            self.assertEqual(typed, text.splitlines())
            for call in run.call_args_list:
                self.assertNotIn(text, call.args[0])
            self.assertEqual(run.call_args_list[-2].args[0], ["xdotool", "keyup", "Control_L", "Control_R"])
            self.assertIn("--clearmodifiers", run.call_args_list[-1].args[0])
            self.assertEqual(run.call_count, 6)
            run.reset_mock()
            core.run_slot(4)
            run.assert_not_called()


class BindingTests(unittest.TestCase):
    def test_migration_preserves_mouse_and_other_modifiers(self):
        original = '''# user's shortcuts
"mouse-action"
  b:8
"another-action"
  Shift + Control + F1
"legacy text"
# keep this comment
  control + F1
"legacy second"
  Release + Control + F2
"keep-f6"
  Control + F6
'''
        merged = core.merge_bindings(original)
        self.assertIn('"mouse-action"\n  b:8', merged)
        self.assertIn('"another-action"\n  Shift + Control + F1', merged)
        self.assertIn('"keep-f6"\n  Control + F6', merged)
        self.assertIn("# keep this comment", merged)
        self.assertNotIn("legacy text", merged)
        self.assertNotIn("legacy second", merged)
        self.assertEqual(core.merge_bindings(merged), merged)
        self.assertEqual(merged.count("--run"), 5)

    def test_damaged_managed_block_fails_without_changing_config(self):
        with self.assertRaises(core.MacroError):
            core.merge_bindings(core.BEGIN + "\nunknown\n")

    def test_backup_is_only_created_once(self):
        with isolated_home() as home, patch.object(core, "check_desktop"), patch.object(core, "reload_shortcuts"):
            original = '"keep-me"\n  b:9\n'
            core.bindings_path().write_text(original)
            core.apply_settings(settings())
            core.apply_settings(settings())
            self.assertEqual((home / ".xbindkeysrc.before-text-macros").read_text(), original)

    def test_wayland_has_an_actionable_error(self):
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":1"}):
            with self.assertRaisesRegex(core.MacroError, "X11"):
                core.check_desktop()

    def test_scheme_config_has_an_actionable_error(self):
        with isolated_home() as home, patch.dict(os.environ, {"DISPLAY": ":1"}), patch.object(core.shutil, "which", return_value="/usr/bin/tool"):
            (home / ".xbindkeysrc.scm").write_text("(legacy)")
            with self.assertRaisesRegex(core.MacroError, "overrides"):
                core.check_desktop()


# Never send synthetic input to the user's real display. The integration checks
# run only when xvfb-run supplies its distinctive authority file.
VIRTUAL_DISPLAY = "xvfb-run" in os.environ.get("XAUTHORITY", "")


@unittest.skipUnless(VIRTUAL_DISPLAY and shutil.which("xbindkeys") and shutil.which("xdotool"), "Run with xvfb-run for isolated X11 integration checks")
class DesktopTests(unittest.TestCase):
    def test_replaces_legacy_daemonized_listener(self):
        with isolated_home():
            core.save_settings(settings())
            core.atomic_write(core.bindings_path(), core.merge_bindings(""))
            try:
                subprocess.run(
                    ["xbindkeys"], stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=True, timeout=5,
                )
                deadline = time.monotonic() + 2
                old_pids = core.matching_daemons()
                while not old_pids and time.monotonic() < deadline:
                    time.sleep(.02)
                    old_pids = core.matching_daemons()
                self.assertTrue(old_pids)
                core.apply_settings(settings())
                new_pids = core.matching_daemons()
                self.assertTrue(new_pids)
                self.assertTrue(set(old_pids).isdisjoint(new_pids))
                for pid in new_pids:
                    args = (Path("/proc") / str(pid) / "cmdline").read_bytes().split(b"\0")
                    self.assertIn(b"-n", args)
            finally:
                for pid in core.matching_daemons():
                    os.kill(pid, signal.SIGTERM)

    def test_start_shortcuts_restores_saved_bindings(self):
        with isolated_home():
            core.save_settings(settings())
            try:
                result = subprocess.run(
                    [sys.executable, core.__file__, "--start-shortcuts"],
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(core.bindings_path().read_text().count("--run"), 5)
                self.assertTrue(core.matching_daemons())
                for pid in core.matching_daemons():
                    args = (Path("/proc") / str(pid) / "cmdline").read_bytes().split(b"\0")
                    self.assertIn(b"-n", args)
            finally:
                for pid in core.matching_daemons():
                    os.kill(pid, signal.SIGTERM)

    def test_installer_creates_valid_launchers_without_touching_settings(self):
        with isolated_home() as home:
            core.save_settings(settings())
            original = core.settings_path().read_bytes()
            # Exercise an installation path requiring Desktop Exec quoting.
            os.environ["XDG_DATA_HOME"] = str(home / 'data with spaces and "quotes" and $cash')
            result = subprocess.run(["bash", "install.sh"], capture_output=True, text=True, check=True)
            self.assertIn("Installed Text Macros", result.stdout)
            data_home = Path(os.environ["XDG_DATA_HOME"])
            self.assertTrue((data_home / "text-macros/macro_app.py").exists())
            for launcher in (data_home / "applications/text-macros.desktop", home / "config/autostart/text-macros.desktop"):
                subprocess.run(["desktop-file-validate", str(launcher)], check=True)
            self.assertEqual(core.settings_path().read_bytes(), original)
            from gi.repository import Gio
            launcher = Gio.DesktopAppInfo.new_from_filename(str(data_home / "applications/text-macros.desktop"))
            self.assertIsNotNone(launcher)
            # GLib's shell parser must recover the exact installed path.
            from gi.repository import GLib
            _, argv = GLib.shell_parse_argv(launcher.get_commandline())
            self.assertEqual(argv[1], str(data_home / "text-macros/macro_app.py"))

    def test_editor_and_all_five_global_shortcuts(self):
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gio, Gtk
        import macro_app

        def pump(seconds=0.2):
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                while Gtk.events_pending():
                    Gtk.main_iteration_do(False)
                time.sleep(0.005)

        with isolated_home():
            app = macro_app.MacroApp()
            # The installed editor may be open on the user's real display.
            # Never register this test window with that running application.
            app.set_flags(Gio.ApplicationFlags.NON_UNIQUE)
            app.register(None)
            editor = macro_app.MacroWindow(app, settings())
            samples = ["first macro", "two\nlines", "quotes: '$HOME' $(id) `id`", "你好 café", "--literal-option\n"]
            for index, (view, enter) in enumerate(editor.editors):
                view.get_buffer().set_text(samples[index])
                enter.set_active(index == 0)
            self.assertTrue(editor.dirty)
            # Exercise the real Save & Apply startup path, with no listener
            # already running. A manually started foreground daemon hid the
            # daemonized-startup bug in the original integration test.
            target = Gtk.Window(title="Text Macros Integration Target")
            target.set_default_size(500, 300)
            text = Gtk.TextView()
            target.add(text)
            target.show_all()
            pump()
            try:
                self.assertTrue(editor.on_save(), editor.status.get_text())
                self.assertFalse(editor.dirty)
                self.assertTrue(core.matching_daemons())
                previous_pids = set(core.matching_daemons())
                self.assertTrue(editor.on_save(), editor.status.get_text())
                self.assertTrue(previous_pids.isdisjoint(core.matching_daemons()))
                window_id = subprocess.check_output(["xdotool", "search", "--name", "^Text Macros Integration Target$"], text=True).splitlines()[0]
                subprocess.run(["xdotool", "windowfocus", "--sync", window_id], check=True)
                text.grab_focus()
                pump()
                subprocess.run([sys.executable, core.__file__, "--run", "1"], check=True)
                pump()
                buf = text.get_buffer()
                self.assertEqual(buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True), samples[0] + "\n")
                for number, sample in enumerate(samples, 1):
                    with self.subTest(shortcut=f"Ctrl+F{number}"):
                        text.get_buffer().set_text("")
                        pump()
                        subprocess.run(["xdotool", "key", f"ctrl+F{number}"], check=True)
                        expected = sample + ("\n" if number == 1 else "")
                        actual = ""
                        deadline = time.monotonic() + 5
                        while actual != expected and time.monotonic() < deadline:
                            pump(0.05)
                            buf = text.get_buffer()
                            actual = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
                        self.assertEqual(actual, expected, core.read_text(core.config_dir() / "listener.log"))
                        # The last character arrives on key-down; allow its
                        # key-up and modifier cleanup to finish before retriggering.
                        pump(0.2)
                        # Reapplying after typing must replace the listener,
                        # avoiding the signal-based reload that could hang it.
                        previous_pids = set(core.matching_daemons())
                        self.assertTrue(editor.on_save(), editor.status.get_text())
                        self.assertTrue(previous_pids.isdisjoint(core.matching_daemons()))
                # Closing the UI leaves the registered shortcuts available.
                editor.destroy()
                core.save_settings({"version": 1, "slots": [{"text": "after close", "press_enter": False}] + settings()["slots"][1:]})
                text.get_buffer().set_text("")
                subprocess.run(["xdotool", "key", "ctrl+F1"], check=True)
                pump(2)
                buf = text.get_buffer()
                self.assertEqual(buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True), "after close")
            finally:
                for pid in core.matching_daemons():
                    os.kill(pid, signal.SIGTERM)
                editor.destroy()
                target.destroy()
                pump()


if __name__ == "__main__":
    unittest.main()
