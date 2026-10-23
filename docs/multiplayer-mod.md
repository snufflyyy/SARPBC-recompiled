# Multiplayer: the community online mod, compared with 01.09

Living document for T068. **Not started: the mod's files are not on this machine.** Plan and context:
[multiplayer.md](multiplayer.md). Fill this in from the diff (`mod_diff.py` (T068, to be added under tools/)), summarised by purpose; never
paste game bytes, code dumps or key values (AGENTS.md rule 1).

## What is known from public sources (read 2026-10-23) [unverified]

- **SARPBC Online Mod 1.15**, by kuxir97; setup guide by eiddor (https://github.com/eiddor/sarpbc-online),
  which says the author of the guide neither made nor hosts the mod. Files: SARPBC v1.02 PKG, v1.04 PKG
  (`NPUB30035`), `SARPBC Online Mod 1.15.pkg`, optional `stuttering fix.pkg`. Install order 1.02 → 1.04 → 1.15.
  Distributed through the SARPBC+ Discord (https://discord.gg/qzDfqkaVTB).
- Played in RPCS3 with RPCN: PSN status RPCN, network "Connected", an RPCN account (email token), RPCN friends.
  In game: Play Online → **Unranked Match** (host starts matchmaking from the lobby) / **Join A Friend**.
- Guide advice that hints at what the mod changes: cap fps (the engine's frame rate is uncapped), disable
  controller deadzones and anti-deadzones ("the patch adjusts some input values").
- Known issues: poor performance for ~2 minutes after boot, scoring on **Galleon** crashes, saving **replays**
  crashes.
- RPCS3 wiki RPCN compatibility row: "Requires OpenSpy patch and a custom pkg", custom server **Available**.

## Questions this document must answer

| # | Question | Answer |
|---|---|---|
| 1 | Is the mod's 1.04 the same build as our 01.09 (EBOOT hash, packages, SFO)? | |
| 2 | What does 1.15 change: EBOOT/SPRX ranges, which UE3 packages/functions/default properties, COALESCED keys? | |
| 3 | How does it redirect `sarb.psyonix.com`: patched URL, package default, DNS? | |
| 4 | Version strings, `DB=` and `CallProcKey` the mod's client sends (kept out of git) vs 01.09's | |
| 5 | What are the "Unranked Match" / "Join A Friend" flows in terms of web procedures and NP calls? | |
| 6 | What is the server (name, protocol, source, ports, accounts)? Is RPCN used, and for what? (decision D1) | |
| 7 | Input changes (deadzones) and the "stuttering fix" | |
| 8 | Anything the mod needs from the runtime that ps3recomp lacks | |
