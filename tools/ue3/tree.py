"""Readable dump of a script.Node tree (symbolic names), for building new code from real examples.

python3 tools/ue3 tree <package> <Class.Function> [statement index]
"""
import struct

from . import upk


def fmt(node, names, imps, exps, depth=0):
    pad = '  ' * depth
    out = []
    head = '%s0x%02x' % (pad, node.op)
    parts = []
    kids = []
    for k, v in node.parts:
        if k == 'e':
            kids.append(v)
        elif k == 'obj':
            parts.append('obj=%s' % upk.path_of(v, imps, exps) if v else 'obj=None')
        elif k == 'name':
            i, n = v
            parts.append('name=%s%s' % (names[i], '_%d' % (n - 1) if n else ''))
        elif k == 'raw':
            parts.append('raw=%r' % (v,))
        else:
            parts.append('%s=%r' % (k, v))
    out.append(head + ' ' + ' '.join(parts))
    for kid in kids:
        out.append(fmt(kid, names, imps, exps, depth + 1))
    return '\n'.join(out)
