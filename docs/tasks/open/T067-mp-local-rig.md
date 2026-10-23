# T067: Local server rig: config-driven redirect, port map, two instances on one machine

Status: open
Owner: -
Priority: blocked
Touches: config.toml, src/main.cpp, src/overrides/net_*.cpp (new), patches/ps3recomp/NNNN-net-portmap.patch (libs/network/sysNet.c), tools/mp_local.sh (new), docs/multiplayer.md, docs/build-linux.md
Reads: docs/multiplayer.md (sections 1, 6, 8), docs/online.md, patches/ps3recomp/0073-net-hostmap-sandbox.patch, tools/run.sh, tools/boot_check.sh

## Goal
Part of the multiplayer port (umbrella T015). Make "talk to a server I run locally" a **configuration**, not an
env-var recipe, and make two clients run side by side.

1. `config.toml` `[online]`: `enabled` (default false), `server` (host or IP), `hostmap` entries
   (`sarb.psyonix.com`), `account` (online ID), `p2p_port`, `sandbox` (default true). Env still wins. Offline
   stays the default and must behave exactly as today (docs/online.md) when `enabled=false`.
2. **Port map** in sys_net (extend patch 0073's idea, title-agnostic): `name:port=ip:port`, so the client's
   `sarb.psyonix.com:80` reaches `127.0.0.1:8080` without root. Log it like the hostmap; sandbox rules apply to
   the mapped destination.
3. `tools/mp_local.sh start|stop|status`: starts the local server processes the user points it at (web service,
   and RPCN if T068 says so) from a git-ignored `.local-server/` directory, with pid files, so `stop` only stops
   what it started (never `pkill` by name). Until T068 delivers the real server it can start the T066 probe.
4. **Toolchain for RPCN** (only if T068's decision D1 says RPCN is needed): **ask the user first** before
   installing anything (`dnf install cargo protobuf-compiler` or docker/podman; none installed on 2026-10-23).
   Build in `.local-server/rpcn/`, `rpcn --cert-gen`, bind to loopback only.
5. **Two instances on one machine**: per-instance saves/profile (`gamedata/`, VFS save dir), P2P port
   (`PS3_NET_P2P_PORT`), UE3 listen port, window title/output dir, audio device sharing; document the exact two
   command lines in docs/multiplayer.md.

## Done when
With the T066 probe (or the real server) on loopback and only `config.toml` edited, the game's Play Online
request arrives at it (no env vars, no root), `[sys_net] SANDBOX blocked` never appears for it, and two
instances boot side by side with separate saves, each logging its own P2P port. Offline default verified
unchanged (`tools/verify.sh --no-boot` and a normal boot_check). Lint clean.

## Log
- 2026-10-23 claude: created from the multiplayer research. Port 80 is privileged; the box runs as root today
  but the port map keeps it working for other users and agents.
- 2026-10-23 user: "the server isn't open source like i assumed. just postpone the multiplayer plan." Set to blocked; resume when the user supplies the server (or decides on a different approach).
