# -*- coding: utf-8 -*-
"""
T-02 建 store 端 v2（tmp 验证副本，字节级无损口径）
=========================================================
v1 -> v2 修改：import _t02_common_v2（段拼接 == 原文字节，surrogateescape）
其余逻辑不变。
"""
import argparse
import json
import os
import sys
import time
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _t02_common import (iter_segments_marker, iter_segments_window, split_sentences)

sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def s_key(unit, blen):
    crc = zlib.crc32(unit.encode('utf-8', errors='surrogateescape')) & 0xFFFFFFFF
    return (crc << 16) | (blen & 0xFFFF)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--meta', required=True)
    ap.add_argument('--seg-mode', required=True, choices=['marker', 'window'])
    ap.add_argument('--seg-marker', default='=== seq=')
    ap.add_argument('--window-chars', type=int, default=4000)
    args = ap.parse_args()

    if args.seg_mode == 'marker':
        it = iter_segments_marker(args.corpus, args.seg_marker)
    else:
        it = iter_segments_window(args.corpus, args.window_chars)

    t0 = time.time()
    total_chars = 0
    total_bytes = 0
    n_seg = 0
    key2id = {}
    uniq_list = []
    per_seg = {}
    occ = 0
    for seg_no, text in it:
        n_seg += 1
        total_chars += len(text)
        total_bytes += len(text.encode('utf-8', errors='surrogateescape'))
        ids = []
        for unit, blen in split_sentences(text):
            k = s_key(unit, blen)
            sid = key2id.get(k)
            if sid is None:
                sid = len(uniq_list)
                key2id[k] = sid
                uniq_list.append(unit)
            ids.append(sid)
            occ += 1
        if ids:
            per_seg[str(seg_no)] = ids

    store = {'S': uniq_list, 'P': per_seg}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8', errors='surrogateescape') as f:
        json.dump(store, f, ensure_ascii=False)
    meta = {'corpus': os.path.basename(args.corpus),
            'seg_mode': args.seg_mode,
            'seg_marker': args.seg_marker if args.seg_mode == 'marker' else None,
            'window_chars': args.window_chars if args.seg_mode == 'window' else None,
            'n_seg': n_seg, 'total_chars': total_chars, 'total_bytes': total_bytes,
            'uniq_sentences': len(uniq_list), 'occ_sentences': occ,
            'store_bytes': os.path.getsize(args.out)}
    with open(args.meta, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    print('=' * 60)
    print('T-02 build_store v2 完成')
    print('=' * 60)
    print(f'语料            : {os.path.basename(args.corpus)}')
    print(f'分段模式        : {args.seg_mode}'
          + (f' window_chars={args.window_chars}' if args.seg_mode == 'window'
             else f' marker={args.seg_marker!r}'))
    print(f'段数            : {n_seg:,}')
    print(f'语料字符数      : {total_chars:,}')
    print(f'语料字节数      : {total_bytes:,}')
    print(f'唯一句子数      : {len(uniq_list):,}')
    print(f'句子出现总次数  : {occ:,}')
    print(f'store 字节      : {meta["store_bytes"]:,}')
    print(f'耗时            : {time.time() - t0:.1f} s')


if __name__ == '__main__':
    main()
