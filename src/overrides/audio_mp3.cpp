/*
 * MultiStream's MP3 decoder, natively, behind a stand-in flashMP3.pic.
 *
 * Ported from Drakengard 3's port: soyjxck/dod3-recomp src/apu/mp3_native.c
 * and the `standin` part of tools/make_spu_overlays.py, commit 96df4c3
 * (MIT, Copyright (c) 2026 soyjxck and the dod3-recomp contributors; the
 * licence text is in audio_mp3dec.h). What changed for SARPBC: the stand-in
 * is built and served at start-up instead of from a generated header, the
 * entry is registered as a native SPU function with an overlay signature
 * instead of through dod3's SPU hook table, and the modes that compare
 * against Sony's lifted decoder are gone (they need the firmware).
 *
 * MultiStream (statically linked into the EBOOT; its mixer is SPU image 0 on
 * 01.09, sha e33837bb..., fp C1759183E2FF7448) decodes MP3 streams with the
 * firmware's /dev_flash/sys/external/flashMP3.pic. The PPU reads the whole
 * file into a buffer (01.09 func_0082E690), parses its section table
 * (func_00835588) into a descriptor {+0 file EA, +4 body EA (lowest alloc
 * sh_offset), +8 lowest sh_addr, +C body size, +10 e_entry, +14/+18 bss},
 * and the mixer GETs the body into its local store and calls the entry.
 * Without the file the PPU prints "Multistream: mp3 failed to load MP3
 * codec (are you using the correct flash?)" and the mixer's body GET has
 * size 0. We ship no firmware, so:
 *
 *   1. At start-up we write our own stand-in, an SPU ELF of the same shape
 *      (alloc sections from va 0x80: a 16-byte .SpuGUID, a 16-byte .text
 *      whose entry is `bi $r0`, padding to 1 KB), to
 *      <exe dir>/dev_flash/sys/external/flashMP3.pic and point
 *      PS3_DEV_FLASH there (unless the user set PS3_DEV_FLASH). Nothing of
 *      Sony's is in it.
 *   2. The entry's local-store address gets a native SPU function under an
 *      image id of our own, made resident by the body's 16-byte signature
 *      when the mixer GETs it (spu_overlay_register_sig_region).
 *   3. That function is the firmware's decodeFrame on our decoder
 *      (audio_mp3dec.cpp, dod3's).
 *
 * decodeFrame(r3 frame, r4 &consumed, r5 &produced, r6 work area, r7..r11
 * stream state, r12 &word), as dod3 documented the firmware decoder:
 *   - *consumed = *produced = 0, and the work area's 0x5800 bytes cleared;
 *   - "ID3" at the frame: an ID3v2 tag, skipped (consumed = 10 + its size;
 *     128 if the version byte is 1); "TAG": 128 bytes skipped. Returns 0.
 *   - a header it cannot parse: returns -1 (the mixer reports an error).
 *   - otherwise one frame: consumed = its length, the PCM as 16-bit big-
 *     endian planar channels at r6+0x900 (left) and r6+0x1900 (right),
 *     produced = bytes per channel (2 x samples), *r12 stepped, and returns
 *     r6+0x900. A Xing/Info header frame is decoded the same but reports
 *     produced = -1, so nothing of it is played.
 * The stream state lives in local store, in regions the mixer DMAs in and
 * out around each stream's call: r9 (0x880) header + left synthesis
 * history, r7 (0x900) left overlap, r11 (0x200) bit reservoir, r10/r8 the
 * right channel's. Ours keeps its own state there (host byte order, behind a
 * magic word); a region without the magic is a stream start.
 *
 * The firmware ABI is the firmware's, not the game's, so it is the same for
 * every MultiStream version; only where the mixer puts the body could
 * differ (dod3's 2013 MultiStream and our 2008 one both use LS 0x1A900:
 * kBodyLsa below).
 *
 * Environment:
 *   SARPBC_MP3_NATIVE=0  do not serve or register the stand-in (debugging:
 *                        PS3_DEV_FLASH / the runtime default then decide).
 *   SARPBC_MP3_LSA=<hex> override kBodyLsa (another MultiStream build).
 *   SARPBC_MP3_TRACE=<n> log the first n decodeFrame calls.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <atomic>
#include <string>
#include <vector>
#include <sys/stat.h>
#ifdef _WIN32
#include <direct.h>
#include <windows.h>
#else
#include <unistd.h>
#endif

#include "spu_context.h"
#include "audio_mp3dec.h"

extern "C" {
void spu_begin_image(int image_id);
void spu_register_function(uint32_t addr, void (*fn)(spu_context*));
void spu_overlay_register_sig_region(const uint8_t sig[16], uint32_t span, int image_id);
}

namespace {

/* ---- the stand-in ------------------------------------------------------------ */

