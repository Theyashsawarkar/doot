# 3. Build on KDE Connect

**Status:** Accepted  
**Date:** 2026-10-19

## Context

Phone integration needs pairing, encryption and an app on the phone; reimplementing that is out of scope.

## Decision

doot talks to the KDE Connect daemon (`kdeconnect-cli` and D-Bus) for battery, files, ringing and pairing.

## Consequences

- Works with the KDE Connect app on Android and iOS.
- The daemon must be running.
