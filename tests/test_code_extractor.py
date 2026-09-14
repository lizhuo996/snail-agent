# -*- coding: utf-8 -*-
"""密令自动提取 + 网页图片解析 离线测试（纯规则/ mock，无网络、无 Key）。"""
import pytest

from server.rag.code_extractor import extract_codes, extract_codes_to_kb
from server.rag.kb import KB


# ---------- 密令提取 ----------
def test_extract_chinese_code_with_reward():
    codes = extract_codes("本周密令：烈焰红唇，奖励：1000黑蝌蚪")
    assert codes and codes[0]["text"] == "烈焰红唇"
    assert codes[0]["reward"] == "1000黑蝌蚪"


def test_extract_ascii_code():
    codes = extract_codes("兑换码 whosyourdaddy 领取神秘礼包")
    assert codes and codes[0]["text"] == "whosyourdaddy"
    assert codes[0]["reward"]


def test_extract_multi_line_dedup():
    text = "密令：AA单独B\n密令：AA单独B\n密令：一起玩耍，奖励：金币\n"
    codes = extract_codes(text)
    texts = [c["text"] for c in codes]
    assert len(texts) == len(set(texts))  # 去重
    assert "一起玩耍" in texts


def test_reward_without_keyword_stays_empty():
    codes = extract_codes("密令：朴实无华且枯燥")
    assert codes[0]["text"] == "朴实无华且枯燥"
    assert codes[0]["reward"] == ""


def test_ignores_plain_text_no_guide_word():
    assert extract_codes("攻略正文没有密令引导词，只是普通句子") == []


def test_cut_trailing_reward_glued():
    # 码和奖励贴在一起无标点：应把“奖励1000…”切掉，只留码
    codes = extract_codes("密令：烈焰红唇奖励1000黑蝌蚪")
    assert codes[0]["text"] == "烈焰红唇"
    assert codes[0]["reward"] == "1000黑蝌蚪"


def test_noise_words_filtered():
    # “密令如下/密令入口”这类引导句不应被判为码
    codes = extract_codes("密令如下：请往游戏内输入。密令入口在活动页。")
    assert not any(c["text"] in ("如下", "入口") for c in codes)


def test_extract_codes_to_kb_dedup(tmp_path):
    kb = KB(db_path=str(tmp_path / "c.sqlite3"))
    added = extract_codes_to_kb("密令：烈焰红唇，奖励：龙珠\n密令：粉红豹爱上蜗牛，奖励：金币", kb)
    assert added == 2
    texts = {c["text"] for c in kb.list_codes_all()}
    assert texts == {"烈焰红唇", "粉红豹爱上蜗牛"}
    # 重复导入不再新增
    assert extract_codes_to_kb("密令：烈焰红唇，奖励：龙珠", kb) == 0
    assert kb.stats()["codes"] == 2


# ---------- 网页图片解析（mock 网络 + vision） ----------
def test_parse_url_extracts_image_text_and_codes(tmp_path, monkeypatch):
    import httpx

    from server.core import vision
    from server.rag import parser as P

    html = (
        '<html><head><title>攻略页</title></head><body><article>'
        '密令：烈焰红唇，奖励：1000黑蝌蚪'
        '<img src="/img/shot.png" alt="截图">'
        '</article></body></html>'
    )

    calls = {}

    class _PageResp:
        raise_for_status = lambda self: None  # noqa: E731

        @property
        def text(self):
            return html

    class _ImgResp:
        content = b"\x89PNG\r\n\x1a\n" + b"0" * 4096
        raise_for_status = lambda self: None  # noqa: E731

    def fake_get(url, **kw):
        if "shot.png" in url:
            return _ImgResp()
        return _PageResp()

    def fake_read_image(path, channel="auto"):
        calls["channel"] = channel
        return "图中密令：粉红豹爱上蜗牛，奖励：神秘礼包", "qwen-vl"

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(vision, "read_image", fake_read_image)

    c = P.parse_url("https://example.com/page")
    assert "密令：烈焰红唇" in c.text                 # 正文保留
    assert "图中密令" in c.text                        # 图片文字并入
    assert c.meta.get("images_parsed", 0) >= 1

    # 正文 + 附图文字合起来，两条密令都能被提取
    codes = extract_codes(c.text)
    texts = [x["text"] for x in codes]
    assert "烈焰红唇" in texts
    assert "粉红豹爱上蜗牛" in texts


def test_parse_url_skips_tiny_or_failed_images(tmp_path, monkeypatch):
    import httpx

    from server.core import vision
    from server.rag import parser as P

    html = ('<html><body><article>正文内容'
            '<img src="/a/tiny.png">'       # 太小的占位图
            '<img src="/b/bad.png">'        # 下载失败
            '</article></body></html>')

    class _PageResp:
        raise_for_status = lambda self: None  # noqa: E731

        @property
        def text(self):
            return html

    def fake_get(url, **kw):
        if "tiny.png" in url:
            m = type("R", (), {})()
            m.content = b"X" * 100
            m.raise_for_status = lambda: None
            return m
        if "bad.png" in url:
            raise RuntimeError("下载失败")
        return _PageResp()

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(vision, "read_image",
                        lambda path, channel="auto": ("图内容", "qwen-vl"))

    c = P.parse_url("https://example.com/b")
    assert "正文内容" in c.text
    assert "图内容" not in c.text          # 小图/失败图都跳过
    assert c.meta.get("images_parsed", 0) == 0


def test_parse_url_max_images_cap(tmp_path, monkeypatch):
    import httpx

    from server.core import vision
    from server.rag import parser as P

    imgs = "".join(f'<img src="/x/{i}.png">' for i in range(5))
    html = f"<html><body><article>正文{imgs}</article></body></html>"

    class _PageResp:
        raise_for_status = lambda self: None  # noqa: E731

        @property
        def text(self):
            return html

    def fake_get(url, **kw):
        if "/x/" in url:
            m = type("R", (), {})()
            m.content = b"\x89PNG" + b"y" * 4096
            m.raise_for_status = lambda: None
            return m
        return _PageResp()

    monkeypatch.setattr(httpx, "get", fake_get)
    n = {"v": 0}
    monkeypatch.setattr(vision, "read_image",
                        lambda path, channel="auto": (f"图{n['v']}", "qwen-vl"))

    c = P.parse_url("https://example.com/x", max_images=3)
    assert c.meta.get("images_parsed", 0) <= 3


def test_vision_guard_empty_model(tmp_path, monkeypatch):
    """vision_model 为空时应给出明确中文错误（而非空模型名调 API）。"""
    from server.core import config as cfg
    from server.core import vision

    monkeypatch.setattr(cfg.settings, "vision_model", "")
    monkeypatch.setattr(cfg.settings, "dashscope_api_key", "sk-x")
    reader = vision.VLImageReader()
    with pytest.raises(RuntimeError, match="vision_model"):
        reader.read(tmp_path / "x.png")