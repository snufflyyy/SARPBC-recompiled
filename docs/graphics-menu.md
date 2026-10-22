# Graphics menu (T065): how the game's menus are built and how we add a page

User request 2026-10-22: a "Graphics" button in the main menu's Options screen, next to System, Profile
and Controls, opening a native-looking page with the settings of T062 (unlocked fps), T063 (resolution),
T064 (FPS overlay). This file is the research log and the design. Rule 1 of AGENTS.md applies: nothing
derived from the game's packages is committed. We commit tools, our own bytecode and the notes below.

## Findings (all verified on the 01.09 cook unless marked as a guess)

**The menus are UnrealScript, not Scaleform.** The UI framework is Psyonix's own **PsyUI** (`PSYUI.XXX`:
`PsyUIListWidget`, `PsyUISpriteWidget`, `PsyUIBitmapTextWidget`, Kismet-style `SeqAct_PsyUI*` actions);
the screens are classes in `TAGAME.XXX` (`MainMenuSceneContainer`, `MidGameMenuActor`, ...) whose
behaviour is script *states*. Text comes from `COALESCED.INT` (plain-text ini sections, keys like
`?loc:tagame:MainMenuSceneContainer:Options` in script).

**The Options screen** (main menu > Options): `MainMenuSceneContainer`, state `Options`:
`Options.BeginState` sets `CurrentItems = OptionsItems` and the title text; `Main.BeginState` (the
shared list builder) copies `CurrentItems[i].ItemText` into `MainMenuList` rows; `Main.PressedConfirm`
reads `CurrentItems[sel].StateName` and `GotoState`s it. `OptionsItems` is a default property, an array
of structs `{ItemText, StateName, HonkyDescStr, bFadeable}` with three entries today:
System (`GameOptions`), Profile (`ProfileOptions`), Controls (`ControlsOptions`).

**The System page** is `MidGameMenuActor_SystemOptions` (a subclass of `MidGameMenuActor`, the pause
menu), spawned by `MainMenuSceneContainer.GameOptions.NextScene`; its `InitScene` calls
`InitOptionsItems(SystemOptionsMenuList, SystemOptionsMenuItems)` then `GotoState('SystemOptions')`.
`SystemOptionsMenuItems` is a default array of `{ItemText, ItemObject}`; each `ItemObject` is a
component (`OptionsMenuItemValue_Slider` or `_ToggleList`) with delegates bound to `Init<Name>` /
`Handle<Name>` script functions (`InitVSync`/`HandleVSync`, `InitScreenSize`, `HandleMusicVolume`...).
Seven rows today: Game Volume, Music Volume, Music Tracks, Split Screen, Voice Volume, Screen Size,
VSync. Settings live in `TAProfile.GetSystemProfile()` (`bUseVSync`, `ViewportScreenScalingX`...);
`HandleVSync` ends with `TAGameViewportClient.GetInstance().ReApplySystemSettings()`, a native.
The Profile page is `MidGameMenuActor_ProfileOptions` with three rows (DualShock, Invert Camera,
Primary Camera).

**Consequence: no new package objects are needed.** Everything above is data in default properties and
bytecode in functions. A Graphics page can be built by replacing the *bodies* of a few existing
functions (and one default-properties body), which is what dod3-recomp did for its Graphics page
(its `menu_patch.py` and `settings_menu.cpp`, soyjxck/dod3-recomp, MIT). Row objects can even be
created at run time in script (`new` is token 0x11).

## Package format (version 539, PS3 cook; `tools/ue3/upk.py`, `pkgwrite.py`)

- File: summary (tag `0x9E2A83C1`, version `0x021B`, licensee 1, header size, folder `None`, package flags,
  name/import/export/depends counts and offsets, GUID, generations, engine and cooker versions),
  `u32 compression = 1` (zlib), `u32 chunk count`, the chunk table `{uncompressed offset, uncompressed
  size, file offset, compressed size}` (16 bytes each), `u32 package source` + `u32 0`, then the chunks.
  Each chunk is `{tag, block size 65536, compressed size, uncompressed size}`, a `{compressed,
  uncompressed}` pair per block, the zlib blocks. The file is zero-padded to 2048-byte sectors.
- The uncompressed image keeps the first 109 bytes of the summary (compression fields zeroed); chunk 0
  starts at 109 and holds the name table, import table, export table and the first objects, so the
  tables can only be read after inflating.
- Name: `FString` + `u64` flags. Import: 28 bytes `{package(name,num), class(name,num), outer i32,
  object(name,num)}`. Export record: `class, super, outer i32; name, number u32; archetype i32; flags
  u64; size i32; offset i32; component-map count u32 + 12 bytes each; export flags u32 (a count in the
  record's tail that is 0 except for a few); u32 count of net-object generations + 4 bytes each; GUID 16;
  package flags u32; u32 0`, i.e. **72 + 12 x components + 4 x net counts** bytes. (Found by trial: a
  linear read with a fixed record size loses sync at export 973, which has a component map.)