constexpr char kGuid[16] = { 'S', 'A', 'R', 'P', 'B', 'C', ' ', 'n', 'a', 't', ' ', 'm', 'p', '3', 0, 0 };
constexpr uint32_t kVaBase = 0x80;      /* lowest alloc sh_addr: the body starts here */
constexpr uint32_t kBodyOff = 0x100;    /* file offset of va 0x80, as in Sony's file */
constexpr uint32_t kBodySize = 0x400;   /* >= 512: the runtime matches signatures only in GETs that big */
constexpr uint32_t kEntryVa = 0x90;     /* .text, right after the GUID */

/* Where the mixer places va 0x80: LS 0x1A900, the same as dod3's MultiStream.
 * 01.09 mixer (image 0): the descriptor goes to LS 0x1A880 (= 0x1A900 -
 * 0x80), and decodeFrame is called at SPU 0x6E2C (bisl to the word at LS
 * 0x3C4B0) with r6 = 0x2C900 (work area), r9 = 0x34100 (left state),
 * r12 = 0x37018: the register layout dod3 documented for the firmware's
 * decodeFrame. */
constexpr uint32_t kBodyLsa = 0x1A900;
constexpr int kImageId = 0x4D503301;    /* "MP3" 1: an id no lifted image uses */

void put16(std::vector<uint8_t>& v, size_t o, uint32_t x) { v[o] = (uint8_t)(x >> 8); v[o + 1] = (uint8_t)x; }
void put32(std::vector<uint8_t>& v, size_t o, uint32_t x)
{
    v[o] = (uint8_t)(x >> 24); v[o + 1] = (uint8_t)(x >> 16); v[o + 2] = (uint8_t)(x >> 8); v[o + 3] = (uint8_t)x;
}

/* An SPU ELF of flashMP3.pic's shape: one PT_LOAD (va 0x80, 1 KB) holding
 * .SpuGUID, .text and .rodata (padding), then .shstrtab and the section
 * headers. The PPU parser (func_00835588) reads e_machine, the section
 * table and e_entry; nothing else. */
