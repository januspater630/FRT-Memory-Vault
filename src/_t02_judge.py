# -*- coding: utf-8 -*-
"""
T-02 判据端 v2（字节级无损口径 + J1/J2/J3/J4 全判据）
=========================================================
判据定义（对应主域 D3 字节级重跑四件套）:
  J1: decode(encode(x)) == x，SHA-256 前后完全一致（字节一样，不是句子一样）
  J2: 295 条痕迹位置恢复率 >= 99%（最好 100%）
  J3: 20 题司南 -> 要件 -> L2 -> 原文证据段闭环
  J4: 随机抽样人工核验（防止机器判据自己骗自己）
总判据: SHA256(X) == SHA256(D(E(X)))

v1 -> v2 修改：
  - load 支持 FRV72 magic（v2 产物）
  - J1 升级：重建全文 -> 写盘 -> SHA-256 == 原文 SHA-256（文件字节级，非迭代器级）
  - 新增 J3 / J4
  - 读语料统一 surrogateescape
"""
import argparse
import hashlib
import io
import json
import os
import random
import re
import struct
import sys
import time
import zlib
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _t02_common import (iter_segments_marker, iter_segments_window)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ENC = 'utf-8'
ENC_KW = {'errors': 'surrogateescape'}

TOKEN_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.\-]*')
CJK_RE = re.compile(r'[\u4e00-\u9fff]{3,}')


