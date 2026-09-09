# -*- coding: utf-8 -*-
"""建库脚本：扫描 knowledge/raw/ 下的攻略 → 解析 → 切块 → 向量化 → 写入 SQLite。

用法：
    D:\\SoftWare\\Python312\\python.exe scripts\\build_kb.py            # 全量重建
    D:\\SoftWare\\Python312\\python.exe scripts\\build_kb.py --keep     # 不清库，仅追加
    D:\\SoftWare\\Python312\\python.exe scripts\\build_kb.py --tags 新手入门,探索地图   # 全局标签（D12）
"""
import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# 把仓库根（scripts/ 的上一级）加入 sys.path，保证 `import server.*` 可用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.core.config import BASE_DIR  # noqa: E402
from server.core.models import Chunk, Document
from server.rag.chunker import chunk_document
from server.rag.kb import KB
from server.rag.parser import parse_path

log = logging.getLogger("build_kb")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

RAW_DIR = BASE_DIR / "knowledge" / "raw"
SUPPORTED_IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}


def scan_files() -> list[Path]:
    """递归收集 RAW_DIR 下待建库文件（图片 P2 再入库，先跳过）。"""
    if not RAW_DIR.exists():
        log.warning("目录不存在: %s", RAW_DIR)
        return []
    files = sorted(
        p for p in RAW_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() not in SUPPORTED_IMAGES and p.suffix
    )
    return files


def main() -> None:
    ap = argparse.ArgumentParser(description="构建最强蜗牛攻略知识库")
    ap.add_argument("--keep", action="store_true", help="不清库，仅追加")
    ap.add_argument("--tags", default="", help="全局标签，逗号分隔（如：新手入门,探索地图）")
    ap.add_argument("--skip-embed", action="store_true", help="跳过向量化（离线开发调试用）")
    args = ap.parse_args()

    files = scan_files()
    if not files:
        log.warning("knowledge/raw 为空，请在 %s 放入攻略文件", RAW_DIR)
        return

    from server.core.llm import embed_texts  # 延迟导入，Key 缺失时只在真的要向量化时报错

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    kb = KB()
    if not args.keep:
        kb.clear()
        log.info("已清空旧知识库")

    t0 = time.time()
    total_chunks = 0
    ok_files = 0
    for i, path in enumerate(files, 1):
        try:
            content = parse_path(path)
        except Exception as e:
            log.error("解析失败 %s: %s", path, e)
            continue
        if not content.text.strip():
            log.warning("无正文，跳过: %s", path)
            continue

        doc_id = kb.add_document(Document(
            title=content.title or path.stem,
            source_type=content.source_type,
            raw_path=str(path),
            created_at=datetime.now().isoformat(timespec="seconds"),
        ))
        chunks = chunk_document(Document(id=doc_id, title=content.title or path.stem), content.text, tags=tags)
        if not chunks:
            continue
        if args.skip_embed:
            kb.add_chunks(chunks)
        else:
            vectors = embed_texts([c.text for c in chunks])
            for c, vec in zip(chunks, vectors):
                c.vector = vec
            kb.add_chunks(chunks)
        total_chunks += len(chunks)
        ok_files += 1
        log.info("[%d/%d] %s → %d 块", i, len(files), path.name, len(chunks))

    kb.rebuild_fts()
    log.info("完成：%d 份文档 / %d 个块，耗时 %.1fs", ok_files, total_chunks, time.time() - t0)
    log.info("知识库: %s", kb.stats())
    kb.close()


if __name__ == "__main__":
    main()