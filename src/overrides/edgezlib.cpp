/*
 * Edge zlib requests, done natively at the LFQueue push.
 *
 * UE3 inflates every compressed package chunk through Sony's Edge zlib SPU
 * task (SPU image 1, fingerprint 4100F6EDD2441719): the PPU's
 * edgeZlibAddInflateQueueElement pushes a 32-byte request onto a SPURS
 * LFQueue with _cellSpursLFQueuePushBody, the task pops it, inflates or
 * copies, counts the request's work-to-do counter down and, when it reaches
 * zero, sets the request's SPURS event flag bits; the loader waits on that
 * flag.
 *
 * ps3recomp has no _cellSpursLFQueuePushBody (NID 0x8A85674D), so the push
 * did nothing and the loader waited forever on CORE.XXX. Drakengard 3's port
 * solves the same thing with libsre's real push lifted from firmware; we do
 * not ship firmware, so the whole request is serviced here instead and the
 * SPU task is simply never handed work.
 *
 * The request (big-endian words; layout from the Drakengard 3 port's reading
 * of the same Edge zlib task, confirmed against this title's pushes with
 * SARPBC_ZLIB_TRACE=1):
 *   +00 compressed EA        +04 output EA
 *   +08 compressed bytes     +0C output bytes
 *   +10 work-to-do counter EA | bit 0: 1 inflate, 0 copy
 *   +14 event flag EA        +18 u16 event flag bits
 *   +1A u16 bytes of the stream to drop before the output
 *   +1C u16 bytes of the stream to drop after it
 *
 * A push onto any other LFQueue (element size != 32) is not ours: it is
 * reported once and fails with CELL_SPURS_TASK_ERROR_STAT.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <atomic>
#include <vector>
#include <zlib.h>

#include "ppu_recomp.h"

extern "C" {
extern uint8_t* vm_base;
typedef void (*hle_ctx_fn)(ppu_context*);
void ps3_hle_register_ctx(uint32_t nid, const char* name, hle_ctx_fn fn);
typedef struct CellSpursEventFlag CellSpursEventFlag;
int32_t cellSpursEventFlagSet(CellSpursEventFlag* eventFlag, uint16_t bits);
}

namespace {

constexpr uint32_t kNidLFQueuePushBody = 0x8A85674D;
constexpr uint32_t kQueueSizeOffset = 0x10;          /* see _cellSpursLFQueueInitialize */
constexpr uint32_t kSpursTaskErrorStat = 0x8041090F;

uint32_t be32(uint32_t ea)
{
    const uint8_t* p = vm_base + ea;
    return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3];
}

bool trace()
{
    static int on = -1;
    if (on < 0) on = getenv("SARPBC_ZLIB_TRACE") ? 1 : 0;
    return on;
}

std::atomic<unsigned long long> s_requests, s_failed, s_bytes_in, s_bytes_out;

void report()
{
    fprintf(stderr, "[edgezlib] %llu requests (%.1f MB -> %.1f MB), %llu failed to inflate\n",
            s_requests.load(), s_bytes_in.load() / 1048576.0, s_bytes_out.load() / 1048576.0,
            s_failed.load());
}

/* Inflate the raw deflate stream at `in` into `out`, exactly `total` bytes. */
bool inflate_exact(const uint8_t* in, uint32_t in_size, uint8_t* out, uint32_t total)
{
    z_stream z;
    memset(&z, 0, sizeof z);
    if (inflateInit2(&z, -15) != Z_OK) return false;
    z.next_in = const_cast<Bytef*>(in);
    z.avail_in = in_size;
    z.next_out = out;
    z.avail_out = total;
    const int rc = inflate(&z, Z_FINISH);
    const bool ok = (rc == Z_STREAM_END || rc == Z_OK || rc == Z_BUF_ERROR) && z.total_out == total;
    inflateEnd(&z);
    return ok;
}

