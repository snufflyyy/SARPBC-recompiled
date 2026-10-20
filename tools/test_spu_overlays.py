#!/usr/bin/env python3
"""Test MultiStream bank layout with synthetic SPU ELFs, never game data."""
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('overlays', Path(__file__).with_name('make_spu_overlays.py'))
ovl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ovl)


def fake_plugin(name, size, entry=0x98):
    elf = bytearray(0x100 + size)
    struct.pack_into('>II', elf, 0x18, entry, 52)
    struct.pack_into('>H', elf, 0x2C, 1)
    struct.pack_into('>8I', elf, 52, 1, 0x100, 0x80, 0x80, size, size, 5, 16)
    elf[0x100:0x110] = name.encode()[:16].ljust(16, b'!')
    struct.pack_into('>III', elf, 0x110, ovl.BI_R0, ovl.LNOP, 0x40800003)
    elf.extend(name.encode() + b'\0')
    return bytes(elf)


class OverlayBanksTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='sarpbc-overlay-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plugins = {
            'mstream_dsp_i3dl2.pic': fake_plugin('mstream_dsp_i3dl2.pic', 0x27C0),
            'mstream_dsp_para_eq.pic': fake_plugin('mstream_dsp_para_eq.pic', 0x690),
            'mstream_dsp_filter.pic': fake_plugin('mstream_dsp_filter.pic', 0x500, 0x90),
        }
        for i, (name, elf) in enumerate(self.plugins.items()):
            out = self.root / f'spu_test_{i}'
            out.mkdir()
            (out / 'image.elf').write_bytes(elf)

    def test_original_bank_is_unchanged(self):
        block, entries, sig, span = ovl.build_msdsp(self.root)
        self.assertEqual(span, 0x2E90)
        self.assertEqual(sig, block[:16])
        self.assertEqual(block[:0x27C0], ovl.text_segment(self.plugins['mstream_dsp_i3dl2.pic'])[2])
        self.assertEqual(block[0x27C0:0x2800], bytes(0x40))
        self.assertEqual(block[0x2800:], ovl.text_segment(self.plugins['mstream_dsp_para_eq.pic'])[2])
        for entry in (0x37010, 0x37018, 0x39810, 0x39818):
            self.assertIn(entry, entries)

    def test_filter_bank_has_its_own_image_at_the_same_ls_base(self):
        banks = ovl.BANKS
        self.assertEqual(len(banks), 2)
        names, ids = zip(*[(name, image) for name, image, _ in banks])
        self.assertEqual(len(set(names)), 2)
        self.assertEqual(len(set(ids)), 2)
        name, image, layout = banks[1]
        self.assertEqual(layout, [('mstream_dsp_filter.pic', 0)])
        self.assertEqual(banks[0][:2], (ovl.MSDSP_NAME, ovl.MSDSP_IMAGE_ID))
        block, entries, sig, span = ovl.build_msdsp(self.root, layout)
        self.assertEqual(block, ovl.text_segment(self.plugins['mstream_dsp_filter.pic'])[2])
        self.assertEqual(span, 0x500)
        self.assertEqual(sig, block[:16])
        self.assertNotEqual(sig, ovl.build_msdsp(self.root)[2])
        self.assertIn(0x37010, entries)
        self.assertIn(0x37018, entries)

    def test_generated_banks_are_not_treated_as_plugin_sources(self):
        for name, _, _ in ovl.BANKS:
            bank = self.root / name
            bank.mkdir()
            (bank / 'image.elf').write_bytes(fake_plugin('mstream_dsp_filter.pic', 0x100))
        self.assertEqual(ovl.find_plugins(self.root), self.plugins)

    def test_each_generated_constructor_registers_its_own_bank(self):
        def fake_lift(cmd, **kwargs):
            out = Path(cmd[cmd.index('-o') + 1])
            self.assertIn('--extra-funcs', cmd)
            (out / 'spu_recomp.c').write_text('#include "../../runtime/spu/spu_context.h"\n')
            (out / 'spu_recomp.h').write_text('#include "../../runtime/spu/spu_context.h"\n')
            return types.SimpleNamespace(returncode=0)

        wrapper = types.SimpleNamespace(wrap=lambda block, **kw: b'synthetic-elf' + block)
        with mock.patch.dict(sys.modules, wrap_spu_elf=wrapper), mock.patch.object(ovl.subprocess, 'run', fake_lift):
            output = self.root / 'private-build'
            before = ovl.find_plugins(self.root)
            for name, image, layout in ovl.BANKS:
                ovl.lift_bank(self.root, self.root / 'tools', name, image, layout, output)
                text = (output / name / 'spu_recomp.c').read_text()
                self.assertIn(f'spu_begin_image(0x{image:X})', text)
                self.assertIn(f'{name}_spu_recomp_register()', text)
                span = ovl.build_msdsp(self.root, layout)[3]
                self.assertIn(f'spu_overlay_register_sig_region(sig, 0x{span:X}u, 0x{image:X})', text)
                self.assertIn('#include "spu_context.h"', text)
                self.assertFalse((self.root / name).exists())
            self.assertEqual(ovl.find_plugins(self.root), before)

    def test_missing_filter_is_not_silently_ignored(self):
        (self.root / 'spu_test_2/image.elf').unlink()
        with self.assertRaisesRegex(SystemExit, 'mstream_dsp_filter.pic'):
            ovl.build_msdsp(self.root, [('mstream_dsp_filter.pic', 0)])

    def test_overlapping_layout_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, 'overlaps'):
            ovl.build_msdsp(self.root, [('mstream_dsp_i3dl2.pic', 0), ('mstream_dsp_para_eq.pic', 0x100)])


if __name__ == '__main__':
    unittest.main()
