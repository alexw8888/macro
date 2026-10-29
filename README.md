# Text Macros for Linux

A native GTK app with **five editable text slots**, mapped to **Ctrl+F1 through
Ctrl+F5**. Each slot supports multiline text and an optional **Press Enter after
typing** setting. Empty slots do nothing. If your keyboard uses the function row
for media controls, hold **Fn** as well, or turn on Fn Lock; Linux receives the
resulting Ctrl+F1–F5 shortcut.

## Install and open the app

On Ubuntu/Debian, in an **X11/Xorg** desktop session:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 xbindkeys xdotool
bash install.sh
```

Open **Text Macros** from your application menu. You can also run the editor
directly from this checkout:

```bash
/usr/bin/python3 macro_app.py
```

1. Edit the five text boxes labeled **Ctrl+F1**, **Ctrl+F2**, **Ctrl+F3**,
   **Ctrl+F4**, and **Ctrl+F5**.
2. Optionally enable **Press Enter after typing** for a slot. This can submit a
   message or command in the focused application. It is off by default for new slots.
3. Click **Save & Apply** (or press **Ctrl+S**).
4. Focus the destination text field, then press its shortcut.

The shortcuts continue working after closing the editor. Installation adds login
startup for saved shortcuts. Running directly from the checkout also works, but
keep the checkout at the same location and use the installer for login startup.
The editor asks before discarding unsaved changes. If a desktop or another app
already uses a shortcut, remove that conflicting binding in its keyboard settings.

### Settings and existing shortcuts

- Text is stored locally in `~/.config/text-macros/macros.json` (respects
  `XDG_CONFIG_HOME`), in a file readable only by your user. It is plain text.
- The existing encoded Ctrl+F1 macro is imported on first use, including its
  Enter setting. Changes are applied only when you click **Save & Apply**.
- The app manages Ctrl+F1–F5 in `~/.xbindkeysrc`, preserving mouse bindings and
  other shortcuts. The first original file is backed up to
  `~/.xbindkeysrc.before-text-macros`.
- Installation copies the app into `~/.local/share/text-macros` and adds
  `~/.local/share/applications/text-macros.desktop` and
  `~/.config/autostart/text-macros.desktop`. These respect `XDG_DATA_HOME` and
  `XDG_CONFIG_HOME`. Re-run `bash install.sh` after updating the checkout.
- This backend requires **X11**, not Wayland. Choose **Ubuntu on Xorg** at login.
  A `~/.xbindkeysrc.scm` configuration takes priority over the text file and must
  be moved aside before using the app.
- The old `deploy.sh` replaces `~/.xbindkeysrc`. If you use it later, open the app
  and click **Save & Apply** again to restore the five shortcuts.

To remove the app, delete the installed application directory, menu entry and
autostart file listed above. Remove the marked `text-macros` section from
`~/.xbindkeysrc` and reload xbindkeys (`pkill -HUP -x xbindkeys`, then move the
mouse). Alternatively, restore `~/.xbindkeysrc.before-text-macros` if you have not
made other shortcut changes since installing. Your saved text can be kept or
removed separately by deleting `~/.config/text-macros`.

### Development checks

```bash
python3 -m unittest discover -s tests -v
# Also exercises the real GTK editor and all five shortcuts on an isolated X11 display:
xvfb-run -a /usr/bin/python3 -m unittest discover -s tests -v
```

## Original mouse shortcut setup

### Logitech G604 on Ubuntu (X11): Macros with `xbindkeys` + `xdotool`

This README shows how to configure your Logitech **G604** extra buttons to run macros on **Ubuntu (X11)** using **xbindkeys** and **xdotool**, plus how to inspect button/key codes with **evtest** and **xinput**. It also includes autostart and troubleshooting tips.

> **Wayland vs X11**
> 
> -   These steps are for **X11** (a.k.a. Xorg). On Wayland, `xbindkeys`/`xdotool` are limited. If you prefer Wayland, use **input-remapper** and/or **ydotool** instead (notes at the end).
> -   Check your session: `echo $XDG_SESSION_TYPE` → should print `x11`. To switch at login: log out → ⚙️ (gear) → **Ubuntu on Xorg** → log in.

---

## 1) Install required tools

```bash
sudo apt updatesudo apt install -y xbindkeys xdotool evtest xinput libnotify-bin
```

Optional (handy for window matching / debugging):

```bash
​sudo apt install -y wmctrl
```

---

## 2) Identify your G604 button events

### A) Using `evtest` (kernel level, very detailed)

1.  List devices:
    
    ```bash
    sudo evtest
    ```
    
2.  Note the entries for your G604 (it often appears multiple times: mouse, keyboard, consumer control).
3.  Run against the likely candidate (replace N with the correct event number, e.g. `/dev/input/event3`):
    
    ```bash
    sudo evtest /dev/input/eventN
    ```
    
4.  Press the G604 buttons and observe lines like:
    
    ```
    type 1 (EV_KEY), code 192 (KEY_F22), value 1   # presstype 1 (EV_KEY), code 192 (KEY_F22), value 0   # releasetype 1 (EV_KEY), code 275 (BTN_SIDE), value 1  # press
    ```
    
    -   **KEY_F22/F23/F24** are great for macros (rarely used by apps).
    -   **BTN_SIDE/BTN_EXTRA** are mouse buttons (you can bind them as `b:8`, `b:9` via `xinput`, see below).

### B) Using `xinput` (X11-level; great for button numbers)

1.  List X input devices:
    
    ```bash
    xinput list
    ```
    
2.  Find your G604 device `id=` (e.g. `id=12`), then:
    
    ```bash
    xinput test <id>
    ```
    
3.  Press the side/extra buttons; you’ll see:
    
    ```
    button press   8button release 8button press   9
    ```
    
    Use these as `b:8`, `b:9` in xbindkeys bindings.

### C) Confirm what X11 sees for function keys

```bash
xev -event keyboard
```

Focus the white window and press the G604 “F22/23/24” buttons — you should see `keycode` and `keysym` reported.

---

## 3) Create a minimal `xbindkeys` config

Create a default file (once):

```bash
xbindkeys --defaults > ~/.xbindkeysrc
```

### Example 1 — Bind by **keysym** (F22/F23/F24)

```bash
cat > ~/.xbindkeysrc <<'EOF'# F22 → paste (Ctrl+V)"/usr/bin/xdotool key --clearmodifiers ctrl+v"  F22# F23 → type text"/usr/bin/xdotool type --clearmodifiers 'Hello from G604 (F23)!'"  F23# F24 → Ctrl+Shift+T"/usr/bin/xdotool key --clearmodifiers ctrl+shift+t"  F24EOF
```

### Example 2 — Bind by **keycode** (force override)

Find exact keycode with `xbindkeys -k` (press the target key). Suppose:

-   F22 → `m:0x0 + c:192`
-   F23 → `m:0x0 + c:193`
-   F24 → `m:0x0 + c:194`

```bash
cat > ~/.xbindkeysrc <<'EOF'# Force-bind by keycode to avoid desktop defaults"/usr/bin/bash -lc 'sleep 0.08; /usr/bin/xdotool key --clearmodifiers ctrl+v'"  release + m:0x0 + c:192"/usr/bin/bash -lc 'sleep 0.08; /usr/bin/xdotool type --clearmodifiers "Hello from G604 (F23)!"'"  release + m:0x0 + c:193"/usr/bin/bash -lc 'sleep 0.08; /usr/bin/xdotool key --clearmodifiers ctrl+shift+t'"  release + m:0x0 + c:194EOF
```

**Notes**

-   `release +` triggers after you let go, avoiding races with the mouse’s onboard events.
-   `sleep 0.08` (80ms) gives time for any device-generated keystrokes to finish.
-   `--clearmodifiers` neutralizes stuck Shift/Ctrl/Alt from the originating event.

### Example 3 — Bind **mouse buttons** (`BTN_SIDE/EXTRA` → `b:8`, `b:9`)

```bash
cat >> ~/.xbindkeysrc <<'EOF'# Mouse button 8 → copy"/usr/bin/xdotool key --clearmodifiers ctrl+c"  b:8# Mouse button 9 → paste"/usr/bin/xdotool key --clearmodifiers ctrl+v"  b:9EOF
```

---

## 4) Run and test

Kill any existing instance and run in verbose mode for debugging:

```bash
pkill -x xbindkeys 2>/dev/nullxbindkeys -n -v
```

Press your G604 buttons:

-   You should see “Start program with fork+exec call” traces.
-   Put focus in a text editor to test `type` actions.

If it works, start it normally:

```bash
pkill -x xbindkeysxbindkeys &
```

---

## 5) Start `xbindkeys` **automatically** on login

### Option A — Startup Applications (GUI)

1.  Open **Startup Applications** (install with `sudo apt install gnome-startup-applications` if missing).
2.  **Add** → Name: `xbindkeys` → Command: `/usr/bin/xbindkeys`.

### Option B — systemd user service (robust)

Create `~/.config/systemd/user/xbindkeys.service`:

```ini
[Unit]Description=Start xbindkeys[Service]ExecStart=/usr/bin/xbindkeys -nRestart=on-failure[Install]WantedBy=default.target
```

Enable + start:

```bash
systemctl --user enable xbindkeys.servicesystemctl --user start xbindkeys.servicesystemctl --user status xbindkeys
```

### Option C — `~/.xsessionrc` (X11 sessions)

```bash
echo 'xbindkeys &' >> ~/.xsessionrc
```

---

## 6) Troubleshooting

-   **Nothing happens**
    
    -   Ensure X11: `echo $XDG_SESSION_TYPE` → must be `x11`.
    -   Validate config syntax: two lines per binding (command then key).
    -   Run verbose: `pkill -x xbindkeys; xbindkeys -n -v` and watch logs.
    -   Confirm keys are seen: `xbindkeys -k`, `xev -event keyboard`, `xinput test <id>`.
-   **Command runs but no text appears**
    
    -   Use `release +` and add a small `sleep` before `xdotool`.
    -   Add `--clearmodifiers` to neutralize Shift/Ctrl/Alt.
    -   Try sending a shortcut instead of `type`: `xdotool key ctrl+v`.
-   **Double actions / conflicts**
    
    -   Desktop shortcut grabs the same key. Clear it in **Settings → Keyboard Shortcuts**.
    -   Bind by **keycode** (`m:0x0 + c:###`) instead of `Fxx` names.
