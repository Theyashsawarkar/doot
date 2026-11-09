"""doot (दूत, "messenger"): your phone in Vyom, through KDE Connect.

The phone at the top: its battery as a ring, charging, mobile signal and
network; its actions as numbered tiles (send the clipboard, send a recent
file, ring it to find it, browse its storage, ping it), a digit runs one;
Unpair in red, apart, and it asks first. Pairing requests and other
devices are the list below (Enter pairs); typing searches the actions.
KDE Connect doesn't publish its transfers' progress, so there is no
transfer list.
"""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from gi.repository import Gtk
from vyom import Hint, Row, Section, ui, util
from vyom import Plugin as Base

from . import vim

# KEYBINDS (generated from doot/vim.py by scripts/keybinds.py; don't edit by hand)
# keybind: Vyom/phone:normal | 1 | Send this laptop's clipboard to the phone
# keybind: Vyom/phone:normal | 2 | Send a file to the phone (pick it from the list)
# keybind: Vyom/phone:normal | 3 | Play the phone's ringtone (find it)
# keybind: Vyom/phone:normal | 4 | Open the phone's storage in a file manager
# keybind: Vyom/phone:normal | 5 | Send a ping to the phone
# keybind: Vyom/phone files:normal | l | Send the selected file to the phone
# keybind: Vyom/phone files:normal | h | Go back to the phone
# keybind: Vyom/phone files:normal | q | Go back to the phone (on the phone: close the panel)
# keybind: Vyom/phone leader:normal | Space x c | Send this laptop's clipboard to the phone
# keybind: Vyom/phone leader:normal | Space x f | Send a file to the phone (pick it from the list)
# keybind: Vyom/phone leader:normal | Space n r | Play the phone's ringtone (find it)
# keybind: Vyom/phone leader:normal | Space n p | Send a ping to the phone
# keybind: Vyom/phone leader:normal | Space o f | Open the phone's storage in a file manager
# keybind: Vyom/phone leader:normal | Space a a | Add the device that asks to pair (accept it; check the key on the phone)
# keybind: Vyom/phone leader:normal | Space d r | Decline the waiting pairing request
# keybind: Vyom/phone leader:normal | Space d d | Remove the pairing with the phone (y confirms)
# keybind: Vyom/phone leader:normal | Space y b | Copy the phone's battery level
# END KEYBINDS

BUS = "org.kde.kdeconnect"
DEV = "org.kde.kdeconnect.device"
RECENT_DIRS = ["Downloads", "Desktop", "Pictures", "Documents", "Videos", "Music"]
# The phone's actions, numbered in this order: (key, title, what it does, icon, colour)
ACTIONS = [("clipboard", "Send clipboard", "puts this laptop's clipboard on the phone", "\U000f014c", "teal"),
           ("files", "Send a file", "from Downloads, Pictures, Documents…", "\U000f0552", "mauve"),
           ("ring", "Ring it", "find my phone", "\U000f009a", "peach"),
           ("browse", "Browse files", "the phone's storage", "\U000f024b", "blue"),
           ("ping", "Ping", "check the link", "\U000f04c5", "yellow")]


def prop(dev, name, iface=DEV, suffix=""):
    code, out = util.run(["busctl", "--user", "get-property", BUS, f"/modules/kdeconnect/devices/{dev}{suffix}",
                          iface, name], timeout=4)
    if code or not out:
        return None
    kind, _, val = out.partition(" ")
    if kind == "b":
        return val == "true"
    if kind in ("i", "u", "x"):
        try:
            return int(val)
        except ValueError:
            return None
    return val.strip('"')


def daemon_running():
    code, out = util.run(["busctl", "--user", "call", "org.freedesktop.DBus", "/org/freedesktop/DBus",
                          "org.freedesktop.DBus", "NameHasOwner", "s", BUS])
    return out.strip() == "b true"


def devices():
    code, out = util.run(["busctl", "--user", "--json=short", "call", BUS, "/modules/kdeconnect",
                          "org.kde.kdeconnect.daemon", "devices", "bb", "false", "false"], timeout=8)
    try:
        ids = json.loads(out)["data"][0]
    except (ValueError, KeyError, IndexError):
        return []
    res = []
    for d in ids:
        res.append({"id": d, "name": prop(d, "name") or d, "paired": bool(prop(d, "isPaired")),
                    "reachable": bool(prop(d, "isReachable")), "request": bool(prop(d, "isPairRequestedByPeer")),
                    "type": prop(d, "type") or "phone"})
    return res


def cli(*args, timeout=20):
    return util.run(["kdeconnect-cli", *args], timeout=timeout)