std::vector<uint8_t> build_standin()
{
    static const char shstr[] = "\0.SpuGUID\0.text\0.rodata\0.shstrtab";   /* names at 1, 10, 16, 24 */
    const uint32_t shstr_size = sizeof shstr;   /* includes the final NUL */
    const uint32_t shstr_off = kBodyOff + kBodySize;
    const uint32_t sh_off = (shstr_off + shstr_size + 3) & ~3u;
    std::vector<uint8_t> f(sh_off + 5 * 40, 0);

    static const uint8_t ident[8] = { 0x7F, 'E', 'L', 'F', 1 /* 32-bit */, 2 /* BE */, 1, 0 };
    memcpy(f.data(), ident, sizeof ident);
    put16(f, 0x10, 2);          /* ET_EXEC */
    put16(f, 0x12, 0x17);       /* EM_SPU */
    put32(f, 0x14, 1);
    put32(f, 0x18, kEntryVa);
    put32(f, 0x1C, 52);         /* e_phoff */
    put32(f, 0x20, sh_off);
    put16(f, 0x28, 52);         /* e_ehsize */
    put16(f, 0x2A, 32);         /* e_phentsize */
    put16(f, 0x2C, 1);
    put16(f, 0x2E, 40);         /* e_shentsize */
    put16(f, 0x30, 5);
    put16(f, 0x32, 4);          /* e_shstrndx */

    /* PT_LOAD R+X: file 0x100.. -> va 0x80.. */
    const uint32_t ph[8] = { 1, kBodyOff, kVaBase, kVaBase, kBodySize, kBodySize, 5, 0x80 };
    for (int i = 0; i < 8; i++) put32(f, 52 + 4 * i, ph[i]);

    memcpy(&f[kBodyOff], kGuid, 16);
    /* .text: bi $r0 ; nop ; lnop ; nop. Never executed: the native function
     * registered at its address runs instead. */
    const uint32_t text[4] = { 0x35000000, 0x40200000, 0x00200000, 0x40200000 };
    for (int i = 0; i < 4; i++) put32(f, kBodyOff + 16 + 4 * i, text[i]);
    memcpy(&f[shstr_off], shstr, shstr_size);

    /* name, type, flags, addr, offset, size, link, info, align, entsize */
    const uint32_t sh[5][10] = {
        { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
        { 1, 1, 6, kVaBase, kBodyOff, 16, 0, 0, 16, 0 },
        { 10, 1, 6, kVaBase + 16, kBodyOff + 16, 16, 0, 0, 16, 0 },
        { 16, 1, 2, kVaBase + 32, kBodyOff + 32, kBodySize - 32, 0, 0, 16, 0 },
        { 24, 3, 0, 0, shstr_off, shstr_size, 0, 0, 1, 0 },
    };
    for (int s = 0; s < 5; s++)
        for (int i = 0; i < 10; i++) put32(f, sh_off + 40 * s + 4 * i, sh[s][i]);
    return f;
}

std::string exe_dir()
{
#ifdef _WIN32
    char buf[4096];
    DWORD n = GetModuleFileNameA(NULL, buf, sizeof buf);
    std::string p(buf, n);
    size_t k = p.find_last_of("\\/");
#else
    char buf[4096];
    ssize_t n = readlink("/proc/self/exe", buf, sizeof buf - 1);
    if (n <= 0) return ".";
    std::string p(buf, (size_t)n);
    size_t k = p.find_last_of('/');
#endif
    return k == std::string::npos ? std::string(".") : p.substr(0, k);
}

void make_dirs(const std::string& path)
{
    for (size_t i = 1; i <= path.size(); i++) {
        if (i == path.size() || path[i] == '/') {
            std::string d = path.substr(0, i);
#ifdef _WIN32
            _mkdir(d.c_str());
#else
            mkdir(d.c_str(), 0755);
#endif
        }
    }
}

/* Write the stand-in under <exe dir>/dev_flash and point PS3_DEV_FLASH at it,
 * unless the user chose a dev_flash. Rewritten each start (it is 1.6 KB), so
 * a stale or foreign file there is never what loads. */
void serve_standin()
{
    const char* fw = getenv("PS3_DEV_FLASH");
    if (fw && *fw) {
        fprintf(stderr, "[mp3] PS3_DEV_FLASH=%s set by the user: flashMP3.pic comes from there, not our stand-in\n", fw);
        return;
    }
    /* Beside the executable first; a read-only install directory falls back to
     * the user's cache directory. */
    std::vector<std::string> roots{exe_dir() + "/dev_flash"};
#ifndef _WIN32
    if (const char* xdg = getenv("XDG_CACHE_HOME"); xdg && *xdg) roots.push_back(std::string(xdg) + "/sarpbc/dev_flash");
    else if (const char* home = getenv("HOME"); home && *home) roots.push_back(std::string(home) + "/.cache/sarpbc/dev_flash");
#else
    if (const char* tmp = getenv("TEMP"); tmp && *tmp) roots.push_back(std::string(tmp) + "\\sarpbc\\dev_flash");
#endif
    const std::vector<uint8_t> pic = build_standin();
    std::string root, path;
    for (const std::string& candidate : roots) {
        const std::string dir = candidate + "/sys/external";
        make_dirs(dir);
        const std::string p = dir + "/flashMP3.pic";
        FILE* out = fopen(p.c_str(), "wb");
        const bool ok = out && fwrite(pic.data(), 1, pic.size(), out) == pic.size();
        if (out) fclose(out);
        if (ok) { root = candidate; path = p; break; }
        fprintf(stderr, "[mp3] cannot write the stand-in %s\n", p.c_str());
    }
    if (root.empty()) {
        fprintf(stderr, "[mp3] no writable place for the stand-in: MultiStream gets no MP3 decoder\n");
        return;
    }
#ifdef _WIN32
    _putenv_s("PS3_DEV_FLASH", root.c_str());
#else
    setenv("PS3_DEV_FLASH", root.c_str(), 1);
#endif
    fprintf(stderr, "[mp3] stand-in flashMP3.pic (%zu bytes, our native decoder) served from %s\n", pic.size(),
            root.c_str());
}

/* ---- decodeFrame, natively (dod3 mp3_native.c) ---------------------------------- */

constexpr uint32_t WORK_BYTES = 0x5800u;
constexpr uint32_t OUT_OFF = 0x900u;
constexpr uint32_t OUT_R_OFF = 0x1000u;
constexpr uint32_t STATE_MAGIC = 0x444D3331u;   /* "DM31", as dod3: the same state layout */

inline uint32_t ls_rd32(const uint8_t* ls, uint32_t a)
{
    const uint8_t* p = ls + (a & SPU_LS_MASK & ~3u);
    return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3];
}
inline void ls_wr32(uint8_t* ls, uint32_t a, uint32_t v)
{
    uint8_t* p = ls + (a & SPU_LS_MASK & ~3u);
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);
    p[3] = (uint8_t)v;
}
inline bool ls_ok(uint32_t a, uint32_t n) { return a <= SPU_LS_SIZE && n <= SPU_LS_SIZE - a; }

