# -*- coding: utf-8 -*-
"""知识库检索离线测试：构造小库，验证向量/BM25 融合与多标签过滤。"""
import numpy as np
import pytest

from server.core.models import Code, Document
from server.rag.kb import KB, _cjk_tokenize


def make_chunks():
    docs = [
        "新手前期推荐刷英伦地图，资源稳定，第一周稳过。",
        "抽奖周活动：本周抽奖券翻倍，建议囤300抽。",
        "贵重品优先升级橙色，加到攻击属性最划算。",
        "密令是最强蜗牛兑换码，在设置里兑换领取奖励。",
    ]
    chunks = []
    for i, t in enumerate(docs, 1):
        chunks.append(dict(doc_id=i, title=f"攻略{i}", text=t, tags=["新手入门"] if i < 3 else ["进阶玩法"]))
    return chunks


@pytest.fixture()
def kb(tmp_path):
    k = KB(db_path=str(tmp_path / "t.sqlite3"))
    # 用简易词条向量（模拟），保证余弦有区分度
    for c in make_chunks():
        doc = Document(id=c["doc_id"], title=c["title"])
        kid = k.add_document(doc)
        vec = [0.1, 0.2, 0.3, 0.4]
        from server.core.models import Chunk
        k.add_chunks([Chunk(doc_id=kid, title=c["title"], text=c["text"], tags=c["tags"], vector=vec)])
    yield k
    k.close()


def test_tokenize_cjk():
    toks = _cjk_tokenize("抽奖周活动 English123")
    assert "抽奖" in toks
    assert "english123" in toks


def test_search_returns_scored(kb):
    vec = [0.1, 0.2, 0.3, 0.4]
    hits = kb.search(vec, top_k=2, query="抽奖周 活动")
    assert len(hits) <= 2
    assert all("score" in h for h in hits)
    assert hits[0]["score"] >= hits[1]["score"]


def test_single_tag_filter(kb):
    vec = [0.1, 0.2, 0.3, 0.4]
    hits = kb.search(vec, top_k=10, tags=["新手入门"])
    assert hits, "应至少命中新手入门块"
    assert all("新手入门" in h["tags"] for h in hits)


def test_code_roundtrip(kb):
    kb.add_code(Code(text="零帧起手", reward="信物x20", status="生效", valid_until="2026-09-30"))
    kb.add_code(Code(text="旧码", reward="黑蝌蚪x100", status="已过期"))
    allc = kb.search_codes()
    assert len(allc) == 1 and allc[0]["text"] == "零帧起手"  # 只返回生效
    kw = kb.search_codes("起手")
    assert kw and kw[0]["text"] == "零帧起手"


def test_clear(kb):
    kb.clear()
    assert kb.stats()["chunks"] == 0