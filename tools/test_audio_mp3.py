#!/usr/bin/env python3
"""Firmware-free tests of MultiStream's native MP3/SPU ABI.

Requires a C++20 compiler. ffmpeg/libmp3lame enables the synthetic tone round-trip;
the local-store boundary and metadata tests do not require an encoder or game data.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include "audio_mp3.cpp"
#include <cmath>
#include <fstream>
#include <iterator>
#include <sys/mman.h>
#include <unistd.h>

extern "C" {
void spu_begin_image(int) {}
void spu_register_function(uint32_t, void (*)(spu_context*)) {}
void spu_overlay_register_sig_region(const uint8_t[16], uint32_t, int) {}
void spu_indirect_branch(spu_context*) { abort(); }
SPU_THREAD_LOCAL void (*g_spu_trampoline_fn)(spu_context*) = nullptr;
}

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "line %d: %s\n", __LINE__, #x); exit(1); } } while (0)

struct Fixture {
    spu_context ctx{};
    uint8_t* mapping;
    size_t size = SPU_LS_SIZE + (size_t)sysconf(_SC_PAGESIZE);
    args_t a{0x1000, 0x4000, 0x4004, 0x20000, 0x10000, 0x11000,
             0x12000, 0x13000, 0x14000, 0x4008};
    Fixture() {
        mapping = (uint8_t*)mmap(nullptr, size, PROT_READ | PROT_WRITE,
                                MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        CHECK(mapping != MAP_FAILED);
        CHECK(mprotect(mapping + SPU_LS_SIZE, size - SPU_LS_SIZE, PROT_NONE) == 0);
        ctx.ls = mapping;
        ctx.host_depth = 1;
        ctx.gpr[0]._u32[0] = 0x1234;
    }
    ~Fixture() { munmap(mapping, size); }
    void call() {
        const uint32_t regs[] = { a.in, a.cons, a.prod, a.work, a.l_ov, a.r_ov,
                                  a.l_syn, a.r_syn, a.reserv, a.word };
        for (int i = 0; i < 10; ++i) ctx.gpr[i+3]._u32[0] = regs[i];
        standin_entry(&ctx);
        CHECK(ctx.pc == 0x1234);
        for (int i = 1; i < 4; ++i) CHECK(ctx.gpr[3]._u32[i] == ctx.gpr[3]._u32[0]);
    }
    void error() {
        ls_wr32(mapping, a.cons, 99);
        ls_wr32(mapping, a.prod, 99);
        call();
        CHECK(ctx.gpr[3]._u32[0] == 0xffffffffu);
        CHECK(ls_rd32(mapping, a.cons) == 0);
        CHECK(ls_rd32(mapping, a.prod) == 0);
    }
};

int main(int argc, char** argv) {
    CHECK(argc >= 2);
    Fixture f;
    auto ls = f.mapping;
    const std::string mode = argv[1];
    if (mode == "id3-edge") {
        // Four bytes are enough for a frame header, not a 10-byte ID3v2 header.
        f.a.in = SPU_LS_SIZE - 4;
        memcpy(ls + f.a.in, "ID3\4", 4);
        f.error();
    } else if (mode == "frame-edge") {
        f.a.in = SPU_LS_SIZE - 4;
        const uint8_t hdr[] = {0xff, 0xfb, 0x94, 0x00};
        memcpy(ls + f.a.in, hdr, 4);
        f.error();
    } else if (mode == "metadata") {
        memcpy(ls + f.a.in, "ID3\4\0\0\0\0\1\2", 10);
        f.call();
        CHECK(f.ctx.gpr[3]._u32[0] == 0);
        CHECK(ls_rd32(ls, f.a.cons) == 140);
        CHECK(ls_rd32(ls, f.a.prod) == 0);
        memcpy(ls + f.a.in, "TAG\0", 4);
        f.call();
        CHECK(ls_rd32(ls, f.a.cons) == 128);
        CHECK(ls_rd32(ls, f.a.prod) == 0);
    } else if (mode == "invalid") {
        memcpy(ls + f.a.in, "nope", 4);
        f.error();
    } else if (mode == "tone") {
        CHECK(argc == 3);
        std::ifstream in(argv[2], std::ios::binary);
        std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(in)), {});
        CHECK(bytes.size() > 4);
        dod3_mp3 reference{};
        const int first_bytes = dod3_mp3_frame_bytes(bytes.data(), nullptr);
        CHECK(first_bytes > 0 && (size_t)first_bytes <= bytes.size());
        // Two streams share the host thread but retain independent LS state.
        Fixture second;
        size_t pos = 0;
        int frames = 0, peak = 0;
        while (pos + 4 <= bytes.size()) {
            dod3_mp3_info info{};
            int n = dod3_mp3_frame_bytes(bytes.data() + pos, &info);
            CHECK(n >= 4 && pos + (size_t)n <= bytes.size());
            CHECK(n < 0x3000);
            int16_t pcm[2][1152]{};
            int16_t* out[] = { pcm[0], pcm[1] };
            CHECK(dod3_mp3_decode(&reference, bytes.data() + pos, out, &info) == info.samples);
            memcpy(ls + f.a.in, bytes.data() + pos, n);
            f.call();
            CHECK(f.ctx.gpr[3]._u32[0] == f.a.work + OUT_OFF);
            CHECK(ls_rd32(ls, f.a.cons) == (uint32_t)n);
            CHECK(ls_rd32(ls, f.a.prod) == (uint32_t)info.samples * 2);
            CHECK(ls_rd32(ls, f.a.word) == (uint32_t)(-18 * (info.samples/576) * (frames+1) & 15));
            for (int c = 0; c < info.channels; ++c) {
                auto p = ls + f.a.work + OUT_OFF + (c ? OUT_R_OFF : 0);
                for (int i = 0; i < info.samples; ++i) {
                    int16_t got = (int16_t)((p[2*i] << 8) | p[2*i+1]);
                    CHECK(got == pcm[c][i]);
                    if (abs(got) > peak) peak = abs(got);
                }
            }
            // Repeatedly restart a different stream between f's calls.
            memset(second.mapping, 0, SPU_LS_SIZE);
            memcpy(second.mapping + second.a.in, bytes.data(), first_bytes);
            second.call();
            pos += n;
            frames++;
        }
        CHECK(frames > 10 && peak > 100 && peak < 32000);
        printf("%d frames, peak %d, planar BE PCM and stream state match\n", frames, peak);
    } else return 2;
    return 0;
}
'''


class NativeMP3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.name != 'posix':
            raise unittest.SkipTest('guard-page fixture requires POSIX mmap')
        compiler = os.environ.get('CXX', 'clang++')
        if not shutil.which(compiler):
            raise unittest.SkipTest(f'{compiler} unavailable')
        cls.tmp = tempfile.TemporaryDirectory(prefix='sarpbc-audio-test-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.path = Path(cls.tmp.name)
        source = cls.path / 'harness.cpp'
        source.write_text(HARNESS)
        cls.exe = cls.path / 'harness'
        subprocess.run([compiler, '-std=c++20', '-O2', '-Wall', '-Wextra',
                        '-I' + str(ROOT / 'src/overrides'),
                        '-I' + str(ROOT / 'external/ps3recomp/runtime/spu'),
                        '-I' + str(ROOT / 'external/ps3recomp/include'),
                        str(source), str(ROOT / 'src/overrides/audio_mp3dec.cpp'),
                        '-o', str(cls.exe)], check=True)

    def run_case(self, *args):
        env = dict(os.environ, SARPBC_MP3_NATIVE='0')
        result = subprocess.run([str(self.exe), *args], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_truncated_id3_at_local_store_end(self):
        self.run_case('id3-edge')

    def test_truncated_frame_at_local_store_end(self):
        self.run_case('frame-edge')

    def test_metadata_consumed_without_output(self):
        self.run_case('metadata')

    def test_invalid_header_reports_error(self):
        self.run_case('invalid')

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required for synthetic MP3')
    def test_synthetic_tone_spu_abi(self):
        tone = self.path / 'tone.mp3'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'sine=frequency=440:duration=1:sample_rate=48000',
                        '-ac', '2', '-codec:a', 'libmp3lame', '-b:a', '128k',
                        '-write_xing', '0', '-id3v2_version', '0', '-y', str(tone)], check=True)
        self.run_case('tone', str(tone))


if __name__ == '__main__':
    unittest.main()
