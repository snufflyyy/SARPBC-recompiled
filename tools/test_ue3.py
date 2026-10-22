#!/usr/bin/env python3
"""tools/ue3: coalesced files, tagged properties, script trees and chunk packing on synthetic data
(nothing from the game)."""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue3 import coalesced, pkgwrite, props, script, upk   # noqa: E402


class CoalescedTest(unittest.TestCase):
    def test_round_trip_and_section_add(self):
        entries = [['..\\A\\TAGame.int\0', '[One]\nA="x"\n[Two]\nB="y"\n\0', False, False],
                   ['..\\A\\Wide.int\0', '[W]\nk="é"\n\0', True, True]]
        raw = coalesced.dump(entries)
        self.assertEqual(struct.unpack_from('>I', raw, 0)[0], 4)
        self.assertEqual(coalesced.dump(coalesced.load(raw)), raw)
        text = coalesced.section_add(entries[0][1], 'One', ['C="z"'])
        self.assertEqual(text, '[One]\nA="x"\nC="z"\n[Two]\nB="y"\n\0')
        with self.assertRaises(KeyError):
            coalesced.section_add(entries[0][1], 'Missing', [])


NAMES = ['None', 'ItemText', 'StrProperty', 'StateName', 'NameProperty', 'bFadeable', 'BoolProperty']


def tag(name, typ, value, extra=b''):
    return (struct.pack('>II', NAMES.index(name), 0) + struct.pack('>II', NAMES.index(typ), 0)
            + struct.pack('>ii', len(value), 0) + extra + value)


class PropsTest(unittest.TestCase):
    def test_struct_array_edit(self):
        none = struct.pack('>II', 0, 0)
        elem = tag('ItemText', 'StrProperty', props.fstring_value('hello')) + \
            tag('StateName', 'NameProperty', struct.pack('>II', 1, 0)) + \
            tag('bFadeable', 'BoolProperty', b'', struct.pack('>I', 1)) + none
        value = struct.pack('>I', 1) + elem
        els = props.parse_struct_array(value, NAMES)
        self.assertEqual([t['pname'] for t in els[0]], ['ItemText', 'StateName', 'bFadeable'])
        self.assertEqual(props.read_fstring(els[0][0]['value']), 'hello')
        self.assertEqual(props.encode_struct_array(els, 0), value)
        els.append([dict(t) for t in els[0]])
        els[1][0]['value'] = props.fstring_value('second')
        again = props.parse_struct_array(props.encode_struct_array(els, 0), NAMES)
        self.assertEqual([props.read_fstring(e[0]['value']) for e in again], ['hello', 'second'])

    def test_body_round_trip(self):
        body = struct.pack('>I', 7) + tag('ItemText', 'StrProperty', props.fstring_value('a')) + \
            struct.pack('>II', 0, 0) + b'tail'
        b = props.parse_body(body, 0, len(body), NAMES)
        self.assertEqual(b.build(), body)
        b.get('ItemText')['value'] = props.fstring_value('longer text')
        self.assertIn(b'longer text', b.build())


class ScriptTest(unittest.TestCase):
    def test_parse_encode(self):
        # a = 1 (IntOne into a local ref), then a string constant statement, then return nothing, end
        code = (bytes([0x0F, 0x00]) + struct.pack('>i', 5) + bytes([0x26])
                + bytes([0x1F]) + b'?loc:x\0' + bytes([0x04, 0x0B, 0x53]))
        ps = script.Parser(code, 0, len(code))
        stmts = []
        while True:
            n = ps.expr()
            stmts.append(n)
            if n.op == 0x53:
                break
        enc, mem = script.encode(stmts)
        self.assertEqual(enc, code)
        self.assertEqual(mem, ps.m)
        stmts[1].parts[0] = ('raw', b'new text\0')
        enc, mem = script.encode(stmts)
        self.assertIn(b'new text\0', enc)
        self.assertEqual(mem, ps.m + len('new text') - len('?loc:x'))


class ChunkTest(unittest.TestCase):
    def test_compress_chunk_inflates(self):
        data = os.urandom(70000) + b'\0' * 5000
        blob = pkgwrite.compress_chunk(data)
        self.assertEqual(upk.chunk_stream(blob, 0), data)
        self.assertEqual(pkgwrite.csz_of(blob, 0), len(blob))

    def test_toc_set(self):
        toc = '10 0 0 ..\\X\\A.xxx 0\r\n20 0 0 ..\\X\\TAGame.xxx 0\r\n'
        self.assertEqual(pkgwrite.toc_set(toc, '\\tagame.xxx', 99), '10 0 0 ..\\X\\A.xxx 0\r\n99 0 0 ..\\X\\TAGame.xxx 0\r\n')
        with self.assertRaises(KeyError):
            pkgwrite.toc_set(toc, '\\none.xxx', 1)


class EngineIniTest(unittest.TestCase):
    INI = ('[Engine.GameEngine]\r\nMaxSmoothedFrameRate=60\r\n[SystemSettings]\r\nMaxAnisotropy=4\r\nTrilinear=false\r\n'
           'TEXTUREGROUP_World=(MinLODSize=128,MaxLODSize=1024,LODBias=0)\r\n'
           'TEXTUREGROUP_UI=(MinLODSize=128,MaxLODSize=1024, LODBias=0)\r\n[Engine.Client]\r\nDisplayGamma=2.2\r\n')

    def patched(self, **env):
        import tempfile
        import graphics_menu_patch as g
        raw = coalesced.dump([['..\\PS3-TAEngine.ini\0', self.INI + '\0', False, False]])
        saved = {k: os.environ.pop(k, None) for k in list(g.ENV.values()) + ['SARPBC_GFX_FILE']}
        os.environ['SARPBC_GFX_FILE'] = '/nonexistent/graphics.ini'
        os.environ.update(env)
        try:
            with tempfile.NamedTemporaryFile() as f:
                f.write(raw)
                f.flush()
                self.assertEqual(g.engine_ini_wanted(), bool(env))
                return coalesced.load(g.patch_engine_ini(f.name)) if env else None
        finally:
            for k in list(g.ENV.values()) + ['SARPBC_GFX_FILE']:
                os.environ.pop(k, None)
                if saved.get(k) is not None:
                    os.environ[k] = saved[k]

    def test_defaults_ship_no_ini(self):
        self.assertIsNone(self.patched())

    def test_settings_edit_the_ini(self):
        t = self.patched(SARPBC_UNLOCK_FPS='1', SARPBC_BRIGHTNESS='4')[0][1]
        self.assertIn('MaxSmoothedFrameRate=1000', t)
        self.assertIn('DisplayGamma=2.800000', t)
        # texture filtering and quality are live in the sampler now: the INI keeps the game's values
        self.assertIn('MaxAnisotropy=4', t)
        self.assertIn('LODBias=0', t)


if __name__ == '__main__':
    unittest.main()
