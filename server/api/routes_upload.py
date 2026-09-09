# -*- coding: utf-8 -*-
"""对话侧解析（P2 场景A）：上传图片/文档 → 解析为 ParsedContent。

聊天接口 /api/chat 增加 attachments 字段：先解析附件文本并入上下文（SSE 增 parsed 事件）。
独立 /api/parse 接口给管理后台/聊天页复用（文件、URL）。
"""
import io
import logging
import urllib.parse
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from server.core.models import ParsedContent
from server.rag import parser
from server.rag.parser import parse_path, parse_url

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# 允许上传扩展（与建库一致 + 图片）
ALLOWED_EXT = {e for e in parser.SUPPORTED}


class ParseURLReq(BaseModel):
    url: str


class ParseResult(BaseModel):
    text: str
    source_type: str
    title: str = ""
    meta: dict = {}


def _save_tmp(upload: UploadFile) -> tuple[Path, str]:
    """把上传文件写到临时目录，返回 (tmp路径, 原始文件名)。"""
    import tempfile

    name = Path(upload.filename or "upload.bin")
    ext = name.suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"不支持的格式：{ext or '(无扩展名)'}")
    data = upload.file.read()
    if not data:
        raise HTTPException(400, "空文件")
    tmpdir = Path(tempfile.gettempdir()) / "snail_uploads"
    tmpdir.mkdir(parents=True, exist_ok=True)
    tmp = tmpdir / f"u_{upload.filename.replace('/', '_')}"
    tmp.write_bytes(data)
    return tmp, name.name


@router.post("/parse")
async def parse_upload(file: UploadFile = File(...)):
    """上传文件解析成文本（图片自动走多模态/OCR双通道）。"""
    tmp, fname = _save_tmp(file)
    try:
        content = parse_path(tmp)
    finally:
        tmp.unlink(missing_ok=True)
    content.title = content.title or fname
    return ParseResult(
        text=content.text, source_type=content.source_type,
        title=content.title, meta=content.meta).model_dump()


@router.post("/parse-url")
def parse_url_endpoint(req: ParseURLReq):
    """粘贴网页链接 → 提取正文。"""
    try:
        content = parse_url(req.url)
    except Exception as e:
        raise HTTPException(400, f"网页解析失败：{e}")
    return ParseResult(
        text=content.text, source_type=content.source_type,
        title=content.title, meta=content.meta).model_dump()


def parse_attachments(files: List[UploadFile]) -> tuple[List[ParsedContent], List[str]]:
    """解析多个附件（对话/建库共用），返回 (contents, source_labels)。"""
    contents: List[ParsedContent] = []
    for f in files:
        tmp, fname = _save_tmp(f)
        try:
            content = parse_path(tmp)
            content.title = content.title or fname
            contents.append(content)
        except Exception as e:
            log.warning("附件解析失败 %s: %s", fname, e)
            raise HTTPException(400, f"附件「{fname}」解析失败：{e}")
        finally:
            tmp.unlink(missing_ok=True)
    return contents, [c.title or f"{i}" for i, c in enumerate(contents)]