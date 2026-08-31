# -*- coding: utf-8 -*-
"""
T-02 字节级公共模块 v2（tmp 验证副本）
=========================================================
相对 v1 的修复（字节级无损漏洞）：
  1. iter_segments_marker / iter_segments_window 改为**段拼接 == 原文字节**：
     - v1 用 line.rstrip('\\n') + '\\n'.join()，段尾换行丢失 → 段拼接 != 原文
     - v2 每行原样保留（含 \\r\\n），段文本 = ''.join(lines)，段拼接 == 文件字节精确切片
  2. 读文件统一 errors='surrogateescape'：非法 UTF-8 字节无损往返（对主域合法 UTF-8 无影响，
     对含非法字节的文件是字节级无损的必要条件）
"""
import re

SPLIT_RE = re.compile(r'([。！？!?\n]+)')   # 捕获组：保留句读/换行
TOKEN_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.\-]*')
CJK_RUN_RE = re.compile(r'[\u4e00-\u9fff]{2,}')

# newline='' 禁用 universal newlines 翻译（\r\n 保留原样，字节级无损必要条件）
OPEN_KW = {'encoding': 'utf-8', 'errors': 'surrogateescape', 'newline': ''}


def iter_segments_marker(path, marker):
    """marker 分段（字节级无损）：以 marker 开头的行作为新段起点。
    段内容 = 行原样拼接（含行尾换行），段拼接 == 原文精确字节切片。"""
    seg_text = []
    seg_no = 0

    def flush():
        nonlocal seg_text, seg_no
        if not seg_text:
            return None
        text = ''.join(seg_text)
        seg_text = []
        seg_no += 1
        return (seg_no, text)

    with open(path, 'r', **OPEN_KW) as f:
        for line in f:
            if line.startswith(marker):
                r = flush()
                if r:
                    yield r
            seg_text.append(line)
    r = flush()
    if r:
        yield r


def iter_segments_window(path, window_chars):
    """固定字符窗口分段（字节级无损）：行原样保留，段文本 = 行拼接，段拼接 == 原文精确。"""
    seg_no = 0
    buf = []
    buf_len = 0
    with open(path, 'r', **OPEN_KW) as f:
        for line in f:
            if buf and buf_len + len(line) > window_chars:
                seg_no += 1
                yield (seg_no, ''.join(buf))
                buf = []
                buf_len = 0
            buf.append(line)
            buf_len += len(line)
    if buf:
        seg_no += 1
        yield (seg_no, ''.join(buf))


def split_sentences(text):
    """字节级无损分句：句子单元 = 文本片段 + 分隔符（句读/换行全部保留）。
    空 piece 且无分隔符的尾部跳过。返回 [(unit, blen)]。"""
    pieces = SPLIT_RE.split(text)
    out = []
    i = 0
    n = len(pieces)
    while i < n:
        piece = pieces[i]
        sep = pieces[i + 1] if i + 1 < n else ''
        if piece == '' and sep == '':
            i += 2
            continue
        unit = piece + sep
        blen = len(unit.encode('utf-8', errors='surrogateescape'))
        if blen > 65535:
            blen = 65535
        out.append((unit, blen))
        i += 2
    return out


def iter_sentences_of_segment(text):
    return [u for u, _ in split_sentences(text)]


def tokenize(norm):
    """把句子切成 (kind, text) 序列：ascii token / cjk run / 其他原文片段。"""
    parts = []
    i = 0
    n = len(norm)
    for m in TOKEN_RE.finditer(norm):
        if m.start() > i:
            parts.append(('raw', norm[i:m.start()]))
        parts.append(('ascii', m.group(0)))
        i = m.end()
    if i < n:
        parts.append(('raw', norm[i:]))
    out = []
    for kind, text in parts:
        if kind == 'raw':
            j = 0
            for m in CJK_RUN_RE.finditer(text):
                if m.start() > j:
                    out.append(('raw', text[j:m.start()]))
                out.append(('cjk', m.group(0)))
                j = m.end()
            if j < len(text):
                out.append(('raw', text[j:]))
        else:
            out.append((kind, text))
    return out