struct args_t {
    uint32_t in, cons, prod, work, l_syn, l_ov, reserv, r_syn, r_ov, word;
};

void get_args(const spu_context* ctx, args_t* a)
{
    a->in = ctx->gpr[3]._u32[0] & SPU_LS_MASK;
    a->cons = ctx->gpr[4]._u32[0] & SPU_LS_MASK;
    a->prod = ctx->gpr[5]._u32[0] & SPU_LS_MASK;
    a->work = ctx->gpr[6]._u32[0] & SPU_LS_MASK;
    a->l_ov = ctx->gpr[7]._u32[0] & SPU_LS_MASK;
    a->r_ov = ctx->gpr[8]._u32[0] & SPU_LS_MASK;
    a->l_syn = ctx->gpr[9]._u32[0] & SPU_LS_MASK;
    a->r_syn = ctx->gpr[10]._u32[0] & SPU_LS_MASK;
    a->reserv = ctx->gpr[11]._u32[0] & SPU_LS_MASK;
    a->word = ctx->gpr[12]._u32[0] & SPU_LS_MASK;
}

bool args_ok(const args_t* a)
{
    return ls_ok(a->in, 4) && ls_ok(a->cons, 4) && ls_ok(a->prod, 4) && ls_ok(a->work, WORK_BYTES) &&
           ls_ok(a->l_syn, 0x880) && ls_ok(a->l_ov, 0x900) && ls_ok(a->reserv, 0x200) && ls_ok(a->r_syn, 0x880) &&
           ls_ok(a->r_ov, 0x900) && ls_ok(a->word, 4);
}

struct state_hdr {
    uint32_t magic;
    int32_t synth_pos, reserv_len, nch;
};

void state_load(const uint8_t* ls, const args_t* a, int nch, dod3_mp3* d)
{
    state_hdr h;
    memcpy(&h, ls + a->l_syn, sizeof h);
    if (h.magic != STATE_MAGIC || h.reserv_len < 0 || h.reserv_len > 511) {
        memset(d, 0, sizeof *d);   /* a stream start */
        return;
    }
    d->synth_pos = h.synth_pos & 15;
    d->reserv_len = h.reserv_len;
    memcpy(d->ch[0].synth, ls + a->l_syn + sizeof h, sizeof d->ch[0].synth);
    memcpy(d->ch[0].overlap, ls + a->l_ov, sizeof d->ch[0].overlap);
    memcpy(d->reserv, ls + a->reserv, sizeof d->reserv);
    if (nch == 2 && h.nch == 2) {
        memcpy(d->ch[1].synth, ls + a->r_syn, sizeof d->ch[1].synth);
        memcpy(d->ch[1].overlap, ls + a->r_ov, sizeof d->ch[1].overlap);
    } else {
        memset(&d->ch[1], 0, sizeof d->ch[1]);
    }
}

