# -*- coding: utf-8 -*-
"""
T-02 痕迹采样端 v2（tmp 验证副本，v2 迭代器口径 + seed 固定随机抽样）
=========================================================
v1 -> v2 修改：import _t02_common_v2（段拼接 == 原文字节，surrogateescape）
主域 295 条痕迹（随机抽样防 295 恰好命中）
"""
import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _t02_common import iter_segments_marker, iter_segments_window

sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TOKEN_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.\-]*')
CJK_RE = re.compile(r'[\u4e00-\u9fff]{3,}')


def cjk_trigrams(text):
    out = set()
    for m in CJK_RE.finditer(text):
        s = m.group(0)
        for j in range(0, len(s) - 2):
            out.add(s[j:j + 3])
    return out


def pass1(path, seg_mode, seg_marker, window_chars):
    if seg_mode == 'marker':
        it = iter_segments_marker(path, seg_marker)
    else:
        it = iter_segments_window(path, window_chars)
    ascii_df = defaultdict(int)
    cjk_df = defaultdict(int)
    n_seg = 0
    for seg_no, text in it:
        n_seg += 1
        toks = set()
        for m in TOKEN_RE.finditer(text):
            tok = m.group(0)
            if re.search(r'[A-Za-z]', tok):
                toks.add(tok)
        for tok in toks:
            ascii_df[tok] += 1
        for g in cjk_trigrams(text):
            cjk_df[g] += 1
    return ascii_df, cjk_df, n_seg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--seg-mode', required=True, choices=['marker', 'window'])
    ap.add_argument('--seg-marker', default='=== seq=')
    ap.add_argument('--window-chars', type=int, default=4000)
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--n-ascii', type=int, default=150)
    ap.add_argument('--n-cjk', type=int, default=100)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    t0 = time.time()
    ascii_df, cjk_df, n_seg = pass1(args.corpus, args.seg_mode, args.seg_marker, args.window_chars)
    print(f'[pass1] segs={n_seg} ascii_candidates={len(ascii_df):,} '
          f'cjk_candidates={len(cjk_df):,} elapsed={time.time()-t0:.1f}s')

    ascii_pool = [e for e, df in ascii_df.items() if 2 <= df <= 50000]
    cjk_pool = [g for g, df in cjk_df.items() if 2 <= df <= 50000]
    rng = random.Random(args.seed)
    n_ascii = min(args.n_ascii, len(ascii_pool))
    n_cjk = min(args.n_cjk, len(cjk_pool))
    ascii_sample = rng.sample(ascii_pool, n_ascii)
    cjk_sample = rng.sample(cjk_pool, n_cjk)
    print(f'[sample] ascii={len(ascii_sample)} (pool {len(ascii_pool):,}) '
          f'cjk={len(cjk_sample)} (pool {len(cjk_pool):,}) seed={args.seed}')

    ascii_set = set(ascii_sample)
    cjk_set = set(cjk_sample)
    e0 = {e: [] for e in ascii_set}
    e0.update({g: [] for g in cjk_set})
    it = (iter_segments_marker(args.corpus, args.seg_marker)
          if args.seg_mode == 'marker'
          else iter_segments_window(args.corpus, args.window_chars))
    n2 = 0
    t1 = time.time()
    for seg_no, text in it:
        n2 += 1
        toks = set()
        for m in TOKEN_RE.finditer(text):
            tok = m.group(0)
            if re.search(r'[A-Za-z]', tok):
                toks.add(tok)
        hit = toks & ascii_set
        for h in hit:
            e0[h].append(seg_no)
        grams = cjk_trigrams(text)
        hit2 = grams & cjk_set
        for h in hit2:
            e0[h].append(seg_no)
    print(f'[E0] segs={n2} elapsed={time.time()-t1:.1f}s')

    traces = {}
    for e, lst in e0.items():
        kind = 'cjk' if re.search(r'[\u4e00-\u9fff]', e) else 'ascii'
        traces[e] = {'kind': kind, 'E0': lst}
    doc = {
        'corpus': os.path.basename(args.corpus),
        'seg_mode': args.seg_mode,
        'seg_marker': args.seg_marker if args.seg_mode == 'marker' else None,
        'window_chars': args.window_chars if args.seg_mode == 'window' else None,
        'seed': args.seed,
        'n_seg': n_seg,
        'n_ascii': len(ascii_sample), 'n_cjk': len(cjk_sample),
        'total': len(traces),
        'traces': traces,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    sha = hashlib.sha256(open(args.out, 'rb').read()).hexdigest()
    print(f'[traces] total={len(traces)} 已落盘 {args.out}')
    print(f'[GT SHA-256] {sha}')
    print(f'总耗时: {time.time()-t0:.1f} s')


if __name__ == '__main__':
    main()