- Object references: positive = export index + 1, negative = import.
- A tagged property: name (idx, num), type name, size i32, array index i32, then for `StructProperty`
  the struct name, for `ByteProperty` the enum name, for `BoolProperty` **a u32 value** (size is 0);
  then `size` bytes. `None` ends the list. A default object body starts with a 4-byte word before the
  first tag (`tools/ue3/props.py` `skip=4`).
- Function body: 11 words, then bytecode. Word 0 = next field, word 6 = first parameter/local, word 10 =
  the bytecode's **in-memory** size (object references are 4 bytes on disk, 8 in memory); the bytecode runs
  to `EX_EndOfScript` (0x53); the tail is `iNative u16, operator precedence u8, flags u32, [replication
  offset u16 when FUNC_Net (0x40)], friendly name (8)`, 15 or 17 bytes.
- Bytecode tokens are the same ones dod3's parser handles: 4,982 of the 4,990 functions in `TAGAME.XXX`
  parse and re-encode byte for byte (`tools/ue3/funcedit.py`). The 8 that fail use tokens 0x4C-0x4E.
- Strings in script: `EX_StringConst` (0x1F) holds `?loc:tagame:Class:Key` for localised text, or plain
  text.
- Writing a patched package (`tools/ue3/pkgwrite.py`): append new export bodies to the image, point the
  export records at them, recompress only the changed chunks (the one with the export table) and add a
  chunk for the appended tail. Names cannot be added (that would move the tables), so a patch uses
  existing names and string constants.
- `PS3TOC.TXT` lists each file's on-disk size (`<size> 0 0 ..\TAGame\CookedPS3\TAGame.xxx 0`): a patched
  package needs its line rewritten.

## Serving patched files: `PS3_VFS_OVERLAY`

`PS3_VFS_OVERLAY=<dir>` lays files under `<dir>/<path relative to dev_hdd0>` over the VFS (patch 0019,
ported from dod3). Until patch **0077** (`ppu_fs.cpp`) it never applied to this title: the `/dev_hdd0`
branch of `host_path()` returned before the overlay. The overlay tree for 01.09 is
`<dir>/game/NPUB30035/USRDIR/SARB/TAGAME/{PS3TOC.TXT,COOKEDPS3/TAGAME.XXX,LOCALIZATION/COALESCED.INT}`.

## Native functions and the bridge to the host

