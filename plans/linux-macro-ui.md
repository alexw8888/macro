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
