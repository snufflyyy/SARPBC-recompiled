"""python3 tools/ue3 <command> ...

  info <package>                       summary and counts
  dis <package> <Class|*> [Function]   disassemble a class's functions
  find <package> <text>                exports whose path contains text
  tree <package> <Class.Func> [n]      statement trees of a function (all, or statement n)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ue3 import dis, funcedit, pkgwrite, tree, upk   # noqa: E402


def main(argv):
    if len(argv) < 2 or argv[0] not in ('info', 'dis', 'find', 'tree'):
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd == 'dis':
        dis.main(args)
        return 0
    if cmd == 'tree':
        pkg = pkgwrite.Package(args[0])
        f = funcedit.Func(pkg, upk.find_export(pkg.imps, pkg.exps, args[1], 'Function'))
        for i, st in enumerate(f.stmts):
            if len(args) > 2 and int(args[2]) != i:
                continue
            print('[%d] mem %s' % (i, st.mem))
            print(tree.fmt(st, pkg.names, pkg.imps, pkg.exps, 1))
        return 0
    u, s = upk.decompress(args[0])
    names, imps, exps = upk.tables(u, s)
    if cmd == 'info':
        print('%s: version %d, %d bytes uncompressed, %d names, %d imports, %d exports' % (
            args[0], s['version'], len(u), len(names), len(imps), len(exps)))
        return 0
    pat = args[1].lower()
    for i, e in enumerate(exps):
        p = upk.path_of(i + 1, imps, exps)
        if pat in p.lower():
            print(i + 1, upk.objname(e['cls'], imps, exps), p, e['size'], e['off'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
