# -*- coding: utf-8 -*-
"""文本切块：500 字/上限 800/重叠 80，中文句子边界处切分（防截断）。"""
import re

from server.core.models import Chunk, Document

# 目标块大小（字符）、硬上限、相邻重叠（字符）
CHUNK_TARGET = 500
CHUNK_MAX = 800
CHUNK_OVERLAP = 80

# 中文/英文句子终止符
_SENT_END = re.compile(r"(?<=[。！？!?；;\n])")


def split_text(text: str) -> list[str]:
    """核心切块函数（纯函数，离线可测）。

    规则：
    1. 每个块尽量接近 CHUNK_TARGET 字符，硬上限 CHUNK_MAX 强制截断；
    2. 优先在句子终止符处切，避免把一句话劈两半；
    3. 相邻块保留 CHUNK_OVERLAP 重叠，防主题断裂。
    """
    text = text.strip()
    if not text:
        return []

    # 先按句子终止符切开，再贪心合并到 target 附近
    sentences = [s.strip() for s in _SENT_END.split(text) if s.strip()]
    # 没有标点分隔的长文本，直接按长度硬切
    if not sentences:
        sentences = _hard_split(text)

    chunks: list[str] = []
    current = ""
    for sent in sentences:
        # 单句超过上限的兜底硬切
        if len(sent) > CHUNK_MAX:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(sent))
            continue
        # 加上当前句会超上限 → 结算当前块
        if len(current) + len(sent) > CHUNK_MAX:
            chunks.append(current.strip())
            # 重叠：从当前块尾部取 overlap 字符接续
            current = current[-CHUNK_OVERLAP:] if len(current) >= CHUNK_OVERLAP else current
        current += sent
        # 超过目标宽度就结算，避免块过长
        if len(current) >= CHUNK_TARGET:
            chunks.append(current.strip())
            current = current[-CHUNK_OVERLAP:] if len(current) >= CHUNK_OVERLAP else current

    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if c]


def _hard_split(text: str, step: int = CHUNK_MAX) -> list[str]:
    """按固定长度硬切，返回不含重叠的片段。"""
    return [text[i : i + step] for i in range(0, len(text), step)]


def chunk_document(doc: Document, text: str, tags: list[str] | None = None) -> list[Chunk]:
    """把整篇文本解析为 Chunk 列表（按 section 留空、doc_id 标记）。

    tags：多标签（D12），对整篇生效，后续可按块微调。
    """
    return [
        Chunk(doc_id=doc.id or 0, title=doc.title, section="", text=t, tags=list(tags or []))
        for t in split_text(text)
    ]