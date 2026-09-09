# -*- coding: utf-8 -*-
"""知识库存储与检索：SQLite（向量近似 + Rank-BM25 混检）。

表结构：
- documents: 原始文档登记
- chunks:    切块 + embedding(BLOB) + tags(JSON)
- codes:     密令结构化表（D13）

检索（D4/D12）：
- 向量路径：chunks.vector BLOB → numpy 余弦相似度；
- 关键词路径：rank-bm25 对全库文本打分（中文按字/词轻量切分）；
- 融合：score = (1-w)*vec_norm + w*bm25_norm（w=bm25_weight，默认 0.4）；
- 多标签 OR 过滤：tags 任一命中即保留（D12）。
"""
import json
import logging
import sqlite3
from pathlib import Path
from typing import List, Optional

import numpy as np

from server.core.config import settings
from server.core.models import Chunk, Code, Document

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT, source_type TEXT, raw_path TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS chunks(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER, title TEXT, section TEXT, page INTEGER,
    text TEXT, vector BLOB, tags TEXT DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS codes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT UNIQUE, reward TEXT, status TEXT DEFAULT '生效',
    valid_until TEXT, batch TEXT, remark TEXT
);
"""


def _cjk_tokenize(text: str) -> List[str]:
    """轻量中文分词：保留连写英文/数字单词，中文切成字+二元组供 BM25。

    不引 jieba 等重型依赖；对攻略类短查已有足够区分度（D4）。
    """
    import re

    tokens: list[str] = []
    # 英文/数字词
    tokens += re.findall(r"[a-zA-Z0-9]{2,}", text.lower())
    # 中文字（连续）拆成字符和二元组
    cjk = re.findall(r"[\u4e00-\u9fff]+", text)
    for run in cjk:
        if len(run) <= 2:
            tokens.append(run)
        else:
            tokens.extend(run)               # 单字
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))  # 二元组
    return tokens


class KB:
    """SQLite 知识库（repository 模式，便于换 Milvus/pgvector 只换实现）。"""

    def __init__(self, db_path=None):
        self._db_path = str(db_path or settings.kb_db_abs)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._bm25 = None  # rank-bm25 索引缓存，增删库后失效

    # ---------- 建库 ----------
    def add_document(self, doc: Document) -> int:
        cur = self._conn.execute(
            "INSERT INTO documents(title, source_type, raw_path, created_at) VALUES(?,?,?,?)",
            (doc.title, doc.source_type, doc.raw_path, doc.created_at),
        )
        self._conn.commit()
        return cur.lastrowid

    def add_chunks(self, chunks: List[Chunk]) -> None:
        for c in chunks:
            vec_blob = np.asarray(c.vector, dtype=np.float32).tobytes() if c.vector else b""
            self._conn.execute(
                "INSERT INTO chunks(doc_id,title,section,page,text,vector,tags) VALUES(?,?,?,?,?,?,?)",
                (c.doc_id, c.title, c.section, c.page, c.text, vec_blob, json.dumps(c.tags, ensure_ascii=False)),
            )
        self._conn.commit()
        self._bm25 = None  # 索引失效

    def rebuild_fts(self) -> None:
        """兼容占位（检索走 rank-bm25，无需 FTS5）。"""
        self._bm25 = None

    def clear(self) -> None:
        self._conn.executescript("DELETE FROM chunks; DELETE FROM documents; DELETE FROM codes;")
        self._conn.commit()
        self._bm25 = None

    # ---------- 密令（D13，query_codes 用） ----------
    def add_code(self, code: Code) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO codes(text,reward,status,valid_until,batch,remark) VALUES(?,?,?,?,?,?)",
            (code.text, code.reward, code.status, code.valid_until, code.batch, code.remark),
        )
        self._conn.commit()

    def search_codes(self, keyword: str = "") -> List[dict]:
        if keyword:
            rows = self._conn.execute(
                "SELECT id,text,reward,status,valid_until,batch FROM codes "
                "WHERE status='生效' AND text LIKE ? ORDER BY valid_until DESC",
                (f"%{keyword}%",),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id,text,reward,status,valid_until,batch FROM codes "
                "WHERE status='生效' ORDER BY valid_until DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ---------- 检索 ----------
    def search(self, vec: List[float], top_k: Optional[int] = None, tags: Optional[List[str]] = None,
               query: str = "") -> List[dict]:
        """混检：向量余弦 + BM25 加权融合；tags 多标签 OR 过滤；query 供 BM25。"""
        top_k = top_k or settings.top_k_default

        rows = self._conn.execute(
            "SELECT id, doc_id, title, section, page, text, tags, vector FROM chunks"
        ).fetchall()
        if not rows:
            return []

        # 1) 向量路径
        q = np.asarray(vec, dtype=np.float32)
        qn = np.linalg.norm(q)
        vec_hits: list[dict] = []
        for r in rows:
            blob = r["vector"]
            if not blob:
                continue
            v = np.frombuffer(blob, dtype=np.float32)
            vn = np.linalg.norm(v)
            if vn == 0:
                continue
            hit = dict(r)
            hit["vec_score"] = float(np.dot(q, v)) / (qn * vn)
            hit["tags"] = _parse_tags(hit.get("tags"))
            hit.pop("vector", None)
            vec_hits.append(hit)
        vec_hits.sort(key=lambda h: h["vec_score"], reverse=True)
        max_vec = vec_hits[0]["vec_score"] if vec_hits else 1.0

        # 2) 关键词路径（rank-bm25）
        bm_hits = self._bm25_rank(query if query else "", rows, top_k)

        # 3) 融合
        merged: dict[int, dict] = {}
        for h in vec_hits[: max(10, top_k * 3)]:
            merged[h["id"]] = {**h, "score": (h["vec_score"] / max_vec if max_vec else 0) * (1 - settings.bm25_weight)}
        bmax = max((x[1] for x in bm_hits), default=1.0)
        for cid, b in bm_hits:
            b_norm = b / bmax if bmax else 0.0
            if cid in merged:
                merged[cid]["score"] = merged[cid].get("score", 0.0) + b_norm * settings.bm25_weight
            else:
                r = next((x for x in rows if x["id"] == cid), None)
                if r:
                    hit = dict(r)
                    hit.pop("vector", None)
                    hit["tags"] = _parse_tags(hit.get("tags"))
                    merged[cid] = {**hit, "vec_score": 0.0, "score": b_norm * settings.bm25_weight}

        # 4) 多标签 OR 过滤（D12）
        if tags:
            want = set(tags)
            merged = {cid: h for cid, h in merged.items() if set(h.get("tags", [])) & want}

        result = sorted(merged.values(), key=lambda h: h["score"], reverse=True)[:top_k]
        for h in result:
            h["score"] = round(h["score"], 4)
        return result

    def _bm25_rank(self, query: str, rows, top_k: int) -> List[tuple[int, float]]:
        """用 rank-bm25 对全库文本打分，返回 [(chunk_id, score)]。"""
        if not query.strip():
            return []
        if self._bm25 is None:
            from rank_bm25 import BM25Okapi

            corpus = [_cjk_tokenize(r["text"]) for r in rows]
            if not corpus or not any(corpus):
                return []
            self._bm25 = BM25Okapi(corpus)
        scores = self._bm25.get_scores(_cjk_tokenize(query))
        ranked = sorted(enumerate(rows), key=lambda x: scores[x[0]], reverse=True)[:top_k]
        return [(rows[i]["id"], scores[i]) for i, _ in ranked if scores[i] > 0]

    # ---------- 统计 ----------
    def stats(self) -> dict:
        docs = self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunks = self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        codes = self._conn.execute("SELECT COUNT(*) FROM codes").fetchone()[0]
        return {"exists": chunks > 0 or docs > 0, "documents": docs, "chunks": chunks,
                "codes": codes, "db": self._db_path}

    def close(self) -> None:
        self._conn.close()


def _parse_tags(raw) -> List[str]:
    try:
        v = json.loads(raw or "[]")
        return list(v) if isinstance(v, list) else []
    except (TypeError, ValueError):
        return []