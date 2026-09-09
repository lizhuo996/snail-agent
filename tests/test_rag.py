# -*- coding: utf-8 -*-
"""切块与解析离线测试（不依赖 Key / 网络）。"""
import pytest

from server.core.models import Document
from server.rag.chunker import chunk_document, split_text
from server.rag.parser import parse_path, SUPPORTED


class TestSplitText:
    def test_empty(self):
        assert split_text("  \n ") == []

    def test_normal_splits_at_sentence_boundary(self):
        # 50 段一句话，应切出多个 ≈500 字的块，且不在句中截断
        long = "".join(f"这是第{i+1}个句话。最强蜗牛的玩法套路讲解内容填充一些字数。"
                       for i in range(50))
        chunks = split_text(long)
        assert len(chunks) > 1
        assert all(c.endswith(("。", "！", "？", "；", "\n")) for c in chunks)

    def test_hard_limit_no_runaway(self):
        huge = "啊" * 9000  # 无标点长串 → 硬切
        chunks = split_text(huge)
        assert chunks
        assert max(map(len, chunks)) <= 800

    def test_overlap_keeps_context(self):
        long = "".join(f"第{i}段句子，记录游戏攻略知识内容。蜗牛吃蘑菇长大变强哦。" for i in range(30))
        chunks = split_text(long)
        if len(chunks) > 1:
            # 相邻两块的接缝处应保留公共字（重叠）
            overlap1, overlap2 = chunks[0], chunks[1]
            assert overlap1[-10:] in overlap2 or overlap2[:10] in overlap1


class TestChunkDocument:
    def test_tags_passed_through(self):
        doc = Document(id=1, title="新手攻略")
        chunks = chunk_document(doc, "第一句。第二句。第三句。", tags=["新手入门", "探索地图"])
        assert all(c.tags == ["新手入门", "探索地图"] for c in chunks)
        assert all(c.doc_id == 1 for c in chunks)


class TestParser:
    def test_supported_exts_include_core_formats(self):
        assert {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".html"} <= SUPPORTED

    def test_parse_txt(self, tmp_path):
        f = tmp_path / "demo.txt"
        f.write_text("最强蜗牛新手引导\n前期刷英伦图", encoding="utf-8")
        c = parse_path(f)
        assert "最强蜗牛" in c.text
        assert c.source_type == "txt"
        assert c.title == "demo"

    def test_parse_md(self, tmp_path):
        f = tmp_path / "guide.md"
        f.write_text("# 周活动\n抽奖周攻略\n", encoding="utf-8")
        c = parse_path(f)
        assert "抽奖周" in c.text

    def test_parse_html(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text("<html><head><title>游戏攻略</title></head>"
                     "<body><h1>标题</h1><p>正文内容</p><script>var x=1;</script></body></html>", encoding="utf-8")
        c = parse_path(f)
        assert "正文内容" in c.text
        assert "var x=1" not in c.text  # script 被剔除
        assert c.title == "游戏攻略"

    def test_unsupported_ext(self, tmp_path):
        f = tmp_path / "a.zip"
        f.write_bytes(b"PK")
        with pytest.raises(ValueError):
            parse_path(f)