"""Edit one Function export's script as a statement tree and rebuild its body.

f = Func(pkg, idx)            parse export idx (1-based)
f.stmts                       list of script.Node (the statements, ending with EX_EndOfScript)
f.body()                      new export body: 44-byte header with the new in-memory
                              size, the re-encoded bytecode, the original tail
                              (iNative, flags, friendly name, ...)

Jump targets are remapped by script.encode(); a statement gets a label via
node.label = [...] if a new jump should land on it.
"""
import struct

from . import script


class Func:
    def __init__(self, pkg, idx):
        self.pkg, self.idx = pkg, idx
        e = pkg.exps[idx - 1]
        b = bytes(pkg.u[e['off']:e['off'] + e['size']])
        self.header = bytearray(b[:44])
        ps = script.Parser(b, 44, len(b))
        stmts = []
        while True:
            n = ps.expr()
            stmts.append(n)
            if n.op == 0x53:
                break
        self.stmts = stmts
        self.tail = b[ps.p:]
        self.mem = struct.unpack_from('>I', b, 40)[0]
        if ps.m != self.mem:
            raise ValueError('export %d: parsed %d bytes of script, header says %d' % (idx, ps.m, self.mem))

    def body(self):
        enc, mem = script.encode(self.stmts)
        h = bytearray(self.header)
        struct.pack_into('>I', h, 40, mem)
        return bytes(h) + enc + self.tail


def walk(node):
    """Every Node under node, node first."""
    yield node
    for k, v in node.parts:
        if k == 'e':
            yield from walk(v)