def read_varint(data, i):
    val = 0
    shift = 0
    while True:
        b = data[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return val, i


def load_v7x(bin_path):
    with open(bin_path, 'rb') as f:
        data = f.read()
    if bin_path.endswith('.z'):
        data = zlib.decompress(data)
    assert data[:6] in (b'FRV71\n', b'FRV72\n'), 'bad magic'
    i = 6
    (dlen,) = struct.unpack_from('<I', data, i); i += 4
    dict_json = data[i:i + dlen].decode('utf-8'); i += dlen
    id2word = {idx: w for idx, (w, _) in enumerate(json.loads(dict_json))}
    (ns,) = struct.unpack_from('<I', data, i); i += 4
    s_enc = []
    for _ in range(ns):
        (blen,) = struct.unpack_from('<I', data, i); i += 4
        s_enc.append(data[i:i + blen]); i += blen
    p_bytes = data[i:]

    S = [decode_sentence(b, id2word) for b in s_enc]

    P = {}
    j = 0
    seg = 0
    while j < len(p_bytes):
        dseg, j = read_varint(p_bytes, j)
        seg += dseg
        nids, j = read_varint(p_bytes, j)
        ids = []
        prev = 0
        for _ in range(nids):
            x, j = read_varint(p_bytes, j)
            sid = x ^ prev
            ids.append(sid)
            prev = sid
        P[str(seg)] = ids
    return S, P


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


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def rebuild_full_text(S, P, seg_mode, seg_marker, window_chars):
    """按 P 重建每段文本（v2 口径：段文本 = ''.join(行)）。返回 {seg_no: text}。"""
    seg_texts = {}
    for seg_str, ids in P.items():
        seg = int(seg_str)
        seg_texts[seg] = ''.join(S[sid] for sid in ids)
    return seg_texts


def j1_file_sha(S, P, corpus, seg_mode, seg_marker, window_chars):
    """J1：重建全文 -> SHA-256 vs 原文 SHA-256（pater 总判据）。同时逐段比对定位错误。"""
    sha_orig = sha256_file(corpus)
    seg_texts = rebuild_full_text(S, P, seg_mode, seg_marker, window_chars)

    # 逐段比对（v2 迭代器口径）
    if seg_mode == 'marker':
        it = iter_segments_marker(corpus, seg_marker)
    else:
        it = iter_segments_window(corpus, window_chars)
    seg_ok = 0
    seg_bad = 0
    total_chars = 0
    first_bad = []
    for seg_no, text in it:
        total_chars += len(text)
        rebuilt = seg_texts.get(seg_no)
        if rebuilt is None:
            seg_bad += 1
            if len(first_bad) < 3:
                first_bad.append((seg_no, 'P missing', text[:120]))
            continue
        if rebuilt != text:
            seg_bad += 1
            if len(first_bad) < 3:
                first_bad.append((seg_no, text[:120], rebuilt[:120]))
        else:
            seg_ok += 1

    # 重建全文（按段号排序拼接）写盘，SHA-256 比对
    ordered = [(seg, seg_texts[seg]) for seg in sorted(seg_texts.keys())]
    full = ''.join(t for _, t in ordered)
    rebuilt_bytes = full.encode(ENC, **ENC_KW)
    sha_rebuilt = hashlib.sha256(rebuilt_bytes).hexdigest()
    sha_pass = (sha_rebuilt == sha_orig)

    return {
        'sha_orig': sha_orig,
        'sha_rebuilt': sha_rebuilt,
        'sha_pass': sha_pass,
        'rebuilt_bytes': len(rebuilt_bytes),
        'seg_ok': seg_ok, 'seg_bad': seg_bad,
        'total_chars': total_chars,
        'first_bad': first_bad[:3],
    }


def ascii_tokens(text):
    out = set()
    for m in TOKEN_RE.finditer(text):
        tok = m.group(0)
        if re.search(r'[A-Za-z]', tok):
            out.add(tok)
    return out


def cjk_trigrams(text):
    out = set()
    for m in CJK_RE.finditer(text):
        s = m.group(0)
        for j in range(0, len(s) - 2):
            out.add(s[j:j + 3])
    return out


def build_invP(P):
    invP = defaultdict(set)
    for seg_str, ids in P.items():
        seg = int(seg_str)
        for sid in ids:
            invP[sid].add(seg)
    return invP


def j2_trace_recovery(S, P, traces):
    e0 = {}
    for e, v in traces.items():
        if v['E0']:
            e0[e] = {'kind': v['kind'], 'E0': set(v['E0'])}
    ascii_set = {e for e, v in e0.items() if v['kind'] == 'ascii'}
    cjk_set = {e for e, v in e0.items() if v['kind'] == 'cjk'}

    invP = build_invP(P)
    sent_hits = defaultdict(set)
    t0 = time.time()
    for sid, s in enumerate(S):
        toks = ascii_tokens(s)
        hit = toks & ascii_set
        for h in hit:
            sent_hits[h].add(sid)
        grams = cjk_trigrams(s)
        hit2 = grams & cjk_set
        for h in hit2:
            sent_hits[h].add(sid)
    print(f'  [scan S] S={len(S):,} hits={len(sent_hits):,} elapsed={time.time()-t0:.1f}s')

    e1 = {}
    for e, sids in sent_hits.items():
        segs = set()
        for sid in sids:
            segs |= invP[sid]
        e1[e] = segs

    pos_total = 0
    pos_rec = 0
    covs = []
    below = []
    for e, v in e0.items():
        e0s = v['E0']
        e1s = e1.get(e, set())
        rec = e1s & e0s
        cov = len(rec) / len(e0s)
        pos_total += len(e0s)
        pos_rec += len(rec)
        covs.append(cov)
        if cov < 0.99:
            below.append((e, v['kind'], round(cov, 4), len(e0s), len(e1s)))
    covs.sort()
    below.sort(key=lambda x: x[2])
    res = {
        'n_traces': len(e0),
        'pos_total': pos_total, 'pos_recovered': pos_rec,
        'position_rate': round(pos_rec / pos_total, 4),
        'trace_full_rate_1.0': round(sum(1 for c in covs if c >= 1.0) / len(covs), 4),
        'trace_ge99': round(sum(1 for c in covs if c >= 0.99) / len(covs), 4),
        'mean_cov': round(sum(covs) / len(covs), 4),
        'min_cov': round(covs[0], 4),
        'below_99_count': len(below),
        'below_99_sample': below[:40],
    }
    return res


def j3_questions(S, P, gt_map, corpus, seg_mode, seg_marker, window_chars):
    """J3：20 题要件 -> 证据段闭环。
    E0（原文证据段）用判据端 v2 迭代器在原文上重新定位（与展开 S/P 同口径）。
    要件词列表来自密封 GT gt_evidence_map_main.json（压缩器零接触）。"""
    # 原文 E0 定位（v2 口径）
    if seg_mode == 'marker':
        it = iter_segments_marker(corpus, seg_marker)
    else:
        it = iter_segments_window(corpus, window_chars)

    def is_ascii(e):
        return not re.search(r'[\u4e00-\u9fff]', e)

    # 收集全部要件词
    term_kind = {}
    for q in gt_map['questions']:
        for e in q['key_entities']:
            term_kind[e] = 'ascii' if is_ascii(e) else 'cjk'
    ascii_set = {e for e, k in term_kind.items() if k == 'ascii'}
    cjk_terms = [e for e, k in term_kind.items() if k == 'cjk']

    e0 = defaultdict(set)
    t0 = time.time()
    for seg_no, text in it:
        toks = ascii_tokens(text)
        hit = toks & ascii_set
        for h in hit:
            e0[h].add(seg_no)
        for t in cjk_terms:
            if t in text:
                e0[t].add(seg_no)
    print(f'  [J3 E0] segs scanned, terms={len(term_kind)} elapsed={time.time()-t0:.1f}s')

    # 展开 S/P 上 E1 定位（与 E0 完全对称：ascii token 精确匹配 + cjk 子串匹配）
    invP = build_invP(P)
    sent_hits = defaultdict(set)
    for sid, s in enumerate(S):
        toks = ascii_tokens(s)
        hit = toks & ascii_set
        for h in hit:
            sent_hits[h].add(sid)
        for t in cjk_terms:
            if t in s:
                sent_hits[t].add(sid)
    e1 = {}
    for e, sids in sent_hits.items():
        segs = set()
        for sid in sids:
            segs |= invP[sid]
        e1[e] = segs

    # 每题统计
    q_res = []
    n_ok = 0
    n_all = 0
    for q in gt_map['questions']:
        ents = q['key_entities']
        e0_union = set()
        e1_union = set()
        per_ent = []
        for e in ents:
            e0s = e0.get(e, set())
            e1s = e1.get(e, set())
            rec = e1s & e0s
            cov = len(rec) / len(e0s) if e0s else 1.0
            per_ent.append({'entity': e, 'e0': len(e0s), 'e1': len(e1s), 'rec': len(rec), 'cov': round(cov, 4)})
            e0_union |= e0s
            e1_union |= e1s
        # 证据段（任一要件段）恢复率
        rec_union = e1_union & e0_union
        cov_union = len(rec_union) / len(e0_union) if e0_union else 1.0
        q_res.append({
            'qid': q['qid'], 'question': q['question'],
            'key_entities': ents, 'per_entity': per_ent,
            'e0_segs': len(e0_union), 'e1_segs': len(e1_union),
            'rec_segs': len(rec_union), 'evidence_cov': round(cov_union, 4),
        })
        if cov_union >= 0.99:
            n_ok += 1
        n_all += 1

    covs = [q['evidence_cov'] for q in q_res]
    return {
        'n_questions': n_all,
        'questions_ge99': n_ok,
        'questions_ge99_rate': round(n_ok / n_all, 4),
        'mean_cov': round(sum(covs) / len(covs), 4),
        'min_cov': round(min(covs), 4),
        'detail': q_res,
    }


def j4_sample_check(S, P, corpus, seg_mode, seg_marker, window_chars,
                    seed=20260830, n=20, out_path=None):
    """J4：随机抽样人工核验。随机抽 n 段，输出 原文段 vs 重建段 对照。"""
    seg_texts = rebuild_full_text(S, P, seg_mode, seg_marker, window_chars)
    if seg_mode == 'marker':
        it = iter_segments_marker(corpus, seg_marker)
    else:
        it = iter_segments_window(corpus, window_chars)
    orig = {}
    for seg_no, text in it:
        orig[seg_no] = text
    seg_nos = sorted(set(orig.keys()) & set(seg_texts.keys()))
    rng = random.Random(seed)
    sample = rng.sample(seg_nos, min(n, len(seg_nos)))

    lines = []
    all_ok = True
    for s in sample:
        o = orig[s]
        r = seg_texts[s]
        same = (o == r)
        if not same:
            all_ok = False
        lines.append('=' * 70)
        lines.append(f'SEG {s}  match={same}  len_orig={len(o)} len_rebuilt={len(r)}')
        lines.append('--- ORIG ---')
        lines.append(o[:500])
        lines.append('--- REBUILT ---')
        lines.append(r[:500])
    report = '\n'.join(lines)
    if out_path:
        with open(out_path, 'w', encoding='utf-8', errors='surrogateescape') as f:
            f.write(report)
    return {'n_sampled': len(sample), 'all_match': all_ok, 'out': out_path}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bin', required=True)
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--traces', required=True)
    ap.add_argument('--seg-mode', required=True, choices=['marker', 'window'])
    ap.add_argument('--seg-marker', default='=== seq=')
    ap.add_argument('--window-chars', type=int, default=4000)
    ap.add_argument('--gt-map', default='')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    t0 = time.time()
    S, P = load_v7x(args.bin)
    print(f'[load_v7x] S={len(S):,} P_segs={len(P):,} elapsed={time.time()-t0:.1f}s')

    # ===== J1 字节/文件级无损（SHA-256 总判据）=====
    t1 = time.time()
    j1 = j1_file_sha(S, P, args.corpus, args.seg_mode, args.seg_marker, args.window_chars)
    print(f'[J1] sha_pass={j1["sha_pass"]} seg_ok={j1["seg_ok"]:,} seg_bad={j1["seg_bad"]:,} '
          f'elapsed={time.time()-t1:.1f}s')
    if j1['first_bad']:
        for seg_no, a, b in j1['first_bad'][:3]:
            print('  SEG_BAD', seg_no)
            print('   SRC:', repr(a[:200]))
            print('   REB:', repr(b[:200]))

    # ===== J2 痕迹恢复 =====
    with open(args.traces, encoding='utf-8') as f:
        gt = json.load(f)
    t2 = time.time()
    j2 = j2_trace_recovery(S, P, gt['traces'])
    print(f'[J2] elapsed={time.time()-t2:.1f}s')

    # ===== J3 20 题要件闭环 =====
    j3 = None
    if args.gt_map and os.path.exists(args.gt_map):
        with open(args.gt_map, encoding='utf-8') as f:
            gt_map = json.load(f)
        t3 = time.time()
        j3 = j3_questions(S, P, gt_map, args.corpus, args.seg_mode, args.seg_marker, args.window_chars)
        print(f'[J3] questions_ge99={j3["questions_ge99"]}/{j3["n_questions"]} '
              f'mean_cov={j3["mean_cov"]} elapsed={time.time()-t3:.1f}s')
    else:
        print('[J3] skipped (no --gt-map)')

    # ===== J4 随机抽样人工核验 =====
    j4_out = os.path.splitext(args.out)[0] + '_j4_sample.txt'
    j4 = j4_sample_check(S, P, args.corpus, args.seg_mode, args.seg_marker, args.window_chars,
                         out_path=j4_out)
    print(f'[J4] n_sampled={j4["n_sampled"]} all_match={j4["all_match"]} out={j4_out}')

    result = {
        'bin': os.path.basename(args.bin),
        'corpus': os.path.basename(args.corpus),
        'traces_sha': gt.get('sha256', ''),
        'J1_file_sha': j1,
        'J1_pass': j1['sha_pass'] and j1['seg_bad'] == 0,
        'J2_trace_recovery': j2,
        'J2_pass_ge99': j2['trace_ge99'] >= 0.99,
        'J3_questions': j3,
        'J4_sample': j4,
        'total_judge_pass': (j1['sha_pass'] and j1['seg_bad'] == 0
                             and j2['trace_ge99'] >= 0.99
                             and (j3 is None or j3['questions_ge99_rate'] >= 0.99)
                             and j4['all_match']),
    }
    print('=' * 60)
    print('J1 SHA-256 总判据 :', 'PASS' if j1['sha_pass'] else 'FAIL',
          f'({j1["sha_rebuilt"][:16]}...)')
    print('J1 逐段比对       :', 'PASS' if j1['seg_bad'] == 0 else 'FAIL',
          f'({j1["seg_ok"]:,}/{j1["seg_ok"]+j1["seg_bad"]:,})')
    print('J2 痕迹恢复       : ge99={:.4f} full1.0={:.4f} pos={:.4f} below_99={}'.format(
        j2['trace_ge99'], j2['trace_full_rate_1.0'], j2['position_rate'],
        j2['below_99_count']))
    if j3:
        print('J3 20题证据段     : ge99={:.4f} mean={:.4f} min={:.4f}'.format(
            j3['questions_ge99_rate'], j3['mean_cov'], j3['min_cov']))
    print('J4 人工抽样       :', 'PASS' if j4['all_match'] else 'FAIL',
          f'({j4["n_sampled"]} 段)')
    print('综合判据          :', 'PASS' if result['total_judge_pass'] else 'FAIL')

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print('结果落盘:', args.out)
    print(f'总耗时: {time.time()-t0:.1f} s')


if __name__ == '__main__':
    main()