void state_save(uint8_t* ls, const args_t* a, int nch, const dod3_mp3* d)
{
    const state_hdr h = { STATE_MAGIC, d->synth_pos, d->reserv_len, nch };
    memcpy(ls + a->l_syn, &h, sizeof h);
    memcpy(ls + a->l_syn + sizeof h, d->ch[0].synth, sizeof d->ch[0].synth);
    memcpy(ls + a->l_ov, d->ch[0].overlap, sizeof d->ch[0].overlap);
    memcpy(ls + a->reserv, d->reserv, sizeof d->reserv);
    if (nch == 2) {
        memcpy(ls + a->r_syn, d->ch[1].synth, sizeof d->ch[1].synth);
        memcpy(ls + a->r_ov, d->ch[1].overlap, sizeof d->ch[1].overlap);
    }
}

struct result_t {
    uint32_t ret, cons, prod;   /* what the mixer sees */
    int samples, nch;
    int16_t pcm[2][1152];
};

void decode_frame(uint8_t* ls, const args_t* a, dod3_mp3* d, result_t* r)
{
    const uint8_t* f = ls + a->in;
    r->ret = 0;
    r->cons = 0;
    r->prod = 0;
    r->samples = 0;
    r->nch = 0;
    if (f[0] == 'I' && f[1] == 'D' && f[2] == '3') {
        /* args_ok covers the four-byte frame header, not ID3v2's size field.
         * A truncated tag at LS end must use the decode-error ABI, not read
         * beyond the local-store allocation. ID3v1 needs only the prefix. */
        if (f[3] != 1 && !ls_ok(a->in, 10)) {
            r->ret = 0xFFFFFFFFu;
            return;
        }
        r->cons = f[3] == 1 ? 128u
                            : 10u + ((uint32_t)(f[6] & 0x7F) << 21 | (uint32_t)(f[7] & 0x7F) << 14 |
                                     (uint32_t)(f[8] & 0x7F) << 7 | (f[9] & 0x7F));
        return;
    }
    if (f[0] == 'T' && f[1] == 'A' && f[2] == 'G') {
        r->cons = 128;
        return;
    }
    dod3_mp3_info info;
    const int bytes = dod3_mp3_frame_bytes(f, &info);
    int16_t* out[2] = { r->pcm[0], r->pcm[1] };
    if (!bytes || !ls_ok(a->in, (uint32_t)bytes) || dod3_mp3_decode(d, f, out, &info) < 0) {
        r->ret = 0xFFFFFFFFu;
        return;
    }
    /* The firmware looks for a Xing/Info tag where an MPEG-1 frame's main
     * data would start, without allowing for a CRC. */
    const uint8_t* x = f + 4 + (info.channels == 1 ? 17 : 32);
    const int xing = (x[0] == 'X' && x[1] == 'i' && x[2] == 'n' && x[3] == 'g') ||
                     (x[0] == 'I' && x[1] == 'n' && x[2] == 'f' && x[3] == 'o');
    r->cons = (uint32_t)bytes;
    r->prod = xing ? 0xFFFFFFFFu : (uint32_t)(2 * info.samples);
    r->ret = a->work + OUT_OFF;
    r->samples = info.samples;
    r->nch = info.channels;
}

