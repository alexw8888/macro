#!/usr/bin/env python3
"""Native Linux editor for five global text macros."""

import subprocess
import sys

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gio, Gtk
except (ImportError, ValueError):
    print("Install the UI dependencies: sudo apt install python3-gi gir1.2-gtk-3.0", file=sys.stderr)
    sys.exit(1)

from macro_core import MacroError, apply_settings, load_settings


class MacroWindow(Gtk.ApplicationWindow):
    def __init__(self, app, data):
        super().__init__(application=app, title="Text Macros")
        self.set_default_size(800, 860)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.data = data
        self.dirty = False
        self.editors = []
        self.connect("delete-event", self.on_close)

        header = Gtk.HeaderBar(title="Text Macros", subtitle="Five shortcuts. Your words.")
        header.set_show_close_button(True)
        self.set_titlebar(header)
        self.save_button = Gtk.Button(label="Save & Apply")
        self.save_button.get_style_context().add_class("suggested-action")
        self.save_button.set_tooltip_text("Save all five slots and enable their global shortcuts (Ctrl+S)")
        self.save_button.connect("clicked", self.on_save)
        header.pack_end(self.save_button)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_border_width(16)
        self.add(root)
        intro = Gtk.Label(xalign=0)
        intro.set_markup('<span size="large" weight="bold">Your text, one shortcut away</span>')
        root.pack_start(intro, False, False, 0)
        help_text = Gtk.Label(
            label="Edit a slot, save, then press its shortcut in any text field.\n"
                  "On keyboards with media keys, hold Fn to access F1–F5.", xalign=0,
        )
        help_text.set_line_wrap(True)
        root.pack_start(help_text, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        root.pack_start(scroll, True, True, 0)
        slots = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scroll.add(slots)
        for index, slot in enumerate(data["slots"], 1):
            frame = Gtk.Frame()
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            card.set_border_width(8)
            frame.add(card)
            top = Gtk.Box(spacing=12)
            title = Gtk.Label(xalign=0)
            title.set_markup(f'<b>Macro {index}</b>   <tt>Ctrl + F{index}</tt>')
            top.pack_start(title, True, True, 0)
            enter = Gtk.CheckButton(label="Press Enter after typing")
            enter.set_active(slot["press_enter"])
            enter.set_tooltip_text("Also sends Enter, which can submit a message or command")
            top.pack_end(enter, False, False, 0)
            card.pack_start(top, False, False, 0)
            text_scroll = Gtk.ScrolledWindow()
            text_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            text_scroll.set_min_content_height(54)
            text_scroll.set_shadow_type(Gtk.ShadowType.IN)
            text = Gtk.TextView()
            text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            text.set_left_margin(10)
            text.set_right_margin(10)
            text.set_top_margin(8)
            text.set_bottom_margin(8)
            text.set_accepts_tab(False)
            text.get_accessible().set_name(f"Macro {index} text, Ctrl+F{index}")
            text.set_tooltip_text(f"Text inserted by Ctrl+F{index}. Leave empty to disable this slot.")
            text.get_buffer().set_text(slot["text"])
            text.get_buffer().connect("changed", self.on_changed)
            enter.connect("toggled", self.on_changed)
            text_scroll.add(text)
            card.pack_start(text_scroll, True, True, 0)
            slots.pack_start(frame, False, False, 0)
            self.editors.append((text, enter))

        self.status = Gtk.Label(label="Ready to edit. Save & Apply enables your shortcuts.", xalign=0)
        self.status.set_line_wrap(True)
        self.status.set_selectable(True)
        root.pack_start(self.status, False, False, 0)
        footer = Gtk.Label(label="X11 session • Empty slots do nothing • Shortcuts stay active after closing", xalign=0)
        footer.get_style_context().add_class("dim-label")
        footer.set_line_wrap(True)
        root.pack_start(footer, False, False, 0)
        self.connect("key-press-event", self.on_key)
        self.show_all()

    def on_changed(self, *_):
        self.dirty = True
        self.set_title("Text Macros — Unsaved changes")
        self.status.set_text("Unsaved changes — click Save & Apply to update your shortcuts.")

    def collect(self):
        slots = []
        for text, enter in self.editors:
            buffer = text.get_buffer()
            slots.append({
                "text": buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True),
                "press_enter": enter.get_active(),
            })
        return {"version": 1, "slots": slots}

    def on_save(self, *_):
        try:
            data = self.collect()
            apply_settings(data)
        except (MacroError, OSError, subprocess.SubprocessError) as error:
            self.status.set_text(f"Could not apply shortcuts: {error}")
            return False
        self.data = data
        self.dirty = False
        self.set_title("Text Macros")
        self.status.set_text("Saved. Ctrl+F1–F5 are ready — try them in your text editor.")
        return True

    def on_key(self, _widget, event):
        from gi.repository import Gdk
        if event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_s, Gdk.KEY_S):
            self.on_save()
            return True
        return False

    def on_close(self, *_):
        if not self.dirty:
            return False
        dialog = Gtk.MessageDialog(
            transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
            text="Save your macro changes?",
        )
        dialog.format_secondary_text("Your shortcuts will keep using the last saved text until you apply these changes.")
        dialog.add_buttons("Keep Editing", Gtk.ResponseType.CANCEL, "Discard", Gtk.ResponseType.REJECT, "Save & Apply", Gtk.ResponseType.ACCEPT)
        dialog.set_default_response(Gtk.ResponseType.ACCEPT)
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.ACCEPT:
            return not self.on_save()
        return response != Gtk.ResponseType.REJECT


class MacroApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="io.github.textmacros.Editor", flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        window = self.get_active_window()
        if window:
            window.present()
            return
        try:
            data = load_settings()
        except (MacroError, OSError) as error:
            dialog = Gtk.MessageDialog(modal=True, message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE, text="Cannot open your macro settings")
            dialog.format_secondary_text(str(error))
            dialog.run()
            dialog.destroy()
            return
        MacroWindow(self, data)


if __name__ == "__main__":
    sys.exit(MacroApp().run(sys.argv))
