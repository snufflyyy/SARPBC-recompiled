# T065: Native-feeling Graphics screen in the game's Options menu (T065)

Status: claimed
Owner: claude
Priority: 5
Touches: src/overrides/ (new graphics_menu.cpp: hooks keyed by guest address/NID), config.toml, docs/unreal-engine-3.md, new docs/graphics-menu.md
Reads: docs/unreal-engine-3.md, docs/subsystems.md (video/menus), tasks T062 (unlocked fps), T063 (resolution), T064 (fps overlay)

## Goal
User request 2026-10-22: the graphics settings (unlocked fps T062, resolution/render scale T063, FPS overlay T064,
later anisotropic filtering etc.) are reached from the game's own menus, not only from config.toml/env: a new
"Graphics" button inside the main menu's Options screen, next to "System", "Profile", ..., which opens a
screen built like those siblings (same list layout, fonts, button prompts, sounds, cursor/back behaviour), so it
feels native to the game. Settings persist (gamedata/, never game data in git) and apply live where possible.

Open questions to answer first (log them): how the Options screen is built (Scaleform GFx movie? UnrealScript
UI scene in a cooked package?) and where its entries come from (a localisation/INT string list? a movie asset?
code in the EBOOT?). Rule 1 of AGENTS.md applies: no game assets or lifted code in git, so the Graphics screen
cannot be a modified cooked package checked in. Candidate routes, to be measured: (a) intercept at run time:
hook the screen's list-population and selection code by guest address, add one entry and route its action to a
native screen that reuses the same movie/list widget with our rows; (b) patch the loaded package bytes in
memory at load time from a small checked-in description (our own data, applied to the user's files in vfs/,
not distributed); (c) as a fallback, draw the screen ourselves in the present pass with the game's own font
atlas captured at run time, driven by the pad. Choose by what the Options screen turns out to be.

## Done when
Options menu shows "Graphics" in the right place with the right look, opens a working screen with the settings
from T062-T064 (on/off, resolution and scale choices), back button returns to Options, choices persist across
runs, verified by pad-scripted boot_check captures; the approach and every guest address are documented in
docs/graphics-menu.md; no game data tracked; lint passes.

## Log

## Log
- 2026-10-22 18:10 claude: claimed
- 2026-10-22 18:36 claude: Options screen = UnrealScript states in TAGAME.XXX (PsyUI), not Scaleform. Route (b): patch script/default-property bodies in the player's package, served by PS3_VFS_OVERLAY (needed patch 0077: ppu_fs HDD0 branch skipped the overlay). tools/ue3 reads/writes v539 packages; tools/graphics_menu_patch.py builds the overlay. Verified 2026-10-22 by pad-scripted boot: Options now lists System/Graphics/Profile/Controls with our INT text (Graphics opens the System page for now). Natives: all exec thunks are in a name table near file off 0x1247000; Helpers.FindLocalizedPropertyValue(Object,string)->string (thunk 0xBBCC58) is never called from script = the bridge. FFrame: Object +8, Code +0xC, GNatives 0x12D17B8, GMalloc 0x123CF30 (Realloc vtable+8, Free +0xC). Design and format notes: docs/graphics-menu.md
