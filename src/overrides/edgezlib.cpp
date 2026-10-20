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
#include <array>
#include <zlib.h>

#include "ppu_recomp.h"

extern "C" {
extern uint8_t* vm_base;
extern uint32_t ppu_vm_size;
typedef void (*hle_ctx_fn)(ppu_context*);
void ps3_hle_register_ctx(uint32_t nid, const char* name, hle_ctx_fn fn);
typedef struct CellSpursEventFlag CellSpursEventFlag;
int32_t cellSpursEventFlagSet(CellSpursEventFlag* eventFlag, uint16_t bits);
}

namespace {

constexpr uint32_t kNidLFQueuePushBody = 0x8A85674D;
constexpr uint32_t kQueueSizeOffset = 0x10;          /* see _cellSpursLFQueueInitialize */
constexpr uint32_t kSpursTaskErrorStat = 0x8041090F;
constexpr uint32_t kSpursTaskErrorInval = 0x80410902;
constexpr uint32_t kSpursTaskErrorAlign = 0x80410910;
constexpr uint32_t kEventFlagBytes = 128;

/* ppu_vm_size=0 is the runner's full 32-bit mapping convention. A nonzero
 * size (also used by synthetic fixtures) bounds the actual guest backing.
 * Do not count the runner's extra 64 KiB guard as guest address space. */
bool guest_range(uint32_t ea, uint64_t bytes)
{
    if (!bytes) return true;
    if (!ea || bytes > 0x100000000ull - ea) return false;
    const uint64_t end = (uint64_t)ea + bytes;
    const uintptr_t base = (uintptr_t)vm_base;
    return (vm_base || ppu_vm_size) &&
           (!ppu_vm_size || end <= ppu_vm_size) && base <= UINTPTR_MAX - ea &&
           bytes - 1 <= UINTPTR_MAX - (base + ea);
}

uint32_t be32(uint32_t ea)
{
    const uint8_t* p = vm_base + ea;
    return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3];
}

bool trace()
{
    static const bool on = getenv("SARPBC_ZLIB_TRACE") != nullptr;
    return on;
}

std::atomic<unsigned long long> s_requests, s_failed, s_bytes_in, s_bytes_out;

void report()
{
    fprintf(stderr, "[edgezlib] %llu requests (%.1f MB -> %.1f MB), %llu rejected requests\n",
            s_requests.load(), s_bytes_in.load() / 1048576.0, s_bytes_out.load() / 1048576.0,
            s_failed.load());
}

/* Stream the prefix/suffix into fixed scratch space instead of allocating
 * skip_begin + total + skip_end bytes from untrusted request lengths. The
 * two skips are u16; the caller checks the combined size in wide arithmetic. */
bool inflate_exact(const uint8_t* in, uint32_t in_size, uint8_t* out, uint32_t total,
                   uint16_t skip_begin, uint16_t skip_end)
{
    z_stream z{};
    if (inflateInit2(&z, -15) != Z_OK) return false;
    z.next_in = const_cast<Bytef*>(in);
    z.avail_in = in_size;
    std::array<uint8_t, UINT16_MAX> discard;
    uint8_t* targets[] = { discard.data(), out, discard.data() };
    const uint32_t lengths[] = { skip_begin, total, skip_end };
    int rc = Z_OK;
    for (unsigned i = 0; i < 3 && rc == Z_OK; ++i) {
        z.next_out = targets[i];
        z.avail_out = lengths[i];
        while (z.avail_out && rc == Z_OK) rc = inflate(&z, Z_NO_FLUSH);
    }
    /* An exact-sized output can fill before zlib consumes the end marker.
     * Give it one byte to finish, but reject a stream that writes that byte. */
    uint8_t extra;
    if (rc == Z_OK) {
        z.next_out = &extra;
        z.avail_out = 1;
        rc = inflate(&z, Z_FINISH);
    }
    const uint64_t expected = (uint64_t)skip_begin + total + skip_end;
    const bool ok = rc == Z_STREAM_END && z.total_out == expected;
    inflateEnd(&z);
    return ok;
}

/* Never wrap a depleted shared work counter, even if another caller changed
 * it after validation. Publish successful output before the completion CAS. */
