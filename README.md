# doot

**doot** (दूत, "messenger") — Your phone, through KDE Connect. A tool for [Vyom](https://github.com/Theyashsawarkar/vyom), the keyboard-driven panels of [Vayu](https://github.com/Theyashsawarkar/vayu); in Vayu it replaces phone-picker.py.

> Your phone through KDE Connect: battery and signal at a glance, send files and the clipboard, ring, ping, browse, pair.

## Features

- The phone's **battery, charging and mobile signal** at a glance.
- Its actions as rows: send the clipboard, **send a recent file** (from Downloads, Pictures, Documents…), ring it to find it, ping it, browse its storage, unpair.
- Pairing requests at the top with Accept / Reject and the verification key; other known devices below (pair the reachable ones).

## Keys

| Key | Action |
|---|---|
| `Enter` | Run the selected phone action (send, ring, browse...) |
| `Backspace (empty search)` | Go back from the file list |
| `Esc` | close |

Every Vyom panel also has: `Up`/`Down` (or `Ctrl+K`/`Ctrl+J`) to move, `Page Up`/`Page Down`, `Tab` to switch to the next tool.

## Requirements

- [Vyom](https://github.com/Theyashsawarkar/vyom) 0.2 or newer (Python 3.11+, GTK 4, gtk4-layer-shell, a layer-shell compositor)
- `kdeconnect-cli`, `busctl`
- optional: wl-paste (send clipboard)
- optional: yazi + kitty (browse)

## Install

```sh
git clone https://github.com/Theyashsawarkar/doot ~/.local/share/vyom/plugins/doot
vyom reload        # or log out and in
vyom doot         # open it (again: close it)
```

Bind it to a key, e.g. in sway:

```
bindsym $mod+<key> exec vyom doot
```

Update: `git -C ~/.local/share/vyom/plugins/doot pull && vyom reload`. `vyom list` shows every installed tool and why one would be skipped.

## Configuration

In `~/.config/vyom/config.toml` (all optional):

```toml
[plugin.doot]
# browse_command: how to open the phone's storage (`{path}` is replaced) (default: yazi in kitty, else xdg-open)
```

## License

MIT.
