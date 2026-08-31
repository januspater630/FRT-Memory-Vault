# -*- coding: utf-8 -*-
"""
T-02 压缩端 v2（tmp 验证副本，字节级无损口径）
=========================================================
v1 -> v2 修改：
  - import _t02_common_v2（段拼接 == 原文字节）
  - encode_sentence / decode_sentence 统一 surrogateescape（非法 UTF-8 字节无损往返）
  - build_dict 计数同 v2 tokenize
其余逻辑（字典化 -> varint -> zlib 物理层）不变。
"""
import argparse
import json
import os
import struct
import sys
import time
import zlib
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _t02_common import tokenize

sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ENC = 'utf-8'
ENC_KW = {'errors': 'surrogateescape'}


def build_dict(store, dict_size):
    cnt = Counter()
    for s in store['S']:
        for kind, text in tokenize(s):
            if kind in ('ascii', 'cjk'):
                cnt[text] += 1
    top = cnt.most_common(dict_size)
    d = {w: i for i, (w, _) in enumerate(top)}
    return d, top


def _varint(n):
    b = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n:
            b.append(x | 0x80)
        else:
            b.append(x)
            return bytes(b)


def encode_sentence(norm, d):
    out = bytearray()
    for kind, text in tokenize(norm):
        if kind in ('ascii', 'cjk') and text in d:
            out.append(0)
            out.extend(_varint(d[text] + 1))
            out.append(0)
        else:
            b = text.encode(ENC, **ENC_KW)
            for ch in b:
                if ch == 0:
                    out.extend(b'\x00\x00')
                else:
                    out.append(ch)
    return bytes(out)


def decode_sentence(enc, id2word):
    out = []
    i = 0
    n = len(enc)
    raw = bytearray()

    def flush_raw():
        nonlocal raw
        if raw:
            out.append(raw.decode(ENC, **ENC_KW))
            raw = bytearray()

    while i < n:
        b = enc[i]
        if b == 0:
            if i + 1 < n and enc[i + 1] == 0:
                raw.append(0)
                i += 2
                continue
            flush_raw()
            i += 1
            val = 0
            shift = 0
            while True:
                c = enc[i]
                i += 1
                val |= (c & 0x7F) << shift
                if not (c & 0x80):
                    break
                shift += 7
            assert enc[i] == 0, 'delimiter expected'
            i += 1
            out.append(id2word[val - 1])
        else:
            raw.append(b)
            i += 1
    flush_raw()
    return ''.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--store', required=True)
    ap.add_argument('--meta', required=True)
    ap.add_argument('--dict-size', type=int, required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--zlib', action='store_true')
    args = ap.parse_args()

    with open(args.store, encoding='utf-8', errors='surrogateescape') as f:
        store = json.load(f)
    with open(args.meta, encoding='utf-8', errors='surrogateescape') as f:
        meta = json.load(f)
    total_bytes = meta['total_bytes']
    S = store['S']
    P = store['P']

    t0 = time.time()
    d, top = build_dict(store, args.dict_size)
    print(f'dict built: size={len(d)} elapsed={time.time()-t0:.1f}s')

    t1 = time.time()
    s_enc = [encode_sentence(s, d) for s in S]
    print(f'S encoded: {len(S):,} sentences elapsed={time.time()-t1:.1f}s')

    t2 = time.time()
    seg_keys = sorted(int(k) for k in P.keys())
    p_bytes = bytearray()
    prev_seg = 0
    for seg in seg_keys:
        ids = P[str(seg)]
        p_bytes.extend(_varint(seg - prev_seg))
        prev_seg = seg
        p_bytes.extend(_varint(len(ids)))
        prev_id = 0
        for sid in ids:
            p_bytes.extend(_varint(sid ^ prev_id))
            prev_id = sid
    print(f'P encoded: {len(seg_keys):,} segs elapsed={time.time()-t2:.1f}s')

    out_p = args.out
    os.makedirs(os.path.dirname(out_p), exist_ok=True)
    t3 = time.time()
    with open(out_p, 'wb') as f:
        f.write(b'FRV72\n')
        dict_json = json.dumps(top, ensure_ascii=False).encode('utf-8')
        f.write(struct.pack('<I', len(dict_json)))
        f.write(dict_json)
        f.write(struct.pack('<I', len(s_enc)))
        for b in s_enc:
            f.write(struct.pack('<I', len(b)))
            f.write(b)
        f.write(p_bytes)
    if args.zlib:
        raw = open(out_p, 'rb').read()
        comp = zlib.compress(raw, 6)
        out_p = out_p + '.z' if not out_p.endswith('.z') else out_p
        with open(out_p, 'wb') as f:
            f.write(comp)
    sz = os.path.getsize(out_p)
    print(f'written: {out_p} bytes={sz:,} ratio={sz/total_bytes:.4f} '
          f'compression={total_bytes/sz:.2f}x elapsed={time.time()-t3:.1f}s')

    # 无损校验：展开 S 与 store 原文逐字比对（机器级，错误必须 = 0）
    t4 = time.time()
    id2word = {i: w for w, i in d.items()}
    ok = 0
    bad = 0
    first_bad = []
    for s, enc in zip(S, s_enc):
        dec = decode_sentence(enc, id2word)
        if dec == s:
            ok += 1
        else:
            bad += 1
            if len(first_bad) < 3:
                first_bad.append((s[:120], dec[:120]))
    print(f'lossless check(S): ok={ok:,} bad={bad:,} elapsed={time.time()-t4:.1f}s')
    if bad:
        for s, dec in first_bad:
            print('  MISMATCH:')
            print('   SRC:', repr(s))
            print('   DEC:', repr(dec))

    summary = {'corpus': meta.get('corpus'), 'seg_mode': meta.get('seg_mode'),
               'dict_size': args.dict_size, 'zlib': args.zlib,
               'store_bytes': sz, 'ratio': round(sz / total_bytes, 4),
               'compression': round(total_bytes / sz, 2),
               'lossless_ok': ok, 'lossless_bad': bad,
               'total_bytes': total_bytes, 'n_sents': len(S),
               'out': os.path.basename(out_p)}
    sum_p = os.path.splitext(out_p)[0] + '_summary.json'
    with open(sum_p, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print('summary:', sum_p)
    print('=' * 60)
    print('J1 字节无损（压缩端自检，展开 S==store S）:', 'PASS' if bad == 0 else 'FAIL')


if __name__ == '__main__':
    main()
