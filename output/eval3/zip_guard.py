#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zip 路径修复 + 闸。

问题:在 Windows 上打的 zip,条目名用反斜杠做路径分隔符。
     ⇒ 在 Linux/macOS 上解出来文件名乱码或落到错误的文件名。
实测:交付的「对话归档-2026-11-10.zip」69 个条目里 63 个(91%)中招。

用法:
    python3 zip_guard.py <zip>              # 闸:检查(非 0 退出 = 有问题)
    python3 zip_guard.py <zip> --fix <out>  # 修复:重打成 POSIX 路径
"""
import sys, os, zipfile, shutil


def scan(path):
    bad = []
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if '\\' in n:
                bad.append(n)
    return bad


def fix(src, dst):
    fixed = 0
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            name = it.filename.replace('\\', '/')
            if name != it.filename:
                fixed += 1
            zi = zipfile.ZipInfo(name, date_time=it.date_time)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = it.external_attr
            zout.writestr(zi, zin.read(it))
    return fixed


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    p = sys.argv[1]
    bad = scan(p)
    total = len(zipfile.ZipFile(p).namelist())
    print('═══ zip 路径闸 ═══')
    print('  %s' % p)
    print('  条目 %d | 含反斜杠 %d (%.0f%%)' % (total, len(bad), 100 * len(bad) / max(1, total)))
    if '--fix' in sys.argv:
        out = sys.argv[sys.argv.index('--fix') + 1]
        n = fix(p, out)
        print('  已修复 %d 条 → %s' % (n, out))
        left = scan(out)
        print('  复验: 含反斜杠 %d 条 %s' % (len(left), '✅' if not left else '❌'))
        return 0 if not left else 1
    if bad:
        print('  ❌ 有 %d 条路径用反斜杠 ⇒ 非 Windows 上解压会乱码' % len(bad))
        for b in bad[:5]:
            print('     ', b)
        return 1
    print('  ✅ 所有条目都是 POSIX 路径')
    return 0


if __name__ == '__main__':
    sys.exit(main())
