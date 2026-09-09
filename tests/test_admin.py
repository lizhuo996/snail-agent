# -*- coding: utf-8 -*-
"""P3 管理后台 API 离线测试（SQLite 用 tmp_path 隔离，不依赖 Key）。"""
import json

import pytest
from fastapi.testclient import TestClient

from server.core.models import Code, Document
from server.rag.kb import KB


@pytest.fixture()
def kb(tmp_path):
    k = KB(db_path=str(tmp_path / "admin.sqlite3"))
    doc = Document(title="新手攻略", source_type="txt", created_at="2026-09-09")
    k.add_document(doc)
    yield k
    k.close()


# ---------- KB 管理方法 ----------
def test_list_documents(kb):
    docs = kb.list_documents()
    assert docs and docs[0]["title"] == "新手攻略"
    assert "chunk_count" in docs[0]


def test_delete_document(kb):
    did = kb.list_documents()[0]["id"]
    assert kb.delete_document(did) is True
    assert kb.delete_document(9999) is False
    assert kb.list_documents() == []


def test_chunk_tags_roundtrip(kb):
    kb.add_chunks([])  # 空，直接构造
    from server.core.models import Chunk

    c = Chunk(doc_id=1, title="x", text="你好世界", tags=["新手入门"])
    kb.add_chunks([c])
    # 拿回 id
    rows = kb.list_chunks()
    cid = rows[0]["id"]
    assert kb.set_chunk_tags(cid, ["周活动", "进阶玩法"]) is True
    assert kb.list_chunks()[0]["tags"] == ["周活动", "进阶玩法"]
    tags = kb.all_tags()
    assert {"tag": "周活动", "count": 1} in tags


def test_codes_admin_ops(kb):
    kb.add_code(Code(text="AA", reward="x1", status="生效"))
    kb.add_code(Code(text="BB", reward="x2", status="停用"))
    kb.add_code(Code(text="CC", reward="x3", status="已过期"))
    codes = kb.list_codes_all()
    assert len(codes) == 3
    only_ok = kb.list_codes_all(status="生效")
    assert len(only_ok) == 1

    aid = next(x["id"] for x in codes if x["text"] == "AA")
    assert kb.update_code(aid, reward="x10", status="停用") is True
    stopped = {c["text"]: c for c in kb.list_codes_all(status="停用")}
    assert stopped["AA"]["reward"] == "x10"
    assert "BB" in stopped
    assert kb.delete_code(aid) is True
    assert kb.delete_code(9999) is False


# ---------- 路由 ----------
def make_app(tmp_path):
    import server.rag.kb as kb_mod
    from server.core import config as cfg
    import server.api.routes_admin as rh

    cfg.settings.kb_db_path = str(tmp_path / "r.sqlite3")
    kb_mod._kb = None
    rh._kb = None
    from server.api.main import app

    return app, KB(db_path=str(tmp_path / "r.sqlite3"))


def test_admin_routes_flow(tmp_path, monkeypatch):
    from server.core.config import settings as cfg_settings

    app, kb = make_app(tmp_path)
    monkeypatch.setattr(cfg_settings, "dashscope_api_key", "")  # 模拟未配 Key（离线可测）
    # 预置数据
    did = kb.add_document(Document(title="测试", source_type="txt"))
    from server.core.models import Chunk

    kb.add_chunks([Chunk(doc_id=did, title="测试", text="英伦地图资源稳定", tags=["探索地图"])])
    kb.add_code(Code(text="码A", reward="金币", status="生效"))

    c = TestClient(app)
    assert c.get("/api/admin/kb/stats").json()["documents"] == 1

    docs = c.get("/api/admin/kb/docs").json()["documents"]
    assert docs[0]["title"] == "测试"
    did = docs[0]["id"]

    # 标签
    chunks = c.get("/api/admin/kb/chunks?doc_id=" + str(did)).json()["chunks"]
    cid = chunks[0]["id"]
    r = c.put(f"/api/admin/kb/chunks/{cid}/tags", json={"tags": ["周活动"]})
    assert r.json()["ok"] is True
    assert c.get("/api/admin/kb/tags").json()["tags"] == [{"tag": "周活动", "count": 1}]

    # 密令 CRUD
    assert c.post("/api/admin/codes", json={"text": "码B", "reward": "钻"}).json()["ok"]
    codes = c.get("/api/admin/codes").json()["codes"]
    assert len(codes) == 2
    bid = next(x["id"] for x in codes if x["text"] == "码B")
    assert c.put(f"/api/admin/codes/{bid}", json={"text": "码B", "status": "停用"}).json()["ok"]
    allc = {x["text"]: x for x in c.get("/api/admin/codes").json()["codes"]}
    assert allc["码B"]["status"] == "停用"
    assert allc["码A"]["status"] == "生效"

    # 批量导入（一行一条）
    r = c.post("/api/admin/codes/batch", json={"lines": "新码1|奖励A|生效|2026-12-31\n新码2|奖励B"})
    assert r.json()["added"] == 2
    # 重复导入跳过
    r = c.post("/api/admin/codes/batch", json={"lines": "新码1|奖励A"})
    assert r.json()["added"] == 0 and r.json()["skipped"] == 1

    # 检索测试：无 Key → bm25-only 渠道，可返回命中
    r = c.post("/api/admin/kb/search-test", json={"query": "英伦地图", "top_k": 3})
    body = r.json()
    assert body["provider"] == "bm25-only(未配Key)"
    assert body["hits"]  # 至少命中 英伦地图 分块

    # 删除
    assert c.delete(f"/api/admin/kb/docs/{did}").json()["ok"] is True
    assert c.get("/api/admin/kb/stats").json()["chunks"] == 0

    # 运维/模型接口
    h = c.get("/api/admin/health").json()
    assert h["service"] == "up"
    mc = c.get("/api/admin/llm/config").json()
    assert "llm_model" in mc and "api_key_configured" in mc


def test_admin_code_dup_rejected(tmp_path):
    app, kb = make_app(tmp_path)
    kb.add_code(Code(text="重复", reward="", status="生效"))
    c = TestClient(app)
    # text 唯一约束，重复新增应被 400 拦截
    r = c.post("/api/admin/codes", json={"text": "重复", "reward": "x"})
    assert r.status_code == 400
    assert len(c.get("/api/admin/codes").json()["codes"]) == 1