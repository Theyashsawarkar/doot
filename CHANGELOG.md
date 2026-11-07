# Changelog

Newest first. Releases are tags (`vX.Y.Z`).

## v0.2.0 -- 2026-11-07

- **A new look** (Vyom 0.6): the phone at the top, its battery as a ring,
  "Connected" in green, signal bars with a word, the network and charging.
- **Actions as numbered tiles** (send clipboard, send a file, ring, browse,
  ping): with the search box empty, `1`..`5` runs one; typing still searches
  them.
- **Unpair is red, apart, and asks first**: `Ctrl+U` (or its button) once
  shows a red note, a second time within 5 seconds unpairs. It used to unpair
  at once.
- Other devices say "Enter pairs"; the preview pane is gone (everything it
  showed is at the top now).
- No transfer list: KDE Connect doesn't publish its transfers' progress.
- Needs Vyom 0.6.0.

- Every corner is rounded: the website's callouts.
- A logo and a shloka at the top of the README and the website: every Vayu tool has them now.
- Screenshots in the README and on the website.

## v0.1.3 -- 2026-10-21

- A website (GitHub Pages, https://theyashsawarkar.github.io/doot/): the README as a home page, the
  changelog, and architecture decision records (`docs/adr/`), built from these files by
  `scripts/build-site.py`; CI checks the site is up to date.

## v0.1.2 -- 2026-10-21

- Documentation for open source: a logo and banner, a full README (features,
  install, usage, configuration, troubleshooting, the whole Vyom family),
  CONTRIBUTING, SECURITY and CODE_OF_CONDUCT, issue and pull request
  templates, and CI (compiles, checks plugin.toml and that every key is
  documented).

## v0.1.1 -- 2026-10-19

- Keys are spelled out (Ctrl+Enter, Shift+Enter, Backspace) instead of symbols
  (⌃↵, ⇧↵, ⌫) in the footer and on rows and buttons.

## v0.1.0 -- 2026-10-19

- First release, as its own repository: your phone, through KDE Connect. Replaces phone-picker.py in Vayu.
- The phone's **battery, charging and mobile signal** at a glance.
- Its actions as rows: send the clipboard, **send a recent file** (from Downloads, Pictures, Documents…), ring it to find it, ping it, browse its storage, unpair.
- Pairing requests at the top with Accept / Reject and the verification key; other known devices below (pair the reachable ones).
