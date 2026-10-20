#!/usr/bin/env python3
"""Synthetic native Edge-zlib HLE tests; no game data or firmware required."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include "edgezlib.cpp"
#include <algorithm>
#include <array>
#include <string>
#include <vector>

extern "C" {
uint8_t* vm_base;
uint32_t ppu_vm_size;
static hle_ctx_fn handler;
void ps3_hle_register_ctx(uint32_t nid, const char*, hle_ctx_fn fn) {
    if (nid != 0x8A85674D) abort();
    handler = fn;
}
static unsigned signals;
static uint32_t signal_ea;
static uint16_t signal_bits;
static int32_t signal_result;
int32_t cellSpursEventFlagSet(CellSpursEventFlag* flag, uint16_t bits) {
    signals++; signal_ea = (uint32_t)(uintptr_t)flag; signal_bits = bits;
    return signal_result;
}
}
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "line %d: %s\n", __LINE__, #x); return 1; } } while (0)
constexpr uint32_t queue = 0x100, request = 0x200, input = 0x400;
constexpr uint32_t output = 0x2000, counter = 0x300, event = 0x380;
alignas(16) std::array<uint8_t, 0x6000> memory;
void wr(uint32_t ea, uint32_t v) {
    for (int i = 0; i < 4; ++i) memory[ea+i] = (uint8_t)(v >> (24-8*i));
}
void descriptor(uint32_t insize, uint32_t outsize, bool inflate = true) {
    wr(queue + 0x10, 32);
    wr(request, input); wr(request+4, output);
    wr(request+8, insize); wr(request+12, outsize);
    wr(request+16, counter | (inflate ? 1u : 0u));
    wr(request+20, event); wr(request+24, 0x00420000);
    wr(counter, 1);
}
uint32_t call(uint32_t q = queue, uint32_t req = request) {
    ppu_context ctx{}; ctx.gpr[3] = q; ctx.gpr[4] = req;
    handler(&ctx); return (uint32_t)ctx.gpr[3];
}
std::vector<uint8_t> compressed(const std::string& text, bool finish) {
    z_stream z{};
    if (deflateInit2(&z, Z_DEFAULT_COMPRESSION, Z_DEFLATED, -15, 8, Z_DEFAULT_STRATEGY) != Z_OK) abort();
    std::vector<uint8_t> result(0x1000);
    z.next_in = (Bytef*)text.data(); z.avail_in = (uInt)text.size();
    z.next_out = result.data(); z.avail_out = (uInt)result.size();
    int rc = deflate(&z, finish ? Z_FINISH : Z_SYNC_FLUSH);
    if (rc != (finish ? Z_STREAM_END : Z_OK)) abort();
    result.resize(z.total_out); deflateEnd(&z); return result;
}
int main(int argc, char** argv) {
    CHECK(argc == 2);
    vm_base = memory.data(); ppu_vm_size = (uint32_t)memory.size();
    sarpbc_register_edgezlib(); CHECK(handler);
    const std::string mode = argv[1], text(4096, 'x');
    auto packed = compressed(text, mode != "unfinished");
    std::copy(packed.begin(), packed.end(), memory.begin()+input);
    descriptor((uint32_t)packed.size(), (uint32_t)text.size());
    if (mode == "unfinished") {
        CHECK(call() == 0x8041090Fu);
        CHECK(signals == 0 && be32(counter) == 1);
    } else if (mode == "inflate") {
        CHECK(call() == 0);
        CHECK(!memcmp(memory.data()+output, text.data(), text.size()));
        CHECK(be32(counter) == 0 && signals == 1);
        CHECK(signal_ea == event && signal_bits == 0x42);
    } else if (mode == "copy") {
        memcpy(memory.data()+input, "overlap", 7);
        descriptor(7, 7, false); wr(request+4, input+1);
        CHECK(call() == 0);
        CHECK(!memcmp(memory.data()+input+1, "overlap", 7));
        CHECK(be32(counter) == 0 && signals == 1);
    } else if (mode == "skips" || mode == "empty-output") {
        const std::string body = mode == "skips" ? text : "";
        const std::string all = std::string(UINT16_MAX, 'a') + body + std::string(UINT16_MAX, 'b');
        packed = compressed(all, true);
        std::copy(packed.begin(), packed.end(), memory.begin()+input);
        descriptor((uint32_t)packed.size(), (uint32_t)body.size());
        wr(request+24, 0x0042ffff); wr(request+28, 0xffff0000);
        CHECK(call() == 0);
        CHECK(!memcmp(memory.data()+output, body.data(), body.size()));
        CHECK(memory[output+body.size()] == 0);
        CHECK(be32(counter) == 0 && signals == 1);
    } else if (mode == "empty") {
        packed = compressed("", true);
        std::copy(packed.begin(), packed.end(), memory.begin()+input);
        descriptor((uint32_t)packed.size(), 0);
        CHECK(call() == 0 && signals == 1 && be32(counter) == 0);
    } else if (mode == "truncated" || mode == "invalid-stream") {
        if (mode == "truncated") wr(request+8, (uint32_t)packed.size()-1);
        else memset(memory.data()+input, 0xff, packed.size());
        CHECK(call() == 0x8041090fu);
        CHECK(signals == 0 && be32(counter) == 1);
    } else if (mode == "wrong-length" || mode == "excess-output") {
        wr(request+12, (uint32_t)text.size() + (mode == "wrong-length" ? 1 : -1));
        CHECK(call() == 0x8041090fu);
        CHECK(signals == 0 && be32(counter) == 1);
        if (mode == "excess-output") CHECK(memory[output+text.size()-1] == 0);
    } else if (mode == "flag-error") {
        signal_result = (int32_t)0x8041090fu;
        CHECK(call() == 0x8041090fu && signals == 1);
    } else if (mode == "no-flag") {
        wr(request+20, 0);
        CHECK(call() == 0 && signals == 0 && be32(counter) == 0);
    } else if (mode == "address-limit") {
        // Arithmetic-only boundary checks: no high guest address is dereferenced.
        ppu_vm_size = 0;
        CHECK(guest_range(0xfffffff0u, 16));
        CHECK(!guest_range(0xfffffff0u, 17));
        CHECK(!guest_range(0x10, UINT64_MAX));
        CHECK(!guest_range(0, 4));
        CHECK(guest_range(0, 0));
    } else if (mode == "full-space") {
        ppu_vm_size = 0;
        CHECK(call() == 0 && signals == 1);
    } else if (mode == "copy-input") {
        ppu_vm_size = 0x4000;
        descriptor(1, 32, false); wr(request, 0x3ff0);
        CHECK(call() == 0x80410902u);
        CHECK(signals == 0 && be32(counter) == 1 && memory[output] == 0);
    } else if (mode == "unsupported") {
        wr(queue+0x10, 16);
        CHECK(call() == 0x8041090fu);
        CHECK(signals == 0 && be32(counter) == 1);
    } else if (mode == "null-descriptor") {
        CHECK(call(queue, 0) == 0x80410902u);
        CHECK(signals == 0 && be32(counter) == 1);
    } else if (mode == "counter") {
        wr(counter, 2);
        CHECK(call() == 0 && be32(counter) == 1 && signals == 0);
        CHECK(call() == 0 && be32(counter) == 0 && signals == 1);
    } else if (mode == "no-counter") {
        wr(request+16, 1);
        CHECK(call() == 0 && signals == 1 && be32(counter) == 1);
    } else if (mode == "bounds") {
        // Padding stays host-accessible: even a regression need not fault.
        ppu_vm_size = 0x4000;
        wr(request+4, 0x3ff0);
        CHECK(call() == 0x80410902u);
        CHECK(signals == 0 && be32(counter) == 1 && memory[0x3ff0] == 0);
    } else if (mode == "descriptor") {
        ppu_vm_size = 0x4000;
        memcpy(memory.data()+0x3ff0, memory.data()+request, 32);
        CHECK(call(queue, 0x3ff0) == 0x80410902u);
        CHECK(signals == 0 && be32(counter) == 1);
    } else if (mode == "queue") {
        ppu_vm_size = 0x4000; wr(0x4008, 32);
        CHECK(call(0x3ff8) == 0x80410902u);
        CHECK(signals == 0 && be32(counter) == 1);
    } else if (mode == "input") {
        ppu_vm_size = 0x4000;
        std::copy(packed.begin(), packed.end(), memory.begin()+0x3ff8);
        wr(request, 0x3ff8);
        CHECK(call() == 0x80410902u);
        CHECK(signals == 0 && be32(counter) == 1 && memory[output] == 0);
    } else if (mode == "flag") {
        ppu_vm_size = 0x3fff; wr(request+20, 0x3f80);
        CHECK(call() == 0x80410902u);
        CHECK(signals == 0 && be32(counter) == 1 && memory[output] == 0);
    } else if (mode == "zero-counter") {
        wr(counter, 0);
        CHECK(call() == 0x8041090fu);
        CHECK(signals == 0 && be32(counter) == 0 && memory[output] == 0);
    } else if (mode == "unaligned-counter") {
        wr(request+16, (counter+2) | 1);
        CHECK(call() == 0x80410910u);
        CHECK(signals == 0 && memory[output] == 0);
    } else if (mode == "overflow") {
        // The old wrapped temporary is only 16 bytes; no large allocation.
        ppu_vm_size = 0;
        wr(request+4, 0x10); wr(request+12, 0xfffffff0u);
        wr(request+24, 0x00420020);
        CHECK(call() == 0x80410902u);
        CHECK(signals == 0 && be32(counter) == 1);
    } else return 2;
    return 0;
}
'''


class EdgeZlibTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = os.environ.get('CXX', 'clang++')
        if not shutil.which(compiler):
            raise unittest.SkipTest(f'{compiler} unavailable')
        cls.tmp = tempfile.TemporaryDirectory(prefix='sarpbc-zlib-test-')
        cls.addClassCleanup(cls.tmp.cleanup)
        path = Path(cls.tmp.name)
        (path / 'ppu_recomp.h').write_text('#include <stdint.h>\nstruct ppu_context { uint64_t gpr[32]; };\n')
        (path / 'harness.cpp').write_text(HARNESS)
        cls.exe = path / 'test'
        subprocess.run([compiler, '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I' + str(path), '-I' + str(ROOT / 'src/overrides'),
                        str(path / 'harness.cpp'), '-lz', '-o', str(cls.exe)], check=True)

    def run_case(self, case):
        result = subprocess.run([str(self.exe), case], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_valid_inflate_completes_once(self):
        self.run_case('inflate')

    def test_unfinished_stream_does_not_complete(self):
        self.run_case('unfinished')

    def test_overlapping_copy_completes(self):
        self.run_case('copy')

    def test_counter_only_signals_on_zero(self):
        self.run_case('counter')
        self.run_case('no-counter')

    def test_rejects_out_of_backing_before_access(self):
        for case in ('bounds', 'descriptor', 'queue', 'input', 'flag'):
            with self.subTest(case=case):
                self.run_case(case)

    def test_counter_cannot_underflow(self):
        self.run_case('zero-counter')

    def test_counter_must_be_aligned(self):
        self.run_case('unaligned-counter')

    def test_skip_size_cannot_wrap(self):
        self.run_case('overflow')

    def test_maximum_prefix_suffix_and_empty_output(self):
        self.run_case('skips')
        self.run_case('empty-output')
        self.run_case('empty')

    def test_wrong_decoded_length_does_not_complete(self):
        self.run_case('wrong-length')
        self.run_case('excess-output')

    def test_truncated_and_invalid_streams_do_not_complete(self):
        self.run_case('truncated')
        self.run_case('invalid-stream')

    def test_event_errors_are_not_hidden(self):
        self.run_case('flag-error')
        self.run_case('no-flag')

    def test_full_address_space_mapping_convention(self):
        self.run_case('full-space')

    def test_guest_limit_arithmetic_without_high_address_access(self):
        self.run_case('address-limit')

    def test_copy_checks_actual_read_span(self):
        self.run_case('copy-input')

    def test_unsupported_queue_and_missing_descriptor(self):
        self.run_case('unsupported')
        self.run_case('null-descriptor')


if __name__ == '__main__':
    unittest.main()
