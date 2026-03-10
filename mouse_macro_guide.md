# Guide: Using Your Mouse for Macros

The current project uses **`xbindkeys`** to trigger commands with various input events. Your Logitech G604 mouse has several extra buttons that can be mapped to macros via X11 button numbers.

## 1. Identify Your Mouse Button Numbers

To know which button translates to what code, follow these steps:

1.  Find the Device ID of your mouse:
    ```bash
    xinput list
    ```
2.  Test the buttons (replace `<id>` with your mouse's ID):
    ```bash
    xinput test <id>
    ```
3.  Press the mouse buttons. You should see output like:
    ```bash
    button press   8
    button release 8
    ```
    -   `b:8`: Typically the "Back" button (BTN_SIDE).
    -   `b:9`: Typically the "Forward" button (BTN_EXTRA).

## 2. Configure Macros in `~/.xbindkeysrc`

Open your `~/.xbindkeysrc` file and add the following template:

```bash
# Example 1: Use Mouse Button 8 to copy
"/usr/bin/xdotool key --clearmodifiers ctrl+c"
  b:8

# Example 2: Use Mouse Button 9 to paste
"/usr/bin/xdotool key --clearmodifiers ctrl+v"
  b:9

# Example 3: Send a desktop notification (useful for testing)
"/usr/bin/notify-send 'Macro Triggered' 'Button 8 pressed!'"
  b:8
```

> [!TIP]
> Use `release+` if you want the action to trigger when the button is released instead of pressed. This can help prevent conflicts with other actions.

## 3. Apply the Changes

To apply your changes, you need to restart the `xbindkeys` process:

```bash
# Kill any running instances
pkill -x xbindkeys

# Start xbindkeys in the background
xbindkeys &
```

For debugging, you can run `xbindkeys -n -v` to see real-time logs when buttons are pressed.
