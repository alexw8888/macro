# Linux text macro app

The requested absolute `/plans` directory is not writable (an escalated attempt also returned permission denied). Keep this plan in the repository's `plans/` directory.

Build a native Linux GTK app with five multiline text slots mapped to Ctrl+F1 through Ctrl+F5. Fn is the hardware layer used to access function keys on some keyboards.

1. [x] Preserve existing shortcuts and unrelated working-tree edits.
2. [x] Add persistent JSON storage, safe text execution, and managed xbindkeys bindings. Import the existing Ctrl+F1 macro when possible.
3. [x] Build a five-slot editor with Save & Apply, optional Enter per slot, activation feedback, and unsaved-change handling.
4. [x] Add a desktop launcher, installer, and usage instructions.
5. [x] Test migration, persistence, text safety, installation, and the X11 shortcut-to-text flow using an isolated display.

## Result

- All 13 unit and isolated X11 integration checks passed, including real keyboard injection for all five shortcuts, multiline and Unicode text, persistence after closing the editor, installation and daemon startup.
- Verified a rendered preview with all five input slots visible.
- Installed the per-user application and login startup entry; validated both desktop files and confirmed the Text Macros window opened on the user's desktop.
- Python compilation, shell syntax and git whitespace checks passed.

## Shortcut startup fix

1. [x] Reproduce the reported failure on the user's X11 desktop without exposing macro text.
2. [x] Confirm that the runner types correctly but the daemonized xbindkeys listener handles no shortcuts; verify that `xbindkeys -n` restores all five shortcuts.
3. [x] Start a detached foreground listener, migrate old daemonized instances, and retain startup diagnostics.
4. [x] Update integration coverage to test the actual Save & Apply listener startup, then verify the installed fix on the real desktop.

All 14 checks pass, including migration of a daemonized listener. Reinstalled the app, launched its installed login-startup helper from a stopped listener, and verified that Ctrl+F1 through Ctrl+F5 insert the user's saved text into a temporary GTK text field on the real desktop. Macro contents were preserved and were not printed in diagnostics.

## Repeated listener hang

- [x] Confirm a blocked foreground listener with an available typing lock and intact settings.
- [x] Replace signal-based live reload with a fresh listener on every Save & Apply.
- [x] Verify repeated Save & Apply after typing, reinstall, and reopen the editor to load the updated backend.

All 14 checks pass, including replacement of the listener after each macro test. Reinstalled, gracefully closed the saved editor, reopened it, and invoked its Save & Apply action. All five saved shortcuts then delivered the expected text on the user's actual desktop, retaining the 100 ms character delay.
