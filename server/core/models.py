# -*- coding: utf-8 -*-
"""统一数据模型：跨模块数据唯一出处，禁止各模块重复定义（ADR D15/D11）。"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Document:
    """建库/管理后台：一份原始攻略材料。"""
    id: Optional[int] = None
    title: str = ""
    source_type: str = "txt"  # pdf/word/excel/ppt/html/txt/md/image
    raw_path: str = ""
    created_at: str = ""


@dataclass
class Chunk:
    """切块后的检索单元。"""
    id: Optional[int] = None
    doc_id: int = 0
    title: str = ""
    section: str = ""
    page: Optional[int] = None
    text: str = ""
    vector: list = field(default_factory=list)
    tags: list = field(default_factory=list)  # 多标签（D12），如 ["新手入门","探索地图"]


@dataclass
class ParsedContent:
    """P2 解析层统一输出。"""
    text: str = ""
    source_type: str = ""
    title: str = ""
    section: str = ""
    page: Optional[int] = None
    meta: dict = field(default_factory=dict)  # 标题/章节/页码/OCR通道等


@dataclass
class Code:
    """密令（兑换码）结构化条目（D13）。"""
    id: Optional[int] = None
    text: str = ""
    reward: str = ""
    status: str = "生效"  # 生效/停用/已过期
    valid_until: str = ""
    batch: str = ""
    remark: str = ""