bool counter_decrement(uint32_t ea, uint32_t& remaining)
{
    auto* p = reinterpret_cast<uint32_t*>(vm_base + ea);
    uint32_t old_raw = __atomic_load_n(p, __ATOMIC_ACQUIRE), new_raw;
    do {
        const uint32_t old = __builtin_bswap32(old_raw);
        if (!old) return false;
        remaining = old - 1;
        new_raw = __builtin_bswap32(remaining);
    } while (!__atomic_compare_exchange_n(p, &old_raw, new_raw, false, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE));
    return true;
}

void reject(ppu_context* ctx, uint32_t error, const char* reason)
{
    if (s_failed++ < 8) fprintf(stderr, "[edgezlib] request rejected: %s (0x%08X)\n", reason, error);
    ctx->gpr[3] = error;
}

/* _cellSpursLFQueuePushBody(CellSpursLFQueue* queue, const void* buffer, bool isBlocking) */
void lfqueue_push_body(ppu_context* ctx)
{
    const uint32_t q = (uint32_t)ctx->gpr[3], buf = (uint32_t)ctx->gpr[4];
    if (!guest_range(q, kQueueSizeOffset + 4) || !guest_range(buf, 32)) {
        reject(ctx, kSpursTaskErrorInval, "queue or descriptor outside guest backing");
        return;
    }
    if (be32(q + kQueueSizeOffset) != 32) {
        reject(ctx, kSpursTaskErrorStat, "unsupported non-Edge-zlib queue");
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
    const uint16_t skip_begin = (uint16_t)w[6], skip_end = (uint16_t)(w[7] >> 16);

    const uint64_t total = (uint64_t)skip_begin + out_size + skip_end;
    const uint32_t read_size = do_inflate ? in_size : out_size;
    if (!guest_range(in_ea, read_size) || !guest_range(out_ea, out_size) ||
        (do_inflate && total > UINT32_MAX) ||
        (counter_ea && !guest_range(counter_ea, 4)) ||
        (flag_ea && !guest_range(flag_ea, kEventFlagBytes))) {
        reject(ctx, kSpursTaskErrorInval, "request span or decoded size outside guest backing");
        return;
    }
    if (counter_ea && (counter_ea & 3u)) {
        reject(ctx, kSpursTaskErrorAlign, "unaligned work counter");
        return;
    }
    const uint32_t pending = counter_ea ? __builtin_bswap32(__atomic_load_n(
        reinterpret_cast<uint32_t*>(vm_base + counter_ea), __ATOMIC_ACQUIRE)) : 0;
    if (counter_ea && !pending) {
        reject(ctx, kSpursTaskErrorStat, "work counter already zero");
        return;
    }

    const unsigned long long n = s_requests++;
    if (trace() || n < 4)
        fprintf(stderr,
                "[edgezlib] #%llu %s in=0x%08X/%u out=0x%08X/%u counter=0x%08X(=%u) flag=0x%08X bits=0x%04X "
                "skip=%u/%u\n",
                n, do_inflate ? "inflate" : "copy", in_ea, in_size, out_ea, out_size, counter_ea,
                pending, flag_ea, bits, skip_begin, skip_end);

    bool ok = true;
    if (!do_inflate) {
        if (out_size) memmove(vm_base + out_ea, vm_base + in_ea, out_size);
    } else {
        ok = inflate_exact(vm_base + in_ea, in_size, vm_base + out_ea, out_size, skip_begin, skip_end);
    }
    s_bytes_in += in_size;
    s_bytes_out += out_size;
    if (!ok) {
        /* 01.09 func_00B55024 checks the push result at 0x00B55168. A bad
         * stream is not completed work: do not wake a waiter on corrupt data. */
        reject(ctx, kSpursTaskErrorStat, "invalid or incomplete deflate stream");
        return;
    }

    /* The task's completion: count down, and on zero set the flag bits. This
     * title passes no counter (EA 0) -- one request per wait -- so then the
     * request alone completes the work and sets the flag. */
    uint32_t remaining = 0;
    if (counter_ea && !counter_decrement(counter_ea, remaining)) {
        reject(ctx, kSpursTaskErrorStat, "work counter depleted during request");
        return;
    }
    ctx->gpr[3] = remaining == 0 && flag_ea
        ? (uint32_t)cellSpursEventFlagSet(reinterpret_cast<CellSpursEventFlag*>((uintptr_t)flag_ea), bits)
        : 0;   /* CELL_OK; never hide an event-delivery error. */
}

}  // namespace

extern "C" void sarpbc_register_edgezlib(void)
{
    ps3_hle_register_ctx(kNidLFQueuePushBody, "_cellSpursLFQueuePushBody", lfqueue_push_body);
}
