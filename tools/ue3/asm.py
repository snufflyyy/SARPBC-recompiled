"""Build UnrealScript bytecode trees (script.Node) for a Package, from the encodings of the
01.09 cook (dumps: `python3 tools/ue3 tree`). Node shapes were read from real functions;
anything not listed here is cloned from an existing statement instead (clone/find).

a = Asm(pkg)
a.s('text') a.i(5) a.nm('Name') a.NONE a.NOTHING a.TRUE a.FALSE a.SELF
a.inst('Class.Prop') a.loc('Class.Func.Local') a.default('Class.Prop')
a.ctx(obj, member[, fld='Class.Prop'])         obj.member  (member: a.inst(..) or a call)
a.let(lhs, rhs)  a.native('Name', *args)  a.vcall('Name', *args)  a.fcall('Class.Func', *args)
a.static_call('Class', 'Class.Func', *args)    class'Class'.static.Func(args)
a.elem(arr, idx)  a.smember('Struct.Field', 'Struct', expr)  a.cast(CAST_STRING_TO_INT, expr)  a.dyncast('Class', expr)
a.new(cls_path, template)  a.length(arr)  a.cond(c, x, y)  a.ret()
a.concat(*parts)  a.if_(cond, then, else_=None) -> (statements, end label: put it on the statement after)
a.text(node) -> disassembly   a.find(stmts, text) / a.find_sub(node, text)   clone(node)
"""
import copy
import itertools

from . import dis, script, upk
from .script import Node

CAST_STRING_TO_INT = 74
CAST_STRING_TO_FLOAT = 76
CAST_INT_TO_STRING = 83


class Asm:
    def __init__(self, pkg):
        self.pkg = pkg
        self._labels = itertools.count(1)
        self.NONE = Node(0x2A, [])
        self.NOTHING = Node(0x0B, [])
        self.TRUE = Node(0x27, [])
        self.FALSE = Node(0x28, [])
        self.SELF = Node(0x17, [])
        self.natives = {v: k for k, v in dis.NATIVE_NAMES.items()}

    # -- lookups ---------------------------------------------------------
    def x(self, path, cls=None):
        return upk.find_export(self.pkg.imps, self.pkg.exps, path, cls)

    def label(self):
        return ('L', next(self._labels))

    # -- leaves ----------------------------------------------------------
    def s(self, text):
        return Node(0x1F, [('raw', text.encode('latin-1') + b'\0')])

    def i(self, v):
        if v == 0:
            return Node(0x25, [])
        if v == 1:
            return Node(0x26, [])
        if 0 <= v < 256:
            return Node(0x2C, [('u8', v)])
        return Node(0x1D, [('i32', v)])

    def nm(self, text):
        return Node(0x21, [('name', (self.pkg.name(text), 0))])

    def inst(self, path):
        return Node(0x01, [('obj', self.x(path))])

    def loc(self, path):
        return Node(0x00, [('obj', self.x(path))])

    def default(self, path):
        return Node(0x02, [('obj', self.x(path))])

    def cls(self, path):
        return Node(0x20, [('obj', self.x(path))])

    # -- compound --------------------------------------------------------
    def ctx(self, obj, member, fld=None):
        return Node(0x19, [('e', obj), ('skip_ctx', None), ('obj', self.x(fld) if fld else 0),
                           ('u8', 0), ('e', member)])

    def let(self, lhs, rhs):
        return Node(0x0F, [('e', lhs), ('e', rhs)])

    def native(self, name, *args):
        idx = self.natives[name]
        parts = [('e', a) for a in args] + [('u8', 0x16)]
        if 0x70 <= idx < 0x100:
            return Node(idx, parts)
        return Node(0x60 + (idx >> 8), [('u8', idx & 0xFF)] + parts)

    def vcall(self, name, *args):
        return Node(0x1B, [('name', (self.pkg.name(name), 0))] + [('e', a) for a in args] + [('u8', 0x16)])

    def fcall(self, path, *args):
        return Node(0x1C, [('obj', self.x(path, 'Function'))] + [('e', a) for a in args] + [('u8', 0x16)])

    def static_call(self, cls_path, func_path, *args):
        ret = func_path + '.ReturnValue'
        try:
            r = ret if self.x(ret) else None
        except KeyError:
            r = None
        return Node(0x12, [('e', self.cls(cls_path)), ('skip_ctx', None), ('obj', self.x(r) if r else 0),
                           ('u8', 0), ('e', self.fcall(func_path, *args))])

    def elem(self, arr, idx):
        return Node(0x10, [('e', idx), ('e', arr)])

    def smember(self, field_path, struct_path, expr):
        return Node(0x35, [('obj', self.x(field_path)), ('obj', self.x(struct_path)), ('u8', 0), ('u8', 0),
                           ('e', expr)])

    def cast(self, kind, expr):
        return Node(0x38, [('u8', kind), ('e', expr)])

    def dyncast(self, cls_path, expr):
        return Node(0x2E, [('obj', self.x(cls_path)), ('e', expr)])

    def new(self, cls_path, template):
        return Node(0x11, [('e', self.NOTHING), ('e', self.NOTHING), ('e', self.NOTHING),
                           ('e', self.cls(cls_path)), ('e', template)])

    def length(self, arr):
        return Node(0x36, [('e', arr)])

    def cond(self, c, x, y):
        return Node(0x45, [('e', c), ('skip', 1), ('e', x), ('skip', 1), ('e', y)])

    def ret(self):
        return Node(0x04, [('e', self.NOTHING)])

    def concat(self, *parts):
        """a $ b $ c ... (strings or nodes)."""
        nodes = [self.s(p) if isinstance(p, str) else p for p in parts]
        out = nodes[0]
        for n in nodes[1:]:
            out = self.native('Concat_StrStr', out, n)
        return out

    # -- control flow ----------------------------------------------------
    def if_(self, cond, then, else_=None):
        """Statements for `if (cond) then else else_`."""
        end = self.label()
        els = self.label()
        out = [Node(0x07, [('jmp', els if else_ else end), ('e', cond)])]
        out += then
        if else_:
            out.append(Node(0x06, [('jmp', end)]))
            else_[0].label = (else_[0].label or []) + [els]
            out += else_
        return out, end

    # -- rendering and cloning ------------------------------------------
    def text(self, node):
        enc, _ = script.encode([_strip(node)])
        d = dis.Dis(enc + b'\x53', self.pkg.names, self.pkg.imps, self.pkg.exps)
        return d.expr()

    def find(self, stmts, text, count=1):
        hits = [i for i, s in enumerate(stmts) if self.text(s) == text]
        if len(hits) != count:
            raise KeyError('%r: %d matches among %s' % (text, len(hits), [self.text(s) for s in stmts]))
        return hits if count != 1 else hits[0]

    def find_sub(self, node, text):
        stack = [node]
        while stack:
            n = stack.pop(0)
            if n is not node and self.text(n) == text:
                return n
            stack += [v for k, v in n.parts if k == 'e']
        raise KeyError(text)


def _strip(node):
    n = copy.deepcopy(node)

    def walk(x):
        for i, (k, v) in enumerate(x.parts):
            if k == 'jmp':
                x.parts[i] = ('u16', 0xFFFE)
            elif k == 'skip_ctx' and v is not None:
                x.parts[i] = ('skip_ctx', None)
            elif k == 'e':
                walk(v)
    walk(n)
    n.mem = None
    n.label = None
    return n


def clone(node):
    n = copy.deepcopy(node)

    def walk(x):
        x.mem = None
        x.label = None
        for k, v in x.parts:
            if k == 'e':
                walk(v)
    walk(n)
    return n
