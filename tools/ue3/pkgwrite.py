"""Write a patched UE3 package (version 539, chunk-compressed PS3 cook).

Package(path)                 the uncompressed image plus its tables
p.replace_export(idx, body)   append body to the image and point export idx
                              (1-based) at it; the old body stays as garbage
p.save()                      -> bytes of the compressed file

The file is padded with zeros to a multiple of 2048 like the cook's.

Only the chunks whose bytes changed are recompressed (the one holding the
export table; zlib, 64 KiB blocks like the cooker's); the rest are copied
verbatim, and the appended bodies go in a new last chunk. Nothing else in the
header moves, so no new names can be added: a patch uses existing names and
string constants.

File layout (found by reading the 01.09 cook): the summary up to the
compression fields; u32 compression flags (1 = zlib); u32 chunk count; the
chunk table (uncompressed offset, uncompressed size, file offset, size); u32
package source and a zero u32; then each chunk's {tag, block size, compressed
size, uncompressed size} header, a (compressed, uncompressed) pair per block
and the zlib blocks. The uncompressed image keeps the summary up to its
compression fields with flags 0 and no chunks, i.e. the same 109 bytes.
"""
import struct
import zlib

from . import upk

BLOCK = 65536


def compress_chunk(data, level=6):
    blocks = [data[i:i + BLOCK] for i in range(0, len(data), BLOCK)] or [b'']
    comp = [zlib.compress(b, level) for b in blocks]
    hdr = struct.pack('>IIII', upk.TAG, BLOCK, sum(len(c) for c in comp), len(data))
    hdr += b''.join(struct.pack('>II', len(c), len(b)) for c, b in zip(comp, blocks))
    return hdr + b''.join(comp)


class Package:
    def __init__(self, path):
        self.path = path
        self.disk = open(path, 'rb').read()
        u, self.s = upk.decompress(path)
        self.u = bytearray(u)
        self.orig_len = len(u)
        self.names, self.imps, self.exps = upk.tables(bytes(u), self.s)

    def replace_export(self, idx, body):
        e = self.exps[idx - 1]
        off = len(self.u)
        self.u += body
        struct.pack_into('>ii', self.u, e['pos'] + 32, len(body), off)
        e['size'], e['off'] = len(body), off

    def save(self):
        s, d = self.s, self.disk
        chunks = sorted(s['chunks'])
        out_chunks = []        # (uoff, usz, compressed bytes)
        for uoff, usz, coff, csz in chunks:
            if bytes(self.u[uoff:uoff + usz]) == upk.chunk_stream(d, coff):
                out_chunks.append((uoff, usz, d[coff:coff + csz_of(d, coff)]))
            else:
                out_chunks.append((uoff, usz, compress_chunk(bytes(self.u[uoff:uoff + usz]))))
        if len(self.u) > self.orig_len:
            tail = bytes(self.u[self.orig_len:])
            out_chunks.append((self.orig_len, len(tail), compress_chunk(tail)))
        head = bytearray(d[:s['chunk_table_pos'] - 4])      # up to the chunk count
        head += struct.pack('>I', len(out_chunks))
        table_len = 16 * len(out_chunks)
        source = d[s['summary_end']:s['summary_end'] + 8]
        base = len(head) + table_len + len(source)
        table = b''
        body = b''
        for uoff, usz, comp in out_chunks:
            table += struct.pack('>IIII', uoff, usz, base + len(body), len(comp))
            body += comp
        out = bytes(head) + table + source + body
        return out + b'\0' * (-len(out) % 2048)       # the cook pads to whole sectors


def csz_of(d, coff):
    """Whole size of the chunk stream at coff: header, block table, blocks."""
    _tag, bs, csz, usz = struct.unpack_from('>IIII', d, coff)
    n = (usz + bs - 1) // bs
    return 16 + 8 * n + csz


def toc_set(toc, path_suffix, size):
    """PS3TOC.TXT text with the size of the line whose path ends with path_suffix
    (a backslash path, case-insensitive) replaced. Lines are `<size> 0 0 <path> 0`."""
    rows = toc.split('\r\n')
    hit = 0
    for i, r in enumerate(rows):
        f = r.split(' ')
        if len(f) >= 4 and f[3].lower().endswith(path_suffix.lower()):
            f[0] = str(size)
            rows[i] = ' '.join(f)
            hit += 1
    if hit != 1:
        raise KeyError('%s: %d TOC lines' % (path_suffix, hit))
    return '\r\n'.join(rows)
