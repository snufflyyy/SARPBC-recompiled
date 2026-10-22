# Enhancement candidates (researched 2026-10-22)

What could be added next to the Options > Graphics page and the port, ranked by effort, each with the evidence
behind it. "Tested" means a pad-scripted boot of the arena spawn scene compared with a baseline at the same
moment (same pad script, 1280x720 PNG diff, `base` vs experiment); "static" means read from the game's scripts or
the runtime but not yet tried. The engine INI is `PS3-TAEngine.ini` inside `COALESCED.INI`; the overlay tool
(`tools/graphics_menu_patch.py`, see `patch_engine_ini`) already rewrites it for the unlocked frame rate, so an INI
value costs one line plus a menu row, and applies at the next start.

## Tested: work through the INI (easy)

| Idea | How | Result |
|---|---|---|
| **Anisotropic filtering** (16x) and trilinear | `MaxAnisotropy=4 -> 16`, `Trilinear=true` (all four `[SystemSettings*]` sections) | Distant floor texture and the lane lines are visibly sharper (zoomed crops); no cost seen. The runtime already honours the game's sampler state (dod3-reuse "Port next" 10). Row: Off/4x/8x/16x |
| **Brightness / gamma** | `[Engine.Client] DisplayGamma=2.2` | `1.6` changed 72 % of the pixels by more than 8/255 (mean 20): a real brightness control. Row with 1.6 / 1.9 / 2.2 / 2.5 / 2.8 |
| **Sharper textures** | `TEXTUREGROUP_World*=(...,LODBias=-1)` | Slightly more detail on the floor; small |

## Tested: no effect (do not offer)

`Bloom`, `QualityBloom`, `MotionBlur`, `AmbientOcclusion`, `Distortion` (all four `[SystemSettings*]`): the arena
looks the same, the cooked post-process chain has no such passes. `MaxShadowResolution 512 -> 2048`,
`MinShadowResolution`, `ShadowTexelsPerPixel`, `ShadowFilterRadius`, `ShadowFilterQualityBias`: shadows unchanged.
`MaxMultisamples=4`: diff 0.3 (animation noise only). `[Engine.Client]`-level `FOVAngle=110`: no change (the car
camera overrides it). **`DepthOfField=false` is harmful**: black outlines appear around the boost pickups.

## Static evidence: easy script or data patches (same machinery as the Graphics page)

| Idea | Evidence | Plan |
|---|---|---|
| **Skip the intro** (Loading, ESRB, Powered by Unreal, Psyonix) | `IntroSceneContainer.InitScene` starts with `if (EngineShare.ParseCommandlineParam('nosplash')) { CloseScene(); return; }`: the game has a built-in `-nosplash` | Either put `-nosplash` on the guest's command line, or replace that condition by `true` with `tools/ue3/asm.py` (one statement). Row: "Skip intro" |
| **Safe area 100 %** | The Screen Size row shows 85 % (`TAProfile.ViewportScreenScalingX/Y`, applied by `TAGameViewportClient.UpdateScreenScaling(x, y)`); the 85 % black frame is visible in every screen. `ScreenSizeMessageBoxActor` is the "adjust your screen" intro page | Set the profile default to 1.0 (data patch in the default object, like `OptionsItems`) and/or call `UpdateScreenScaling(1, 1)` at start; skip the safe-area page. Not yet checked where the 0.85 default comes from |
| **Language** | `cellSysutil` answers the language from `PS3_LANG` (en/fr/de/es/it...) else the host locale; the install has `COALESCED.INT/.DEU/.ESN/.FRA/.ITA` | A Language row writing `PS3_LANG` for the next start (restart) |
| **Frame cap choices** (30 / 60 / 120 / unlimited) | `SARPBC_FPS_CAP=<n>` already limits flips (docs/frame-pacing.md); Frame Rate row has two choices today | More choices on the existing row; the cap is on the drain thread (a cap under 60 costs a little) |
| **Render scale without a restart** | Surfaces are cached by the engine | Invalidate the engine's surface table on change (backend + engine, medium) |

## Medium effort

- **FXAA / post anti-aliasing**: the runtime has none (`grep -i fxaa libs/video`: nothing); Drakengard 3's fork has an
  `RSX_AA` FXAA pass at present (`g_rsx_aa`): port it as a backend patch, row Off/On.
- **Field of view**: `FOVAngle` in the INI is overridden; `TAComponents.ini` has `[TAGame.CarFOVComponent]` with
  `CamFOVModifier.Value` 105/75/80 (and `BoostTimeForFullFOV`): the likely lever. Untested.
- **Live gamma**: a small shader in the present blit (backend), no restart.
- **Shadow quality**: INI values do nothing visible here; Drakengard 3's `sysset.cpp` reached `FSystemSettings` in
  memory (`GSystemSettings`): the same needs the EBOOT addresses found for this title.
- **Window**: remember position, borderless, resolution list from the monitor, a resizable window (the swapchain
  follows already).

## Housekeeping found on the way

- The Graphics page is full at six rows; the patch tool now allows eight (rows 6+ clone row 0).
- Frame dumps are the full display image: at render scale 300 % one is 25 MB (see debugging.md "Disk space").