class Plugin(Base):
    name, title, icon, color = "doot", "Phone", "\U000f011c", "green"
    placeholder = "Phone actions…"
    live = 5
    hints = [Hint("1..5", "action"), Hint("Enter", "run"), Hint("Space d d", "unpair")]
    file_hints = [Hint("Enter", "send"), Hint("h", "back")]
    modal = True                # vim keys (Vyom 0.7): NORMAL first, / searches the actions
    start_mode = "normal"
    vim_counts = False          # 1..5 are the phone's actions
    key_groups = vim.GROUPS
    empty_text = "No other devices nearby. Type to search the phone's actions."

    def __init__(self, vyom, conf):
        super().__init__(vyom, conf)
        self.view = "main"
        self.target = None
        self.phone = None        # the paired, reachable phone (search() finds it)
        self.state = {}
        self.running = True      # KDE Connect's daemon
        self.requests = []       # devices asking to pair (search() finds them)

    def opened(self, args):
        super().opened(args)
        self.view = "main"

    def phone_state(self, d):
        s = {"charge": prop(d, "charge", f"{DEV}.battery", "/battery"),
             "charging": prop(d, "isCharging", f"{DEV}.battery", "/battery"),
             "net": prop(d, "cellularNetworkType", f"{DEV}.connectivity_report", "/connectivity_report"),
             "strength": prop(d, "cellularNetworkStrength", f"{DEV}.connectivity_report", "/connectivity_report")}
        return s

    def search(self, q):
        if self.view == "files":
            return self.file_rows(q)
        self.running = daemon_running()
        if not self.running:
            self.phone, self.state = None, {}
            return [Row("KDE Connect isn't running", "Enter starts it", icon="\U000f011c", color="red",
                        data={"kind": "start"})]
        devs = devices()
        self.requests = [d for d in devs if d["request"]]
        rows = []
        for d in devs:
            if d["request"]:
                rows.append(Section(f"{d['name']} wants to pair", note="check the key matches the phone's"))
                key = prop(d["id"], "verificationKey") or ""
                rows.append(Row(f"Accept pairing with {d['name']}", f"verification key {key}: check the phone shows it",
                                icon="\U000f012c", color="green", data={"kind": "accept", "dev": d}))
                rows.append(Row(f"Reject pairing with {d['name']}", "", icon="\U000f0156", color="red",
                                data={"kind": "reject", "dev": d}))
        live = [d for d in devs if d["paired"] and d["reachable"]]
        self.phone = live[0] if live else None
        self.state = self.phone_state(self.phone["id"]) if self.phone else {}
        if q:   # typing searches the actions (Enter runs the first)
            for d in live:
                acts = [a for a in ACTIONS + [("unpair", "Unpair", "forget this phone (asks first)", "\U000f0337", "red")]
                        if util.fuzzy(q, a[1]) is not None]
                if acts:
                    rows.append(Section(d["name"], len(acts)))
                for n, (key, title, sub, icon, color) in enumerate(acts):
                    rows.append(Row(title, sub, icon=icon, color=color, data={"kind": key, "dev": d}))
        others = [d for d in devs if d not in live and not d["request"]
                  and (not q or util.fuzzy(q, d["name"]) is not None)]
        if others:
            rows.append(Section("Other devices", len(others), "Enter pairs"))
            for d in others:
                icon = "\U000f04f6" if d["type"] == "tablet" else "\U000f0322" if d["type"] in ("laptop", "desktop") \
                    else "\U000f011c"
                if d["paired"]:
                    rows.append(Row(d["name"], "paired · not reachable now", icon=icon, color="gray",
                                    dim=True, data={"kind": "info", "dev": d}))
                else:
                    rows.append(Row(d["name"], "reachable · Enter pairs", icon=icon, color="green",
                                    data={"kind": "pair", "dev": d}))
        return rows

    def file_rows(self, q):
        home = Path.home()
        files = []
        for sub in RECENT_DIRS:
            p = home / sub
            if p.is_dir():
                files += [f for f in p.iterdir() if f.is_file() and not f.name.startswith(".")]
        files = sorted(set(files), key=lambda f: f.stat().st_mtime, reverse=True)[:60]
        rows = [Section(f"Send to {self.target['name']}", note="h goes back")]
        for f in files:
            if q and util.fuzzy(q, f.name) is None:
                continue
            age = int((time.time() - f.stat().st_mtime) / 3600)
            rows.append(Row(f.name, f"{str(f.parent).replace(str(home), '~')} · {util.human_bytes(f.stat().st_size)}",
                            icon="\U000f0214", color="mauve", meta=f"{age} h" if age < 48 else f"{age // 24} d",
                            data={"kind": "send", "path": str(f), "dev": self.target}))
        return rows

    # ------------------------------------------------------------ the strip
    def build_strip(self):
        """The phone as the hero (battery ring, name, Connected, signal,
        network, charging) and its actions as numbered tiles."""
        if not self.running:
            return None
        d, st = self.phone, self.state
        if d is None:
            txt = ui.vbox(ui.hbox(ui.label("No phone connected", "hero-title"),
                                  ui.chip("Not connected", "gray", "\U000f0156"), spacing=8),
                          ui.label("Open KDE Connect on the phone, on the same network as this laptop.",
                                   "hero-sub", xalign=0), spacing=6)
            txt.set_hexpand(True)
            return ui.hero(ui.ring(0, "gray", 64, 6, ui.label("\U000f011c", "glyph")), txt, color="gray")
        charge = st.get("charge")
        charge = charge if isinstance(charge, int) and charge >= 0 else None
        ring_color = "gray" if charge is None else "red" if charge < 15 else "yellow" if charge < 30 else "green"
        ring = ui.ring((charge or 0) / 100, ring_color, 70, 6,
                       ui.label(f"{charge}%" if charge is not None else "?", "ring-text"))
        specs = []
        strength = st.get("strength")
        if st.get("net"):
            specs.append((st["net"], "gray", ""))
        if st.get("charging"):
            specs.append(("Charging", "yellow", "\U000f0084"))
        chips = ui.hbox(spacing=6)
        if isinstance(strength, int) and strength >= 0:
            words = ["No signal", "Weak", "Fair", "Good", "Strong"]
            sig = ui.hbox(ui.bars(min(strength, 4), "green" if strength >= 3 else "yellow" if strength >= 2 else "red", 12),
                          ui.label(words[min(strength, 4)]), spacing=6, cls="chip")
            sig.add_css_class("c-gray")
            sig.set_valign(Gtk.Align.CENTER)
            chips.append(sig)
        for sp in specs:
            chips.append(ui.chip(*sp))
        txt = ui.vbox(ui.hbox(ui.label(d["name"], "hero-title"), ui.chip("Connected", "green", "\U000f012c"), spacing=8),
                      chips, spacing=7)
        txt.set_hexpand(True)
        txt.set_valign(Gtk.Align.CENTER)
        unpair = ui.button("Unpair", self.unpair, "danger", "\U000f0337", "Space d d")
        unpair.set_valign(Gtk.Align.CENTER)
        hero = ui.hero(ring, txt, unpair, color="green")
        if self.view == "files":
            return hero
        grid = Gtk.Grid(column_spacing=8, column_homogeneous=True)
        grid.add_css_class("doot-tiles")
        for n, (key, title, _sub, icon, color) in enumerate(ACTIONS):
            b = Gtk.Button()
            b.add_css_class("doot-tile")
            b.set_can_focus(False)
            b.set_child(ui.hbox(ui.tile(icon, color),
                                ui.vbox(ui.label(title, "doot-tile-title", xalign=0),
                                        ui.hbox(ui.keycap(str(n + 1))), spacing=3),
                                spacing=10))
            b.set_tooltip_text(f"{_sub} ({n + 1})")
            b.connect("clicked", lambda _b, k=key: self.run_action(k))
            grid.attach(b, n, 0, 1, 1)
        return ui.vbox(hero, ui.section("Do", note="a number runs it"), grid, spacing=8)

    def run_action(self, key):
        if self.phone is None:
            return
        if self.activate(Row(key, data={"kind": key, "dev": self.phone}), set()):
            self.close()

    def unpair(self):
        """Asks first (y unpairs, any other key keeps it): pairing again needs the phone."""
        d = self.phone
        if d is None:
            self.set_status("no phone connected", "bad")
            return

        def go():
            cli("-d", d["id"], "--unpair")
            self.done(True, f"Unpaired {d['name']}", "")
            self.refresh()
        self.confirm(f"Unpair {d['name']}? Pairing again needs the phone.", go)

    # ------------------------------------------------------------ actions
    def done(self, ok, msg_ok, msg_fail):
        util.notify("Phone", msg_ok if ok else msg_fail, icon="smartphone", urgency=None if ok else "critical")

    def activate(self, row, mods):
        d = row.data or {}
        kind, dev = d.get("kind"), d.get("dev")
        if kind == "start":
            util.spawn(["systemctl", "--user", "start", "kdeconnect.service"])
            return False
        if kind == "files":
            self.target, self.view = dev, "files"
            self.panel.entry.set_text("")
            self.panel.refresh_hints()
            self.refresh()
            return False
        if kind == "send":
            self.set_status(f"sending {os.path.basename(d['path'])}…")
            self.background(lambda: cli("-d", dev["id"], "--share", d["path"], timeout=60),
                            lambda r: self.done(isinstance(r, tuple) and r[0] == 0,
                                                f"Sent {os.path.basename(d['path'])} to {dev['name']}",
                                                f"Couldn't send {os.path.basename(d['path'])}"))
            return True
        if kind == "clipboard":
            text = util.run(["wl-paste", "--no-newline"])[1]
            if not text:
                self.set_status("the clipboard is empty (or not text)")
                return False
            r = util.run(["busctl", "--user", "call", BUS, f"/modules/kdeconnect/devices/{dev['id']}/clipboard",
                          f"{DEV}.clipboard", "sendClipboard"])
            self.done(r[0] == 0, f"Sent the clipboard to {dev['name']}", "Couldn't send the clipboard")
            return True
        if kind == "ring":
            r = cli("-d", dev["id"], "--ring")
            self.done(r[0] == 0, f"Ringing {dev['name']}", f"Couldn't ring {dev['name']}")
            return True
        if kind == "ping":
            r = cli("-d", dev["id"], "--ping-msg", f"Ping from {os.uname().nodename}")
            self.done(r[0] == 0, f"Pinged {dev['name']}", f"Couldn't ping {dev['name']}")
            return True
        if kind == "browse":
            self.background(lambda: self.browse(dev))
            return True
        if kind == "unpair":
            self.unpair()
            return False
        if kind == "pair":
            cli("-d", dev["id"], "--pair")
            self.done(True, f"Pair requested: accept it on {dev['name']}", "")
            return False
        if kind in ("accept", "reject"):
            util.run(["busctl", "--user", "call", BUS, f"/modules/kdeconnect/devices/{dev['id']}", DEV,
                      "acceptPairing" if kind == "accept" else "cancelPairing"])
            self.refresh()
            return False
        return False

    def browse(self, dev):
        cli("-d", dev["id"], "--mount")
        mount = ""
        for _ in range(20):  # the mount appears asynchronously
            mount = cli("-d", dev["id"], "--get-mount-point")[1].strip()
            if mount and os.path.ismount(mount):
                break
            time.sleep(0.5)
        if not (mount and os.path.ismount(mount)):
            util.notify("Phone", f"Couldn't open {dev['name']}'s storage: allow storage access in KDE Connect on it",
                        urgency="critical")
            return
        # Android never lists the mount root; open the folder it exposes.
        code, out = util.run(["busctl", "--user", "--json=short", "call", BUS,
                              f"/modules/kdeconnect/devices/{dev['id']}/sftp", f"{DEV}.sftp", "getDirectories"])
        target = mount
        try:
            dirs = [p for p in json.loads(out)["data"][0] if os.path.isdir(p)]
            target = dirs[0] if dirs else mount
        except (ValueError, KeyError, IndexError):
            pass
        cmd = self.conf.get("browse_command")
        if cmd:
            util.spawn(cmd.replace("{path}", target))
        elif shutil.which("yazi") and shutil.which("kitty"):
            util.spawn(["kitty", "--title", f"{dev['name']} files", "-e", "yazi", target])
        else:
            util.spawn(["xdg-open", target])

    # ------------------------------------------------------------ vim keys
    def keys(self, tab):
        return vim.keys(self.view)

    def tab_hints(self):
        return self.file_hints if self.view == "files" else self.hints

    def escape(self):
        if self.view == "files" and not (self.panel and self.panel.query()):
            self.v_back(1, "")
            return True
        return False

    def v_back(self, _n, _a):
        if self.view != "files":
            self.close()
            return
        self.view = "main"
        if self.panel:
            self.panel.entry.set_text("")
            self.panel.refresh_hints()
        self.refresh()

    def v_act(self, _n, key):
        if self.phone is None:
            self.set_status("no phone connected", "bad")
            return
        self.run_action(key)
        if self.panel:
            self.panel.refresh_hints()

    def v_pairing(self, _n, what):
        if not self.requests:
            self.set_status("no device is asking to pair", "bad")
            return
        self.activate(Row("", data={"kind": what, "dev": self.requests[0]}), set())

    def v_unpair(self, _n, _a):
        self.unpair()

    def v_copy(self, _n, _what):
        charge = self.state.get("charge")
        if self.phone is None or not isinstance(charge, int) or charge < 0:
            self.set_status("no battery level to copy", "bad")
            return
        text = f"{self.phone['name']}: {charge}%" + (" (charging)" if self.state.get("charging") else "")
        util.copy(text)
        self.set_status(f"copied {text}", "ok")

    def key(self, name, row, mods):
        # Backspace in an empty search goes back from the file list, in both modes.
        if self.view == "files" and name == "BackSpace" and self.panel is not None and not self.panel.query():
            self.v_back(1, "")
            return True
        return False
