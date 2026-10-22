"""COALESCED.INT / .INI: the engine's packed config and localisation files.

load(bytes) -> [[name, text, name_wide, text_wide]]; dump(entries) -> bytes. Big-endian u32
string count (twice the entries), then per entry two FStrings (name, contents): an i32 length including the
NUL (negative: UTF-16BE characters, positive: Latin-1). Round-trips the 01.09 files.
"""
import struct


def _read(d, p):
    n = struct.unpack_from('>i', d, p)[0]
    p += 4
    if n < 0:
        n = -n
        return d[p:p + 2 * n].decode('utf-16-be'), p + 2 * n, True
    return d[p:p + n].decode('latin-1'), p + n, False


def _write(s, wide):
    if wide:
        raw = s.encode('utf-16-be')
        return struct.pack('>i', -(len(raw) // 2)) + raw
    raw = s.encode('latin-1')
    return struct.pack('>i', len(raw)) + raw


def load(d):
    n = struct.unpack_from('>I', d, 0)[0] // 2
    p = 4
    out = []
    for _ in range(n):
        name, p, nw = _read(d, p)
        text, p, tw = _read(d, p)
        out.append([name, text, nw, tw])
    return out


def dump(entries):
    out = [struct.pack('>I', 2 * len(entries))]
    for name, text, nw, tw in entries:
        out.append(_write(name, nw))
        out.append(_write(text, tw))
    return b''.join(out)


def section_add(text, section, lines):
    """Append key=value lines to [section] of an ini text (before the next section).
    Line endings follow the text's own."""
    nul = '\0' if text.endswith('\0') else ''
    text = text[:len(text) - len(nul)]
    nl = '\r\n' if '\r\n' in text else '\n'
    head = '[%s]' % section
    rows = text.split(nl)
    for i, r in enumerate(rows):
        if r.strip().lower() == head.lower():
            j = i + 1
            while j < len(rows) and not rows[j].startswith('['):
                j += 1
            while j > i + 1 and rows[j - 1].strip() == '':
                j -= 1
            return nl.join(rows[:j] + list(lines) + rows[j:]) + nul
    raise KeyError(section)
