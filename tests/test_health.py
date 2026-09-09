# -*- coding: utf-8 -*-
"""离线冒烟：/api/health 不依赖外部 API Key。"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    # 隔离 DB，避免污染真实知识库
    from server.core import config
    import server.rag.kb as kb_mod

    tmp_db = tmp_path_factory.mktemp("kb") / "test.sqlite3"
    config.settings.kb_db_path = str(tmp_db)
    kb_mod._kb = None  # 强制重建单例
    from server.api import routes_chat

    routes_chat._kb = None

    from server.api.main import app

    return TestClient(app)


def test_health_up(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "up"
    assert "kb" in body
    assert "llm" in body
    assert "api_key_configured" in body["llm"]


def test_kb_stats_empty(client):
    r = client.get("/api/kb/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["documents"] == 0
    assert body["chunks"] == 0


def test_codes_empty(client):
    r = client.get("/api/codes")
    assert r.status_code == 200
    assert r.json() == {"codes": []}


def test_secrets_key_file_priority(tmp_path, monkeypatch):
    """单独 key 文件优先级高于 .env（本机无 .env/占位 key 时应读到占位值）。"""
    from server.core import config as cfg

    key_file = tmp_path / "dashscope.key"
    key_file.write_text("sk-from-secrets-file", encoding="utf-8")
    monkeypatch.setattr(cfg, "SECRETS_KEY_FILE", key_file)

    # 重新实例化 Settings，验证 file 覆盖 .env（此处 .env 不存在 → 空，应取 file）
    s = cfg.Settings(dashscope_api_key="")
    assert s.dashscope_api_key == "sk-from-secrets-file"