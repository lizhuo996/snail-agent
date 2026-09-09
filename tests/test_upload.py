# -*- coding: utf-8 -*-
"""P2 对话侧解析 / 上传流程离线测试（不依赖 Key、网络）。"""
import pytest
from fastapi.testclient import TestClient

from server.core.models import Document
from server.rag.kb import KB

from tests.test_admin import make_app


def test_parse_upload_txt(tmp_path):
    app, kb = make_app(tmp_path)
    c = TestClient(app)
    r = c.post("/api/parse", files={"file": ("攻略.txt", "最强蜗牛新手刷英伦图", "text/plain")})
    assert r.status_code == 200
    body = r.json()
    assert "英伦图" in body["text"]
    assert body["source_type"] == "txt"


def test_parse_upload_bad_ext_rejected(tmp_path):
    app, kb = make_app(tmp_path)
    c = TestClient(app)
    r = c.post("/api/parse", files={"file": ("a.zip", b"PK", "application/zip")})
    assert r.status_code == 400


def test_chat_upload_pasted_text_streams_parsed(tmp_path, monkeypatch):
    """用 /api/chat-upload 传粘贴文本：应出现 parsed 事件与正常回答流。"""
    app, kb = make_app(tmp_path)
    # 库内放一条，让检索能出 sources
    k = kb
    did = k.add_document(Document(title="测试", source_type="txt"))
    from server.core.models import Chunk

    k.add_chunks([Chunk(doc_id=did, title="测试", text="英伦地图资源稳定", tags=[])])

    # 离线替身
    def fake_embed(texts):
        return [[0.0] * 16 for _ in texts]

    def fake_chat_stream(messages):
        texts = messages[1]["content"]
        if "粘贴文本" in texts and "我的补充材料" in texts:
            yield "已结合你的材料回答。"
        else:
            yield "回答。"

    import server.api.routes_chat as rc

    monkeypatch.setattr(rc, "embed_texts", fake_embed)
    monkeypatch.setattr(rc, "chat_stream", fake_chat_stream)

    c = TestClient(app)
    with c.stream("POST", "/api/chat-upload", data={
        "question": "这个材料怎么用",
        "text": "我的补充材料：蜗牛冲装备用白蝌蚪。",
    }) as resp:
        assert resp.status_code == 200
        buf = ""
        events = []
        for chunk in resp.iter_text():
            buf += chunk
            while "\n\n" in buf:
                head, _, buf = buf.partition("\n\n")
                events.append(head)
    joined = "\n".join(events)
    assert "parsed" in joined          # SSE 回显解析结果
    assert "已结合你的材料回答" in joined  # 附件文本真正并入了上下文
    assert "sources" in joined


def test_image_parse_uses_vision_channel(tmp_path, monkeypatch):
    """图片解析走 vision 通道（mock），并记录通道名。"""
    from server.core import vision
    from server.rag import parser as P

    calls = {}

    def fake_read_image(path, channel="auto"):
        calls["channel"] = channel
        return "图中文字：密码 XXXX", "qwen-vl"

    monkeypatch.setattr(vision, "read_image", fake_read_image)

    img = tmp_path / "shot.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    c = P.parse_path(img)
    assert "图中文字" in c.text
    assert c.source_type == "image"
    assert c.meta.get("image_channel") == "qwen-vl"


def test_vision_reader_channel_selection():
    """vision.get_reader 按通道分发；OCR 未安装时给出明确错误而非崩溃。"""
    from server.core import vision

    assert vision._mime_of(".png") == "image/png"
    assert vision.VLImageReader.name == "qwen-vl"
    try:
        import paddleocr  # noqa: F401
        has_paddle = True
    except ImportError:
        has_paddle = False
    if not has_paddle:
        with pytest.raises(RuntimeError, match="PaddleOCR"):
            vision.get_reader("ocr")