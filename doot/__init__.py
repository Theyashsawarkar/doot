"""doot (दूत, "messenger"): your phone in Vyom, through KDE Connect.

The phone's battery, charging and mobile signal in the preview; its
actions as rows: send the clipboard, send a recent file, ring it to find
it, ping it, browse its storage, unpair. Pairing requests show at the
top with Accept / Reject, other known devices below.
"""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from vyom import Hint, Row, Section, ui, util
from vyom import Plugin as Base

# keybind: Vyom/phone | Enter | Run the selected phone action (send, ring, browse...)
# keybind: Vyom/phone | Backspace (empty search) | Go back from the file list

BUS = "org.kde.kdeconnect"
DEV = "org.kde.kdeconnect.device"
RECENT_DIRS = ["Downloads", "Desktop", "Pictures", "Documents", "Videos", "Music"]


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
    preview = True
    preview_width = 280
    live = 5
    hints = [Hint("Enter", "run"), Hint("Backspace", "back (files)")]
    empty_text = "No phone found: open KDE Connect on it (same network)"

    def __init__(self, vyom, conf):
        super().__init__(vyom, conf)
        self.view = "main"
        self.target = None

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
        if not daemon_running():
            return [Row("KDE Connect isn't running", "Enter starts it", icon="\U000f011c", color="red",
                        data={"kind": "start"})]
        devs = devices()
        rows = []
        for d in devs:
            if d["request"]:
                rows.append(Section(f"{d['name']} wants to pair"))
                key = prop(d["id"], "verificationKey") or ""
                rows.append(Row(f"Accept pairing with {d['name']}", f"verification key {key}: check the phone shows it",
                                icon="\U000f012c", color="green", data={"kind": "accept", "dev": d}))
                rows.append(Row(f"Reject pairing with {d['name']}", "", icon="\U000f0156", color="red",
                                data={"kind": "reject", "dev": d}))
        live = [d for d in devs if d["paired"] and d["reachable"]]
        for d in live:
            st = self.phone_state(d["id"])
            rows.append(Section(d["name"]))
            acts = [("clipboard", "Send clipboard", "puts this laptop's clipboard on the phone", "\U000f014c", "teal"),
                    ("files", "Send a file…", "from Downloads, Pictures, Documents…", "\U000f0552", "mauve"),
                    ("ring", "Ring", "find my phone", "\U000f009a", "peach"),
                    ("browse", "Browse files", "the phone's storage", "\U000f024b", "blue"),
                    ("ping", "Ping", "check the link", "\U000f04c5", "yellow"),
                    ("unpair", "Unpair", "forget this phone", "\U000f0156", "red")]
            for key, title, sub, icon, color in acts:
                if q and util.fuzzy(q, title) is None:
                    continue
                rows.append(Row(title, sub, icon=icon, color=color, data={"kind": key, "dev": d, "st": st}))
        others = [d for d in devs if d not in live and not d["request"]]
        if others:
            rows.append(Section("Other devices"))
            for d in others:
                if d["paired"]:
                    rows.append(Row(d["name"], "paired · not reachable now", icon="\U000f011c", color="gray",
                                    dim=True, data={"kind": "info", "dev": d}))
                else:
                    rows.append(Row(f"Pair with {d['name']}", "reachable, not paired", icon="\U000f0337",
                                    color="green", data={"kind": "pair", "dev": d}))
        return rows

    def file_rows(self, q):
        home = Path.home()
        files = []
        for sub in RECENT_DIRS:
            p = home / sub
            if p.is_dir():
                files += [f for f in p.iterdir() if f.is_file() and not f.name.startswith(".")]
        files = sorted(set(files), key=lambda f: f.stat().st_mtime, reverse=True)[:60]
        rows = [Section(f"Send to {self.target['name']}")]
        for f in files:
            if q and util.fuzzy(q, f.name) is None:
                continue
            age = int((time.time() - f.stat().st_mtime) / 3600)
            rows.append(Row(f.name, f"{str(f.parent).replace(str(home), '~')} · {util.human_bytes(f.stat().st_size)}",
                            icon="\U000f0214", color="mauve", meta=f"{age} h" if age < 48 else f"{age // 24} d",
                            data={"kind": "send", "path": str(f), "dev": self.target}))
        return rows

    def build_preview(self, row):
        d = row.data or {}
        dev = d.get("dev")
        if d.get("kind") == "send":
            return ui.vbox(ui.title(os.path.basename(d["path"])), ui.meta(d["path"]),
                           ui.body(f"Enter sends it to {dev['name']}."), spacing=8)
        if not dev:
            return None
        st = d.get("st") or (self.phone_state(dev["id"]) if dev["reachable"] else {})
        parts = [ui.hbox(ui.label("\U000f011c", "doot-big"),
                         ui.vbox(ui.title(dev["name"]),
                                 ui.meta("connected" if dev["reachable"] else "not reachable"), spacing=2), spacing=12)]
        if st.get("charge") is not None and st["charge"] >= 0:
            parts.append(ui.vbox(ui.meta(f"Battery {st['charge']}%" + (" · charging" if st.get("charging") else "")),
                                 ui.progress(st["charge"] / 100), spacing=4))
        facts = [("Type", dev["type"])]
        if st.get("net"):
            facts.append(("Network", f"{st['net']}" + (f" · {st['strength']}/4 bars" if st.get("strength") is not None
                                                        and st["strength"] >= 0 else "")))
        parts.append(ui.kv(facts))
        return ui.vbox(*parts, spacing=12)

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
            cli("-d", dev["id"], "--unpair")
            self.done(True, f"Unpaired {dev['name']}", "")
            self.refresh()
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

    def key(self, name, row, mods):
        if self.view == "files" and name in ("BackSpace", "Escape") and self.panel and not self.panel.query():
            self.view = "main"
            self.refresh()
            return True
        return False