/* Atomically decrement the big-endian u32 at ea; returns the new value. */
uint32_t counter_decrement(uint32_t ea)
{
    auto* p = reinterpret_cast<uint32_t*>(vm_base + ea);
    uint32_t old_raw = __atomic_load_n(p, __ATOMIC_ACQUIRE), new_raw;
    do {
        new_raw = __builtin_bswap32(__builtin_bswap32(old_raw) - 1);
    } while (!__atomic_compare_exchange_n(p, &old_raw, new_raw, false, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE));
    return __builtin_bswap32(new_raw);
}

/* _cellSpursLFQueuePushBody(CellSpursLFQueue* queue, const void* buffer, bool isBlocking) */
void lfqueue_push_body(ppu_context* ctx)
{
    const uint32_t q = (uint32_t)ctx->gpr[3], buf = (uint32_t)ctx->gpr[4];
    if (!q || !buf || be32(q + kQueueSizeOffset) != 32) {
        static bool once = false;
        if (!once) {
            once = true;
            fprintf(stderr, "[edgezlib] push onto a non-Edge-zlib LFQueue q=0x%08X size=%u -- unsupported\n", q,
                    q ? be32(q + kQueueSizeOffset) : 0);
        }
        ctx->gpr[3] = kSpursTaskErrorStat;
        return;
    }
    static bool s_atexit = (atexit(report), true);
    (void)s_atexit;

    uint32_t w[8];
    for (int i = 0; i < 8; i++) w[i] = be32(buf + 4 * i);
    const uint32_t in_ea = w[0], out_ea = w[1], in_size = w[2], out_size = w[3];
    const uint32_t counter_ea = w[4] & ~1u, flag_ea = w[5];
    const bool do_inflate = w[4] & 1u;
    const uint16_t bits = (uint16_t)(w[6] >> 16);
    const uint32_t skip_begin = w[6] & 0xFFFFu, skip_end = w[7] >> 16;

    const unsigned long long n = s_requests++;
    if (trace() || n < 4)
        fprintf(stderr,
                "[edgezlib] #%llu %s in=0x%08X/%u out=0x%08X/%u counter=0x%08X(=%u) flag=0x%08X bits=0x%04X "
                "skip=%u/%u\n",
                n, do_inflate ? "inflate" : "copy", in_ea, in_size, out_ea, out_size, counter_ea,
                counter_ea ? be32(counter_ea) : 0, flag_ea, bits, skip_begin, skip_end);

    bool ok = true;
    if (!do_inflate) {
        memmove(vm_base + out_ea, vm_base + in_ea, out_size);
    } else if (!skip_begin && !skip_end) {
        ok = inflate_exact(vm_base + in_ea, in_size, vm_base + out_ea, out_size);
    } else {
        std::vector<uint8_t> tmp(skip_begin + out_size + skip_end);
        ok = inflate_exact(vm_base + in_ea, in_size, tmp.data(), (uint32_t)tmp.size());
        if (ok) memcpy(vm_base + out_ea, tmp.data() + skip_begin, out_size);
    }
    s_bytes_in += in_size;
    s_bytes_out += out_size;
    if (!ok && s_failed++ < 8)
        fprintf(stderr, "[edgezlib] #%llu in=0x%08X (%u B) did not inflate to %u B -- output is wrong\n", n, in_ea,
                in_size, out_size);

    /* The task's completion: count down, and on zero set the flag bits. This
     * title passes no counter (EA 0) -- one request per wait -- so then the
     * request alone completes the work and sets the flag. */
    const bool done = counter_ea ? counter_decrement(counter_ea) == 0 : true;
    if (done && flag_ea)
        cellSpursEventFlagSet(reinterpret_cast<CellSpursEventFlag*>((uintptr_t)flag_ea), bits);

    ctx->gpr[3] = 0;   /* CELL_OK */
}

}  // namespace

extern "C" void sarpbc_register_edgezlib(void)
{
    ps3_hle_register_ctx(kNidLFQueuePushBody, "_cellSpursLFQueuePushBody", lfqueue_push_body);
}
