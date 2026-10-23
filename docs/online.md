# Offline behaviour and online menus (T014)

Offline play comes first (the official servers are gone). Nothing here connects to any external
server. Online play against a server the user hosts locally is planned in [multiplayer.md](multiplayer.md)
(T015, user's permission 2026-10-23); that doc also has the measured online request the 01.09 client sends. Measured 2026-10-21 on 01.09 with
`tools/boot_check.sh --pad`, frames read from the captures.

## What the title calls at boot

`sceNpInit` (pool 128 KB), `sceNpManagerRegisterCallback`, `sceNpManagerGetStatus` → OFFLINE, the
trophy set (`NPWR00406`, context created and its saved data loaded), `cellNetCtlInit`,
`cellNetCtlAddHandler`, one `cellNetCtlGetState` (fails with NOT_INITIALIZED in offline mode, by
design: the title's connect job exits on a negative return), then `cellNetCtlGetNatInfo` polled
about **40 times a second** forever (NAT type 2 is returned; ~2500 log lines a minute, a cost
only in a verbose log).

## Online menu: Play Online

Main menu items: Continue, **Play Online**, Split Screen, Options, Extras.

| Version of the stub | Result |
|---|---|
| `NetStartDialogUnloadAsync` result 0 ("connected") | "Logging in..." for ~18 s, then "TIMED OUT / The operation has timed out." |
| Result DIALOG_CANCELED (patch 0059, offline default) | "Logging in..." then, within ~8 s of the press, "An error occurred when retrieving data from the online service, please try again later." |

Cross dismisses the message and the main menu is back with no stall (frames keep presenting,
`unresolved 0`). So Play Online fails cleanly, no hang. Reproduce:
`tools/boot_check.sh 72 --version 0109 --pad 'cross@45,down@50,cross@55,cross@64'`.

`PS3_NET_ONLINE=1` restores the old fake-connected behaviour (result 0) for online experiments.

## Split screen (the offline multiplayer)

Split Screen opens the lobby (`LOCALLOBBY` package opened): player 1 "Guest1" joined, three
"PRESS ▶ TO JOIN" slots for ports 2-4. Joining from further pads was **not** exercised:
`boot_check --pad` drives port 0 only. A multi-pad check needs real or injected pads on ports
1-3 (`cellPad` SDL backend, `PAD_FILE` is port 0).

## Left to do

- A shorter or silent GetNatInfo poll is possible but changes what the title sees; left alone.
- Join and play with 2+ pads (needs a multi-port injection in `libs/input/cellPad.c`).
- Other online screens (Extras → leaderboards, if any) were not visited.