The EBOOT registers every native's exec thunk in a table of 12-byte records `{wide-string name pointer,
OPD pointer, 0}` in the data segment (file offset about `0x1247000`; the names read
`<type>Class` + `exec` + `Name`, UTF-16BE, e.g. `intAActorexecConsoleCommand`). The OPD's first word is the
thunk's address. 2,039 records (script `/tmp` survey, 2026-10-22). Several unimplemented natives share one
stub thunk (`0xBC9614`). Natives the shipped game never calls from script are the candidates for a
host bridge (replace the thunk with `ppu_register_function`, as dod3 does): see "Bridge candidates"
below once chosen.

`TAGameViewportClient.ReApplySystemSettings` (thunk `0xBCA908`) is what the System page's VSync row calls
after changing a setting; hooking it is the natural "settings changed" signal.

## How it works (built and verified 2026-10-22)

`tools/graphics_menu_patch.py` builds the overlay (`<vfs>/../overlay`, git-ignored; `--ensure` rebuilds only
when the inputs or the tool changed; `tools/run.sh` and `tools/boot_check.sh` call it and set
`PS3_VFS_OVERLAY`; `SARPBC_NO_GRAPHICS_MENU=1` turns it off). It patches, by path, in `TAGAME.XXX`:

| What | Change |
|---|---|
| `Default__MainMenuSceneContainer` | a fourth `OptionsItems` entry after System (same state, `GameOptions`) |
| `MainMenuSceneContainer.GameOptions.NextScene` | selected row 1 = Graphics: title `GraphicsOptions`, tells the host (`open:gfx`) |
| `MidGameMenuActor_SystemOptions.InitScene` | Graphics: clones the instance's VSync row (`new(...)` with a template, so its delegates are bound to this actor) once per host row; System: keeps six rows |
| `MidGameMenuActor.InitVSync` / `HandleVSync` | the clones' handlers: labels, choices, current value and changes come from the host; the VSync row falls through to the original code (profile, `ReApplySystemSettings`, save) |
| `MidGameMenuActor.SystemOptions.BeginState` | frame height and position fit the row count |
| `OptionsMenuItemValue_ToggleList.SetValue/PressedConfirm`, `InitScene` | markup off on the Graphics page (PsyUI text is markup: plain text shows "Invalid Markup Text") |
| `MidGameMenuActor_SystemOptions.CloseSubScene`, `MidGameMenuActor.InitScene` | `close` / `open:sys` so the pause menu's System page is never left in Graphics mode; both pages now list six rows (VSync moved to Graphics, user 2026-10-22) |

and in `COALESCED.INT`: `[MainMenuSceneContainer] GraphicsOptions/GraphicsOptionsDesc`, `[BackNextWidget] GraphicsOptions`
(the page title is `?loc:tagame:BackNextWidget:` + `NewTitleName`, a **string** property: a name constant there
shows no title). The patch uses no new package objects; new names are appended (`pkgwrite.Package.name`).

The host side is `src/overrides/graphics_menu.cpp` (the bridge and the row list) and `graphics_settings.{h,cpp}`
(values, persisted in `gamedata/graphics.ini`, `$SARPBC_GFX_FILE`). Rows today: Resolution (the window's
size; the frame is scaled to it, patch 0080), Render Scale (T063, restart), Fullscreen (live), VSync (the game's
own), Frame Rate (T062, restart to apply), FPS Counter (T064); the ones that switch something (T062-T064) read
`sarpbc_gfx::settings()`.

Script gotchas learned: a call node's name is `parts[0]`, its arguments follow (`parts[1]...`); `if` needs the end
label on the statement after the block; bytecode token 0x12 is the class-static context, 0x19 the object
context, 0x10 a dynamic-array element, 0x35 a struct member, 0x36 array length, 0x11 `new`
(Outer, Name, Flags, Class, Template); casts: IntToString 83, StringToInt 74, StringToFloat 76.

Adding a row: append to `make_rows()` in graphics_menu.cpp (at most `MAX_ROWS` = 8 in the patch tool; rows 6+ clone row 0,
`MAX_CHOICES` = 12 choices); nothing else changes.

## Status

Menu done and verified by pad-scripted boots (Options lists System/Graphics/Profile/Controls; the page opens,
popups work, choices persist, VSync works, System has six rows). Tools: `tools/ue3/` (upk, script, dis, props,
funcedit, asm, tree, pkgwrite, coalesced).

## Render scale (T063, done 2026-10-22)

Options > Graphics > Render Scale (50/75/100/150/200/300 %, applies at the next start; `SARPBC_RENDER_SCALE=<percent>`).
The engine's own `ScreenPercentage` does nothing here (the PS3 build ignores it: surfaces stay 1280x720), so the
scale is done in the Vulkan backend (patch 0081, `rsx_vulkan_backend_set_render_scale`):

- Every colour and depth target of at least 320x180 guest pixels is allocated `scale` times larger; smaller ones
  (cube faces, 1x1 reductions) keep their size. Each target object keeps its guest size (`w`, `h`, what the draw
  engine speaks) and its image size (`pw`, `ph`, `sc`).
- The boundary converts: viewport and scissor are scaled when a draw is recorded (the engine always sets the
  full surface, the guest's own viewport is a shader epilogue in guest pixels, so shaders needed no change);
  guest-memory transfers into a scaled target (seed, 2D writes) and readbacks (coherence, depth) are resampled
  nearest on the CPU; depth snapshots (shadow maps) crop the scaled rectangle; feedback snapshots copy the
  image size; the framebuffer and scratch depth use the image size.
- The display image (`s_vk.width/height`) is the scaled canvas, so frame dumps and the window blit use the full
  render; `s_vk.lw/lh` stay the guest's 1280x720 for the engine. The window opens at the Resolution row's size
  and is independent of the scale (the present blit scales to it, so a 200% render in a 1080p window is a
  supersampled 1080p picture).
- Verified (arena, menus, loading screens): 100% unchanged, 50% = 640x360, 150% = 1920x1080, 200% = 2560x1440,
  300% = 3840x2160; shadows, glow, HUD and post effects match 100% at the same moment, the HUD and text are sharp.
  Guest fps in the arena at 300%: ~23 (the GPU idles at P8/405 MHz here); 100-150% cost little.
- Not done: changing it at run time (surfaces are cached by the engine), and the screen-space constants the game
  feeds some post passes stay in 1280x720 units (nothing visibly wrong was found; look here first if a post
  effect shows a seam at a scale).

Fullscreen (row 3, live, `SARPBC_FULLSCREEN=1`, **F11**): desktop fullscreen through SDL (patch 0082); leaving it
restores the Resolution size. The setting, the row and the call were checked; the window itself could not be (the
only X server here, Xvfb, has no window manager, so SDL cannot honour the request): a failure is logged
(`[RSX vulkan] fullscreen on failed: ...`).
