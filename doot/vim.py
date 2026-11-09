"""doot's vim keys, as data. NORMAL is the start; digits aren't counts here
(1..5 run the phone's actions), and `/` types to search the actions. The
modes, which-key strip, help (?) and palette (Space Space) are Vyom's
(vyom/keys.py, vyom/modal.py; Vyom ADR 0008). Space groups follow Vayu's
shared letters (a add, d delete, o open outside, y copy); x (send) and
n (notify the phone: ring, ping) are doot's own.

An action "verb:arg" runs Plugin.v_<verb>(count, arg) in doot/__init__.py,
or Vyom's own (moved, nop...).
"""
from vyom.keys import Bind

B = Bind
GROUPS = {" x": "send", " n": "ring, ping"}
ACTION_KEYS = ["clipboard", "files", "ring", "browse", "ping"]   # 1..5, in the tiles' order

MAIN = [B(str(i + 1), f"act:{k}", d) for i, (k, d) in enumerate([
    ("clipboard", "Send this laptop's clipboard to the phone"),
    ("files", "Send a file to the phone (pick it from the list)"),
    ("ring", "Play the phone's ringtone (find it)"),
    ("browse", "Open the phone's storage in a file manager"),
    ("ping", "Send a ping to the phone"),
])]

FILES = [
    B("l", "activate", "Send the selected file to the phone"),
    B("h", "back", "Go back to the phone"),
    B("q", "back", "Go back to the phone (on the phone: close the panel)"),
    B("<BS>", "back", "", hidden=True),
]

LEADER = [
    B(" xc", "act:clipboard", "Send this laptop's clipboard to the phone"),
    B(" xf", "act:files", "Send a file to the phone (pick it from the list)"),
    B(" nr", "act:ring", "Play the phone's ringtone (find it)"),
    B(" np", "act:ping", "Send a ping to the phone"),
    B(" of", "act:browse", "Open the phone's storage in a file manager"),
    B(" aa", "pairing:accept", "Add the device that asks to pair (accept it; check the key on the phone)"),
    B(" dr", "pairing:reject", "Decline the waiting pairing request"),
    B(" dd", "unpair", "Remove the pairing with the phone (y confirms)"),
    B(" yb", "copy:battery", "Copy the phone's battery level"),
]

SECTIONS = [
    ("phone", "normal", "Normal mode, the phone (where it opens; `/` searches its actions)", MAIN),
    ("phone files", "normal", "Normal mode, the file list (Send a file)", FILES),
    ("phone leader", "normal", "Leader (Space)", LEADER),
]


def keys(view):
    return (FILES if view == "files" else MAIN) + LEADER
