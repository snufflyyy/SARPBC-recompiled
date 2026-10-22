"""UE3 package reader for Supersonic Acrobatic Rocket-Powered Battle-Cars
(package version 539 = 0x21B, licensee 1, PS3 cook, big-endian).

decompress(path) -> (bytes of the whole uncompressed package, summary dict)
tables(u, s)     -> (names, imports, exports)

The summary is read up to the compressed-chunk table. Chunk 0 starts at the end
of the summary and holds the name table, so everything past the summary is
inflated before the tables are read. The layouts below were worked out from the
01.09 cook (docs/graphics-menu.md "Package format"); the chunk stream and the
fstring reader follow dod3-recomp's tools/ue3/upk.py (MIT).
"""
import struct
import zlib

TAG = 0x9E2A83C1


def fstring(d, p):
    n = struct.unpack_from('>i', d, p)[0]
    p += 4
    if n >= 0:
        return d[p:p + n].rstrip(b'\0').decode('latin-1'), p + n
    return d[p:p - 2 * n].decode('utf-16-be').rstrip('\0'), p - 2 * n


def chunk_stream(d, off):
    """One compressed chunk: {tag, block size, compressed, uncompressed} then
    (compressed, uncompressed) per block, then the zlib blocks."""
    tag, bs, _csz, usz = struct.unpack_from('>IIII', d, off)
    if tag != TAG:
        raise ValueError('bad chunk tag %#x at %d' % (tag, off))
    n = (usz + bs - 1) // bs
    blocks = [struct.unpack_from('>II', d, off + 16 + 8 * i) for i in range(n)]
    p = off + 16 + 8 * n
    out = []
    for c, _u in blocks:
        out.append(zlib.decompress(d[p:p + c]))
        p += c
    r = b''.join(out)
    if len(r) != usz:
        raise ValueError('chunk inflated to %d, header says %d' % (len(r), usz))
    return r


def summary(d):
    """Package summary up to and including the compressed-chunk table."""
    if struct.unpack_from('>I', d, 0)[0] != TAG:
        raise ValueError('not a UE3 package')
    s = {}
    s['version'], s['licensee'] = struct.unpack_from('>HH', d, 4)
    s['header_size'] = struct.unpack_from('>I', d, 8)[0]
    s['folder'], p = fstring(d, 12)
    s['fields_pos'] = p               # flags, then name n/offset, export n/offset, import n/offset
    (s['flags'], s['name_n'], s['name_off'], s['exp_n'], s['exp_off'],
     s['imp_n'], s['imp_off'], s['depends_off']) = struct.unpack_from('>8I', d, p)
    p += 32 + 16                      # + the package GUID
    gen_n = struct.unpack_from('>I', d, p)[0]
    s['gen_pos'] = p + 4              # {exports, names, net objects} per generation
    p += 4 + 12 * gen_n
    s['engine'], s['cooker'] = struct.unpack_from('>II', d, p)
    p += 8
    s['compression'], cn = struct.unpack_from('>II', d, p)
    p += 8
    s['chunks'] = [struct.unpack_from('>IIII', d, p + 16 * i) for i in range(cn)]
    s['chunk_table_pos'] = p
    s['summary_end'] = p + 16 * cn
    return s


def decompress(path):
    d = open(path, 'rb').read()
    s = summary(d)
    if not s['chunks']:
        return d, s
    first = min(c[0] for c in s['chunks'])
    out = bytearray(d[:first])
    for uoff, usz, coff, _csz in sorted(s['chunks']):
        if len(out) != uoff:
            raise ValueError('chunk at %d does not follow %d' % (uoff, len(out)))
        b = chunk_stream(d, coff)
        if len(b) != usz:
            raise ValueError('chunk size mismatch')
        out += b
    return bytes(out), s


def tables(u, s):
    """names, imports, exports of an uncompressed package.

    import: (package, class, outer, name)
    export: dict(cls, sup, outer, name, name_i, name_n, size, off, pos, len)
      object indices are signed: > 0 an export (index - 1), < 0 an import.
      pos/len: the table record's place in u (the record is 72 + 12*components
      + 4*net-object-counts bytes; the layout was found by trial, see the doc).
    """
    names = []
    p = s['name_off']
    for _ in range(s['name_n']):
        n, p = fstring(u, p)
        p += 8                        # name flags (u64)
        names.append(n)
    s['name_table_end'] = p

    def nm(i, num=0):
        return names[i] + ('_%d' % (num - 1) if num else '')

    imps = []
    p = s['imp_off']
    for _ in range(s['imp_n']):
        cp, cpn, cls, clsn, outer, on, onn = struct.unpack_from('>IIIIiII', u, p)
        p += 28
        imps.append((nm(cp, cpn), nm(cls, clsn), outer, nm(on, onn)))

    exps = []
    p = s['exp_off']
    for _ in range(s['exp_n']):
        cls, sup, outer, on, onn, arch = struct.unpack_from('>iiiIIi', u, p)
        flags = struct.unpack_from('>Q', u, p + 24)[0]
        size, off, comps = struct.unpack_from('>iiI', u, p + 32)
        nets = struct.unpack_from('>I', u, p + 48 + 12 * comps)[0]
        n = 72 + 12 * comps + 4 * nets
        exps.append(dict(cls=cls, sup=sup, outer=outer, name=nm(on, onn), name_i=on, name_n=onn,
                         arch=arch, flags=flags, size=size, off=off, pos=p, len=n))
        p += n
    return names, imps, exps


def objname(i, imps, exps):
    if i > 0:
        return exps[i - 1]['name']
    if i < 0:
        return imps[-i - 1][3]
    return 'None'


def path_of(i, imps, exps):
    out = []
    while i != 0:
        out.append(objname(i, imps, exps))
        i = exps[i - 1]['outer'] if i > 0 else imps[-i - 1][2]
    return '.'.join(reversed(out))


def find_export(imps, exps, path, cls=None):
    """Object index of `path` (e.g. 'MainMenuSceneContainer.GameOptions.NextScene'): the
    1-based export index, else the negative import index (e.g. 'PsyUI.PsyUIListWidget.bValuesAreMarkup');
    optionally of class `cls`."""
    tail = path.rsplit('.', 1)[-1]
    hits = [i + 1 for i, e in enumerate(exps) if e['name'] == tail and path_of(i + 1, imps, exps) == path
            and (cls is None or objname(e['cls'], imps, exps) == cls)]
    if not hits:
        hits = [-(i + 1) for i, m in enumerate(imps) if m[3] == tail and path_of(-(i + 1), imps, exps) == path
                and (cls is None or m[1] == cls)]
    if len(hits) != 1:
        raise KeyError('%s: %d matches' % (path, len(hits)))
    return hits[0]
