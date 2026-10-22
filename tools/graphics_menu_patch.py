#!/usr/bin/env python3
"""Build the Graphics-menu overlay for the player's own 01.09 files (T065).

    tools/graphics_menu_patch.py <vfs dir> <overlay dir>

Reads <vfs>/dev_hdd0/game/NPUB30035/USRDIR/SARB/TAGAME/{COOKEDPS3/TAGAME.XXX, PS3TOC.TXT,
LOCALIZATION/COALESCED.INT}, writes the patched copies under <overlay>/game/NPUB30035/...
(what PS3_VFS_OVERLAY lays over the VFS). Nothing from the game is kept in this repo:
the edits are ours and the output goes to a git-ignored directory. docs/graphics-menu.md
says what each edit is and why.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from ue3 import coalesced, pkgwrite, props, upk   # noqa: E402

REL = 'game/NPUB30035/USRDIR/SARB/TAGAME'
TOC_TAGAME = '\\cookedps3\\tagame.xxx'
TOC_INT = '\\localization\\coalesced.int'

GRAPHICS_TEXT = 'Graphics'
GRAPHICS_DESC = 'Change the resolution, frame rate and other video options.'


def patch_coalesced(path):
    entries = coalesced.load(open(path, 'rb').read())
    for e in entries:
        if e[0].rstrip('\0').lower().endswith('\\int\\tagame.int'):
            e[1] = coalesced.section_add(e[1], 'MainMenuSceneContainer', [
                'GraphicsOptions="%s"' % GRAPHICS_TEXT,
                'GraphicsOptionsDesc="%s"' % GRAPHICS_DESC,
            ])
            return coalesced.dump(entries)
    raise KeyError('TAGame.int')


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


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    vfs, out = argv
    src = os.path.join(vfs, 'dev_hdd0', REL)
    dst = os.path.join(out, REL)
    pkg_path = os.path.join(src, 'COOKEDPS3', 'TAGAME.XXX')
    pkg = pkgwrite.Package(pkg_path)
    add_options_item(pkg)
    tagame = pkg.save()
    ini = patch_coalesced(os.path.join(src, 'LOCALIZATION', 'COALESCED.INT'))
    toc = open(os.path.join(src, 'PS3TOC.TXT'), 'rb').read().decode('latin-1')
    toc = pkgwrite.toc_set(toc, TOC_TAGAME, len(tagame))
    toc = pkgwrite.toc_set(toc, TOC_INT, len(ini))
    for rel, data in (('COOKEDPS3/TAGAME.XXX', tagame), ('LOCALIZATION/COALESCED.INT', ini),
                      ('PS3TOC.TXT', toc.encode('latin-1'))):
        path = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'wb').write(data)
    print('wrote %s: TAGAME.XXX %d bytes, COALESCED.INT %d bytes' % (dst, len(tagame), len(ini)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