-   **Only some apps respond**
    
    -   Some apps block synthetic input. Try a different target app, or use app-specific scripts.
    -   For per-app logic, use `wmctrl` with conditionals in a wrapper script.
-   **Device emits extra characters (onboard macro)**
    
    -   Prefer mapping the button to a **clean function key** (F13–F24) in firmware/Windows G HUB first.
    -   Or on Linux, use **input-remapper** to convert the raw button to a clean key before it reaches apps.

---

## 7) Wayland-friendly alternatives (if you go back to Wayland)

-   **input-remapper (GUI)**: map your G604 buttons to function keys or key combos at the device level.
    
    ```bash
    sudo apt install input-remapperinput-remapper-gtk
    ```
    
-   **ydotool**: system-wide input injector (needs daemon + `uinput` setup).
    
    ```bash
    sudo apt install ydotoolsudo ydotoold &# (or set up udev rule & add your user to "input" group to run without sudo)
    ```
    

---

## 8) Quick reference snippets

Print a notification to verify binding:

```bash
"/usr/bin/notify-send 'xbindkeys' 'F22 pressed'"  F22
```

Send Ctrl+V reliably:

```bash
"/usr/bin/xdotool key --clearmodifiers ctrl+v"  release + m:0x0 + c:192
```

Type text with a short delay:

