#!/usr/bin/env python3
"""Build the Graphics-menu overlay for the player's own 01.09 files (T065).

    tools/graphics_menu_patch.py [--ensure] <vfs dir> <overlay dir>

--ensure builds only when the inputs or this tool changed since the last build (a stamp file in
the overlay dir) and is silent otherwise; tools/run.sh and tools/boot_check.sh call it, then set
PS3_VFS_OVERLAY. SARPBC_NO_GRAPHICS_MENU=1 skips it.

Reads <vfs>/dev_hdd0/game/NPUB30035/USRDIR/SARB/TAGAME/{COOKEDPS3/TAGAME.XXX, PS3TOC.TXT,
LOCALIZATION/COALESCED.INT}, writes the patched copies under <overlay>/game/NPUB30035/...
(what PS3_VFS_OVERLAY lays over the VFS). Nothing from the game is kept in this repo:
the edits are ours and the output goes to a git-ignored directory. docs/graphics-menu.md
says what each edit is and why.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from ue3 import asm, coalesced, dis, funcedit, pkgwrite, props, upk   # noqa: E402

REL = 'game/NPUB30035/USRDIR/SARB/TAGAME'
TOC_TAGAME = '\\cookedps3\\tagame.xxx'
TOC_INT = '\\localization\\coalesced.int'
TOC_INI = '\\config\\battleball\\ps3\\cooked\\coalesced.ini'
INI_REL = 'CONFIG/BATTLEBALL/PS3/COOKED/COALESCED.INI'

GRAPHICS_TEXT = 'Graphics'
GRAPHICS_DESC = 'Change the resolution, frame rate and other video options.'
GRAPHICS_TITLE = 'Graphics Options'
SKIP_INTRO_TEXT = 'Skip Intro'
MAX_ROWS = 10       # rows the page can show: rows 0-5 clone the instance's VSync row, later ones clone row 0
MAX_CHOICES = 12    # choices a row can offer



def patch_coalesced(path):
    entries = coalesced.load(open(path, 'rb').read())
    for e in entries:
        if e[0].rstrip('\0').lower().endswith('\\int\\tagame.int'):
            e[1] = coalesced.section_add(e[1], 'MainMenuSceneContainer', [
                'GraphicsOptions="%s"' % GRAPHICS_TEXT,
                'GraphicsOptionsDesc="%s"' % GRAPHICS_DESC,
            ])
            e[1] = coalesced.section_add(e[1], 'MidGameMenuActor', ['SkipIntroStr="%s"' % SKIP_INTRO_TEXT])
            e[1] = coalesced.section_add(e[1], 'BackNextWidget', ['GraphicsOptions="%s"' % GRAPHICS_TITLE])
            return coalesced.dump(entries)
    raise KeyError('TAGame.int')


# Engine-INI settings (graphics.ini keys / SARPBC_* indexes; the choice tables mirror graphics_settings.h).
TEXTURE_LOD_BIAS = (3, 0, -1)                       # Low, Default, High (+3 softens modestly, tested)
TEXTURE_FILTER = ((4, False), (8, False), (16, False), (16, True))   # (MaxAnisotropy, Trilinear)
BRIGHTNESS_GAMMA = ('1.800000', '2.000000', '2.200000', '2.500000', '2.800000')
DEFAULTS = {'unlock_fps': 0, 'texture_quality': 1, 'texture_filter': 0, 'brightness': 2}
ENV = {'unlock_fps': 'SARPBC_UNLOCK_FPS', 'texture_quality': 'SARPBC_TEXTURE_QUALITY',
       'texture_filter': 'SARPBC_TEXTURE_FILTER', 'brightness': 'SARPBC_BRIGHTNESS'}


def engine_settings():
    """The settings that live in the engine INI: graphics.ini (the Graphics page writes it), the
    SARPBC_* environment switches winning."""
    vals = dict(DEFAULTS)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.environ.get('SARPBC_GFX_FILE') or os.path.join(root, 'gamedata', 'graphics.ini')
    try:
        for line in open(path):
            k, _, v = line.partition('=')
            if k.strip() in vals and v.strip().lstrip('-').isdigit():
                vals[k.strip()] = int(v)
    except OSError:
        pass
    for k, name in ENV.items():
        e = os.environ.get(name)
        if e is not None and e.strip().lstrip('-').isdigit():
            vals[k] = int(e)
    vals['texture_quality'] = min(max(vals['texture_quality'], 0), len(TEXTURE_LOD_BIAS) - 1)
    vals['texture_filter'] = min(max(vals['texture_filter'], 0), len(TEXTURE_FILTER) - 1)
    vals['brightness'] = min(max(vals['brightness'], 0), len(BRIGHTNESS_GAMMA) - 1)
    vals['unlock_fps'] = 1 if vals['unlock_fps'] else 0
    return vals


def unlock_fps_wanted():
    return engine_settings()['unlock_fps'] == 1


def engine_ini_wanted():
    return engine_settings() != DEFAULTS


def patch_engine_ini(path):
    """Edit PS3-TAEngine.ini, inside COALESCED.INI, for the settings that live there:
    - unlocked fps (T062): UE3 sleeps to hold [Engine.GameEngine] MaxSmoothedFrameRate (60) and clamps
      its frame time to it: 1000;
    - texture quality: the LODBias of every TEXTUREGROUP_* (+1 low, -1 high);
    - texture filtering: MaxAnisotropy (4 in the game's four [SystemSettings*]) and Trilinear;
    - brightness: [Engine.Client] DisplayGamma (2.2; lower is darker, tested)."""
    import re
    cfg = engine_settings()
    entries = coalesced.load(open(path, 'rb').read())
    for e in entries:
        if e[0].rstrip('\0').lower().endswith('\\ps3-taengine.ini'):
            t = e[1]
            if cfg['unlock_fps']:
                if 'MaxSmoothedFrameRate=60' not in t:
                    raise KeyError('MaxSmoothedFrameRate=60')
                t = t.replace('MaxSmoothedFrameRate=60', 'MaxSmoothedFrameRate=1000')
            bias = TEXTURE_LOD_BIAS[cfg['texture_quality']]
            if bias:
                t, n = re.subn(r'^(TEXTUREGROUP_[A-Za-z0-9_]+=\(.*?)LODBias=-?\d+', r'\g<1>LODBias=%d' % bias, t, flags=re.M)
                if not n:
                    raise KeyError('TEXTUREGROUP LODBias')
            aniso, trilinear = TEXTURE_FILTER[cfg['texture_filter']]
            if (aniso, trilinear) != TEXTURE_FILTER[0]:
                t, n = re.subn(r'^MaxAnisotropy=\d+', 'MaxAnisotropy=%d' % aniso, t, flags=re.M)
                t, m = re.subn(r'^Trilinear=\w+', 'Trilinear=%s' % ('true' if trilinear else 'false'), t, flags=re.M)
                if not n or not m:
                    raise KeyError('MaxAnisotropy/Trilinear')
            if cfg['brightness'] != DEFAULTS['brightness']:
                t, n = re.subn(r'^DisplayGamma=[\d.]+', 'DisplayGamma=%s' % BRIGHTNESS_GAMMA[cfg['brightness']], t, flags=re.M)
                if not n:
                    raise KeyError('DisplayGamma')
            e[1] = t
            return coalesced.dump(entries)
    raise KeyError('PS3-TAEngine.ini')


def add_options_item(pkg):
    """OptionsItems of MainMenuSceneContainer's defaults: a Graphics entry after System. It
    reuses the System state ('GameOptions'); the page code tells them apart by the row."""
    idx = upk.find_export(pkg.imps, pkg.exps, 'Default__MainMenuSceneContainer')
    e = pkg.exps[idx - 1]
    body = props.parse_body(pkg.u, e['off'], e['size'], pkg.names)
    tag = body.get('OptionsItems')
    items = props.parse_struct_array(tag['value'], pkg.names)
    system = items[0]
    gfx = [dict(t) for t in system]
    for t in gfx:
        if t['pname'] == 'ItemText':
            t['value'] = props.fstring_value('?loc:tagame:MainMenuSceneContainer:GraphicsOptions')
        elif t['pname'] == 'HonkyDescStr':
            t['value'] = props.fstring_value('?loc:tagame:MainMenuSceneContainer:GraphicsOptionsDesc')
    items.insert(1, gfx)
    tag['value'] = props.encode_struct_array(items, body.none_idx)
    pkg.replace_export(idx, body.build())


# ---- the Graphics page: script patches (docs/graphics-menu.md "Design") -------------------------
#
# The host (src/overrides/graphics_menu.cpp) answers one native, Helpers.FindLocalizedPropertyValue,
# which nothing in the game calls. `bridge()` is that call with a command string.

NS = 'MidGameMenuActor.'
ITEMS = NS + 'SystemOptionsMenuItems'
ITEM_TEXT = NS + 'OptionMenuItem.ItemText'
ITEM_OBJ = NS + 'OptionMenuItem.ItemObject'
STRUCT = NS + 'OptionMenuItem'
TOGGLE = 'OptionsMenuItemValue_ToggleList'


class Seq(list):
    """Statements being built. block() appends an if_ result and remembers its end label,
    which lands on whatever statement comes next (finish() for the existing code after it)."""

    def __init__(self):
        super().__init__()
        self.pending = []

    def stmt(self, node):
        if self.pending:
            node.label = (node.label or []) + self.pending
            self.pending = []
        self.append(node)

    def block(self, pair):
        stmts, end = pair
        for s in stmts:
            self.stmt(s)
        self.pending = [end] if end else []

    def finish(self, following):
        if self.pending:
            following.label = (following.label or []) + self.pending
            self.pending = []


class Patcher:
    def __init__(self, pkg):
        self.pkg = pkg
        self.a = asm.Asm(pkg)

    def func(self, path):
        idx = self.a.x(path, 'Function')
        return idx, funcedit.Func(self.pkg, idx)

    def done(self, idx, f):
        self.pkg.replace_export(idx, f.body())

    def bridge(self, *parts):
        a = self.a
        return a.static_call('Helpers', 'Helpers.FindLocalizedPropertyValue', a.NONE, a.concat(*parts))

    def is_gfx(self):
        return self.a.native('EqualEqual_StrStr', self.bridge('page'), self.a.s('gfx'))

    def toint(self, *parts):
        return self.a.cast(asm.CAST_STRING_TO_INT, self.bridge(*parts))

    def istr(self, node):
        return self.a.cast(asm.CAST_INT_TO_STRING, node)

    def selected_row(self, scene_func, text):
        """A clone of `<expr>.GetSelectedIndex()` as the game wrote it in scene_func's statement 1."""
        return asm.clone(self.a.find_sub(self.func(scene_func)[1].stmts[1], text))

    # -- MainMenuSceneContainer.GameOptions.NextScene: which page is being opened ----------
    def next_scene(self):
        a = self.a
        idx, f = self.func('MainMenuSceneContainer.GameOptions.NextScene')
        st = f.stmts
        selected = self.selected_row('MainMenuSceneContainer.Main.PressedConfirm',
                                     'self.MainMenuList.GetSelectedIndex()')
        title = asm.clone(st[1])                      # NewTitleName = 'GameOptions'
        title.parts[-1] = ('e', a.s('GraphicsOptions'))   # NewTitleName is a string: ?loc:tagame:BackNextWidget:<it>
        seq = Seq()
        seq.block(a.if_(a.native('EqualEqual_IntInt', selected, a.i(1)),
                        [title, self.bridge('open:gfx')], [self.bridge('open:sys')]))
        seq.finish(st[2])
        f.stmts = st[:2] + list(seq) + st[2:]
        self.done(idx, f)

    # -- the System page's scene: build the Graphics rows ----------------------------------
    def init_scene(self):
        a = self.a
        idx, f = self.func('MidGameMenuActor_SystemOptions.InitScene')
        st = f.stmts
        items = a.inst(ITEMS)
        # The instance's own VSync row is the template: its delegates (InitVSync, HandleVSync) are
        # bound to this actor, which a copy of the class default's would not be. Row 6 survives
        # until the length is set last, as long as MAX_ROWS <= 6.
        template = a.smember(ITEM_OBJ, STRUCT, a.elem(asm.clone(items), a.i(6)))
        rows = Seq()
        for k in range(MAX_ROWS):
            # rows 6 and up: element 6 is overwritten by then, so clone the first new row instead
            tpl = template if k < 6 else a.smember(ITEM_OBJ, STRUCT, a.elem(asm.clone(items), a.i(0)))
            then = [
                a.let(a.smember(ITEM_TEXT, STRUCT, a.elem(asm.clone(items), a.i(k))), self.bridge('label:%d' % k)),
                a.let(a.smember(ITEM_OBJ, STRUCT, a.elem(asm.clone(items), a.i(k))),
                      a.new(TOGGLE, asm.clone(tpl))),
            ]
            rows.block(a.if_(a.native('Greater_IntInt', self.toint('rows'), a.i(k)), then))
        rows.stmt(a.let(a.length(asm.clone(items)), self.toint('rows')))
        seq = Seq()
        seq.block(a.if_(self.is_gfx(), list(rows), [self.skip_intro_row()]))
        seq.finish(st[0])
        f.stmts = list(seq) + st
        self.done(idx, f)

    def skip_intro_row(self):
        """VSync moved to the Graphics page; the System page's seventh row, built from the same
        component and handlers, is now Skip Intro (the handlers' non-Graphics branch)."""
        a = self.a
        return a.let(a.smember(ITEM_TEXT, STRUCT, a.elem(a.inst(ITEMS), a.i(6))),
                     a.s('?loc:tagame:midgamemenuactor:SkipIntroStr'))

    # -- the VSync row's handlers: the template of every Graphics row ---------------------
    def row_handlers(self):
        a = self.a
        init = NS + 'InitVSync'
        idx, f = self.func(init)
        st = f.stmts
        index = a.loc(init + '.OptionsMenuItemsIndex')
        toggle = st[0].parts[0][1].parts[0][1]            # ToggleList(Items[I].ItemObject)
        values = lambda: a.ctx(asm.clone(toggle), a.inst(TOGGLE + '.Values'))   # noqa: E731
        setvalue = asm.clone(st[1])                       # ToggleList(..).SetValue(<VSync choice>)
        own = setvalue.parts[-1][1].parts[1][1]             # (bUseVSync ? 0 : 1)
        setvalue.parts[-1][1].parts[1] = ('e', a.cond(
            a.native('EqualEqual_IntInt', self.toint('isvsync:', self.istr(asm.clone(index))), a.i(1)),
            own, self.toint('get:', self.istr(asm.clone(index)))))
        then = Seq()
        then.stmt(asm.clone(st[0]))                       # Title = ItemText
        then.stmt(a.let(a.length(values()), self.toint('nvals:', self.istr(asm.clone(index)))))
        for j in range(MAX_CHOICES):
            then.block(a.if_(a.native('Greater_IntInt', a.length(values()), a.i(j)),
                             [a.let(a.elem(values(), a.i(j)),
                                    self.bridge('val:', self.istr(asm.clone(index)), ':%d' % j))]))
        then.stmt(setvalue)
        then.stmt(a.ret())
        seq = Seq()
        seq.block(a.if_(self.is_gfx(), list(then)))
        seq.finish(st[0])
        # System page, seventh row: Skip Intro (Enabled = 0), through the host. First, so the
        # Graphics block's end label lands on the original code after it.
        intro = Seq()
        intro.stmt(asm.clone(st[0]))                                  # Title = ItemText
        sv = asm.clone(st[1])
        sv.parts[-1][1].parts[1] = ('e', self.toint('intro:get'))
        intro.stmt(sv)
        intro.stmt(a.ret())
        seq2 = Seq()
        seq2.block(a.if_(a.native('Not_PreBool', self.is_gfx()), list(intro)))
        seq2.finish(seq[0])
        f.stmts = list(seq2) + list(seq) + st
        self.done(idx, f)

        handle = NS + 'HandleVSync'
        idx, f = self.func(handle)
        st = f.stmts
        selected = self.selected_row(NS + 'SystemOptions.PressedConfirm',
                                     'self.SystemOptionsMenuList.GetSelectedIndex()')
        setvalue = asm.clone(st[0])                       # Item.SetValue(ChosenIndex)
        setvalue.parts[-1][1].parts[1] = ('e', self.toint('set:', self.istr(selected), ':',
                                                          self.istr(a.loc(handle + '.ChosenIndex'))))
        then = Seq()
        then.stmt(setvalue)
        # any row but VSync is done; VSync runs the game's own code below (profile, ReApply, save)
        then.block(a.if_(a.native('NotEqual_IntInt',
                                  self.toint('isvsync:', self.istr(asm.clone(selected))), a.i(1)),
                         [a.ret()]))
        seq = Seq()
        seq.block(a.if_(self.is_gfx(), list(then)))
        seq.finish(st[0])
        st[0].label = (st[0].label or []) + then.pending      # the inner end falls out of the block too
        # System page, seventh row: Skip Intro. First; it returns, the Graphics block is skipped.
        intro = Seq()
        sv2 = asm.clone(st[0])                                # Item.SetValue(ChosenIndex)
        intro.stmt(sv2)
        intro.stmt(self.bridge('intro:set:', self.istr(a.loc(handle + '.ChosenIndex'))))
        intro.stmt(a.ret())
        seq2 = Seq()
        seq2.block(a.if_(a.native('Not_PreBool', self.is_gfx()), list(intro)))
        seq2.finish(seq[0])
        f.stmts = list(seq2) + list(seq) + st
        self.done(idx, f)

    # -- SystemOptions.BeginState: the frame fits the rows ---------------------------------
    def frame(self):
        a = self.a
        idx, f = self.func(NS + 'SystemOptions.BeginState')
        gfx_h = lambda: a.cast(asm.CAST_STRING_TO_FLOAT, self.bridge('frame:h'))   # noqa: E731
        gfx_y = lambda: a.cast(asm.CAST_STRING_TO_FLOAT, self.bridge('frame:y'))   # noqa: E731
        # the System page keeps its seven-row frame (512, 0.2777); the Graphics page sizes it to its rows
        for text, make in (('self.OptionsFrame.self.StretchSize.Value.Y = 512f', gfx_h),
                           ('self.OptionsFrame.self.ScreenSize.Value.Y = 512f', gfx_h),
                           ('self.OptionsFrame.self.ScreenPosition.Value.Y = 0.2777f', gfx_y)):
            n = f.stmts[a.find(f.stmts, text)]
            n.parts[-1] = ('e', a.cond(self.is_gfx(), make(), n.parts[-1][1]))
        self.done(idx, f)

    # -- literal text: the page's strings are not ?loc: markup ------------------------------
    def no_markup(self):
        """PsyUI text widgets parse their text as markup ('?loc:...') unless told not to; the
        ToggleList passes markup = true, the list rows read bValuesAreMarkup. On the Graphics
        page both are false, so the host's plain strings show as they are."""
        a = self.a
        off = lambda: a.cond(self.is_gfx(), a.FALSE, a.TRUE)   # noqa: E731

        def arg(call, k):
            return [i for i, (kind, _) in enumerate(call.parts) if kind == 'e'][k]


        def calls(stmts, name):
            def called(n):
                if n.op == 0x1B:
                    return self.pkg.names[n.parts[0][1][0]]
                if n.op == 0x1C:
                    return upk.objname(n.parts[0][1], self.pkg.imps, self.pkg.exps)
            return [n for s in stmts for n in funcedit.walk(s) if called(n) == name]
        idx, f = self.func(TOGGLE + '.SetValue')
        call = calls(f.stmts, 'SetText')[0]                 # ValueText.SetText(Values[Index], true)
        call.parts[arg(call, 1)] = ('e', off())
        self.done(idx, f)
        idx, f = self.func(TOGGLE + '.PressedConfirm')
        call = calls(f.stmts, 'ShowOptionsBox')[0]          # (.., Title, bUseMarkupText, ..)
        call.parts[arg(call, 5)] = ('e', off())
        self.done(idx, f)

        idx, f = self.func('MidGameMenuActor_SystemOptions.InitScene')
        prop = [p for p in ('PsyUI.PsyUIListWidget.bValuesAreMarkup', 'PsyUI.PsyUIListBase.bValuesAreMarkup')
                if self._has(p)][0]
        # first statement of the Graphics block (after the `if page == gfx` jump)
        f.stmts.insert(1, a.let(a.ctx(a.inst('MidGameMenuActor.SystemOptionsMenuList'), a.inst(prop), prop),
                                a.FALSE))
        self.done(idx, f)

    def _has(self, path):
        try:
            self.a.x(path)
            return True
        except KeyError:
            return False

    # -- IntroSceneContainer.InitScene: Skip Intro -----------------------------------------------
    def intro(self):
        """The game closes the intro scene at once when the command line has -nosplash; the same
        two statements run when the host says to skip (the System page's Skip Intro row)."""
        a = self.a
        idx, f = self.func('IntroSceneContainer.InitScene')
        st = f.stmts
        close = asm.clone(st[a.find(st, 'CloseScene()')])
        ret = asm.clone(st[a.find(st, 'return nothing', 2)[0]])
        seq = Seq()
        seq.block(a.if_(a.native('EqualEqual_StrStr', self.bridge('skipintro'), a.s('1')), [close, ret]))
        seq.finish(st[1])
        f.stmts = st[:1] + list(seq) + st[1:]
        self.done(idx, f)

    # -- leaving the page, and the pause menu's own System page -----------------------------
    def reset(self):
        a = self.a
        idx, f = self.func('MidGameMenuActor_SystemOptions.CloseSubScene')
        f.stmts.insert(0, self.bridge('close'))
        self.done(idx, f)
        idx, f = self.func(NS + 'InitScene')
        at = a.find(f.stmts, 'InitOptionsItems(self.SystemOptionsMenuList, self.SystemOptionsMenuItems)')
        f.stmts.insert(at, self.skip_intro_row())
        f.stmts.insert(0, self.bridge('open:sys'))
        self.done(idx, f)

    def run(self):
        self.next_scene()
        self.init_scene()
        self.row_handlers()
        self.frame()
        self.reset()
        self.no_markup()
        self.intro()


def stamp(vfs):
    """What the overlay depends on: the player's three files and the sources that patch them."""
    import hashlib
    h = hashlib.sha1()
    src = os.path.join(vfs, 'dev_hdd0', REL)
    h.update(repr(sorted(engine_settings().items())).encode())
    for rel in ('COOKEDPS3/TAGAME.XXX', 'LOCALIZATION/COALESCED.INT', INI_REL, 'PS3TOC.TXT'):
        st = os.stat(os.path.join(src, rel))
        h.update(('%s %d %d\n' % (rel, st.st_size, int(st.st_mtime))).encode())
    here = os.path.dirname(os.path.abspath(__file__))
    for path in [os.path.abspath(__file__)] + sorted(
            os.path.join(here, 'ue3', n) for n in os.listdir(os.path.join(here, 'ue3')) if n.endswith('.py')):
        h.update(open(path, 'rb').read())
    return h.hexdigest()


def main(argv):
    ensure = '--ensure' in argv
    argv = [a for a in argv if a != '--ensure']
    if len(argv) != 2:
        print(__doc__)
        return 2
    vfs, out = argv
    stamp_path = os.path.join(out, '.stamp')
    if ensure:
        try:
            if open(stamp_path).read() == stamp(vfs):
                return 0
        except OSError:
            pass
    src = os.path.join(vfs, 'dev_hdd0', REL)
    dst = os.path.join(out, REL)
    pkg_path = os.path.join(src, 'COOKEDPS3', 'TAGAME.XXX')
    pkg = pkgwrite.Package(pkg_path)
    cooked = os.path.dirname(pkg_path)
    dis.load_natives([os.path.join(cooked, n) for n in ('CORE.XXX', 'ENGINE.XXX', 'TAGAME.XXX')])
    add_options_item(pkg)
    Patcher(pkg).run()
    tagame = pkg.save()
    ini = patch_coalesced(os.path.join(src, 'LOCALIZATION', 'COALESCED.INT'))
    toc = open(os.path.join(src, 'PS3TOC.TXT'), 'rb').read().decode('latin-1')
    toc = pkgwrite.toc_set(toc, TOC_TAGAME, len(tagame))
    toc = pkgwrite.toc_set(toc, TOC_INT, len(ini))
    files = [('COOKEDPS3/TAGAME.XXX', tagame), ('LOCALIZATION/COALESCED.INT', ini)]
    if engine_ini_wanted():
        engine_ini = patch_engine_ini(os.path.join(src, INI_REL))
        toc = pkgwrite.toc_set(toc, TOC_INI, len(engine_ini))
        files.append((INI_REL, engine_ini))
    else:   # an overlay built earlier with the setting on must not keep its file
        stale = os.path.join(dst, INI_REL)
        if os.path.exists(stale):
            os.remove(stale)
    for rel, data in files + [('PS3TOC.TXT', toc.encode('latin-1'))]:
        path = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'wb').write(data)
    open(stamp_path, 'w').write(stamp(vfs))
    print('graphics menu overlay: wrote %s (TAGAME.XXX %d bytes, COALESCED.INT %d bytes)'
          % (dst, len(tagame), len(ini)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