void write_result(uint8_t* ls, const args_t* a, const result_t* r)
{
    memset(ls + a->work, 0, WORK_BYTES);
    for (int c = 0; c < r->nch; c++) {
        uint8_t* o = ls + a->work + OUT_OFF + (c ? OUT_R_OFF : 0);
        for (int i = 0; i < r->samples; i++) {
            o[2 * i] = (uint8_t)((uint16_t)r->pcm[c][i] >> 8);
            o[2 * i + 1] = (uint8_t)r->pcm[c][i];
        }
    }
    ls_wr32(ls, a->cons, r->cons);
    ls_wr32(ls, a->prod, r->ret == 0xFFFFFFFFu ? 0 : r->prod);
    if (r->samples) {
        /* the firmware's synthesis offset, stepped 18 per granule */
        const uint32_t bo = ls_rd32(ls, a->word);
        ls_wr32(ls, a->word, (bo - 18u * (uint32_t)(r->samples / 576)) & 15u);
    }
}

std::atomic<unsigned long long> s_calls, s_frames, s_errors;

int trace_left()
{
    static std::atomic<int> left{ -1 };
    int v = left.load();
    if (v < 0) {
        const char* e = getenv("SARPBC_MP3_TRACE");
        v = e ? atoi(e) : 0;
        left.store(v);
    }
    return v;
}

/* Return to the caller as `bi $r0` does (SPU_RET with r3 set). */
void return_to_caller(spu_context* ctx, uint32_t r3)
{
    for (int k = 0; k < 4; k++) ctx->gpr[3]._u32[k] = r3;
    SPU_RET(ctx);
}

/* The stand-in's entry. */
void standin_entry(spu_context* ctx)
{
    args_t a;
    get_args(ctx, &a);
    const unsigned long long n = s_calls++;
    if (n == 0) fprintf(stderr, "[mp3] MultiStream's MP3 decoder: ours (stand-in flashMP3.pic), first call\n");
    if (!args_ok(&a)) {
        fprintf(stderr, "[mp3] decodeFrame with arguments outside local store (r3=0x%X r6=0x%X r9=0x%X): -1\n",
                a.in, a.work, a.l_syn);
        s_errors++;
        return_to_caller(ctx, 0xFFFFFFFFu);
        return;
    }
    uint8_t* ls = ctx->ls;
    dod3_mp3_info info;
    const int nch = dod3_mp3_frame_bytes(ls + a.in, &info) ? info.channels : 1;
    static thread_local dod3_mp3 d;
    static thread_local result_t r;
    state_load(ls, &a, nch, &d);
    decode_frame(ls, &a, &d, &r);
    if (r.samples) state_save(ls, &a, r.nch, &d);
    write_result(ls, &a, &r);
    if (r.samples) s_frames++;
    if (r.ret == 0xFFFFFFFFu) s_errors++;
    if ((long long)n < trace_left() || (r.ret == 0xFFFFFFFFu && s_errors <= 8))
        fprintf(stderr,
                "[mp3] call %llu: frame@0x%05X %02X%02X%02X%02X -> ret 0x%X consumed %u produced %d (%d ch, %d Hz)\n",
                n, a.in, ls[a.in], ls[a.in + 1], ls[a.in + 2], ls[a.in + 3], r.ret, r.cons, (int)r.prod, r.nch,
                r.samples ? info.hz : 0);
    if (n && n % 20000 == 0)
        fprintf(stderr, "[mp3] %llu decodeFrame calls, %llu frames decoded, %llu errors\n", n, s_frames.load(),
                s_errors.load());
    return_to_caller(ctx, r.ret);
}

bool native_on()
{
    const char* e = getenv("SARPBC_MP3_NATIVE");
    return !(e && e[0] == '0');
}

struct Init {
    Init()
    {
        if (!native_on()) {
            fprintf(stderr, "[mp3] SARPBC_MP3_NATIVE=0: no stand-in flashMP3.pic\n");
            return;
        }
        serve_standin();
        uint32_t lsa = kBodyLsa;
        if (const char* e = getenv("SARPBC_MP3_LSA")) lsa = (uint32_t)strtoul(e, nullptr, 16);
        if (!lsa) return;
        spu_begin_image(kImageId);
        spu_register_function(lsa + (kEntryVa - kVaBase), standin_entry);
        spu_begin_image(0);
        spu_overlay_register_sig_region(reinterpret_cast<const uint8_t*>(kGuid), kBodySize, kImageId);
    }
};
Init s_init;

}  // namespace