```bash
"/usr/bin/bash -lc 'sleep 0.08; /usr/bin/xdotool type --clearmodifiers "Hello!"'"  F23
```

Open a terminal:

```bash
"/usr/bin/gnome-terminal"  F24
```

---

## 9) Logitech G Pro X: side buttons → switch desktops

The G Pro X side buttons are programmed **in the mouse firmware** to send `Ctrl+Left` / `Ctrl+Right` (that is what switches Spaces on macOS). They emit key events, not mouse buttons, so they can never match a `b:8`/`b:9` binding in `xbindkeys` — the device simply never sends those.

Instead they are remapped per-device with **input-remapper**, so the keyboard's own `Ctrl+Left`/`Ctrl+Right` keeps working normally. See [input-remapper/](input-remapper):

- `presets/Logitech PRO X/desktop-switch.json`
  - the mouse's own `Ctrl` → `disable` (swallowed, so it is not held down while switching)
  - `Left` → `Super+Alt+Left` (GNOME `switch-to-workspace-left`)
  - `Right` → `Super+Alt+Right` (GNOME `switch-to-workspace-right`)
- `config.json` — autoload entry, so the preset is applied whenever the mouse connects

Deploy it (re-run after editing a preset):

```bash
sudo apt install input-remapper
./deploy_input_remapper.sh
```

Undo it again (stops the injection and removes the preset plus its autoload entry, leaving the rest of `config.json` untouched):

```bash
./deploy_input_remapper.sh --revert
```

Tweak or turn it off in the GUI (`input-remapper-gtk`) or with:

```bash
input-remapper-control --command stop --device "Logitech PRO X"
```

Set `INPUT_REMAPPER_CONFIG_DIR` to deploy to a directory other than `~/.config/input-remapper-2`.

---

**That’s it!** Your G604 should now trigger macros on Ubuntu (X11) with `xbindkeys` + `xdotool`.  
If you want, paste your actual keycodes and the actions you want — I’ll generate a tailor-made `~/.xbindkeysrc` for you.
