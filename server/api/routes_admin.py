# -*- coding: utf-8 -*-
"""管理后台 API（P3）：知识库管理 / 密令管理 / 系统运维 / 模型查看测试。

前缀 /api/admin/*（AGENTS.md 约定）。离线可测：数据操作用临时 KB 隔离，LLM 调用可 mock。
"""
import json
import logging
import subprocess
import sys
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from server.core.config import BASE_DIR, settings
from server.core.models import Code
from server.rag import kb as kb_mod

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin")

_kb: kb_mod.KB | None = None


def get_kb() -> kb_mod.KB:
    global _kb
    if _kb is None:
        _kb = kb_mod.KB()
    return _kb


# ---------- 请求体 ----------
class TagReq(BaseModel):
    tags: List[str] = []


class CodeItem(BaseModel):
    text: str
    reward: str = ""
    status: str = "生效"
    valid_until: str = ""
    batch: str = ""
    remark: str = ""


class CodeBatchReq(BaseModel):
    lines: str = ""  # 每行一条：密令[|奖励][|状态][|有效期]


class SearchTestReq(BaseModel):
    query: str = ""
    tags: Optional[List[str]] = None
    top_k: int = 5


class LLMTestReq(BaseModel):
    prompt: str = "用一句话介绍最强蜗牛"


# ---------- 知识库 ----------
@router.get("/kb/stats")
def kb_stats():
    return get_kb().stats()


@router.get("/kb/docs")
def kb_docs():
    return {"documents": get_kb().list_documents()}


@router.delete("/kb/docs/{doc_id}")
def kb_doc_delete(doc_id: int):
    if not get_kb().delete_document(doc_id):
        raise HTTPException(404, "文档不存在")
    return {"ok": True}


@router.get("/kb/chunks")
def kb_chunks(doc_id: Optional[int] = None):
    return {"chunks": get_kb().list_chunks(doc_id=doc_id)}


@router.put("/kb/chunks/{chunk_id}/tags")
def chunk_tags_update(chunk_id: int, req: TagReq):
    if not get_kb().set_chunk_tags(chunk_id, req.tags):
        raise HTTPException(404, "条目不存在")
    return {"ok": True, "tags": req.tags}


@router.get("/kb/tags")
def kb_tags():
    return {"tags": get_kb().all_tags()}


@router.post("/kb/rebuild")
def kb_rebuild():
    """触发全量重建（跑 scripts/build_kb.py，同步执行并返回末尾日志）。"""
    py = sys.executable
    proc = subprocess.run(
        [py, str(BASE_DIR / "scripts" / "build_kb.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600,
    )
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-20:]
    if proc.returncode != 0:
        raise HTTPException(500, "重建失败：" + "\n".join(tail))
    return {"ok": True, "log": tail}


@router.post("/kb/search-test")
def kb_search_test(req: SearchTestReq):
    """检索测试：真 embedding（需要 Key）；Key 缺失时退化为关键词检索。"""
    from server.core.llm import embed_texts

    if not settings.dashscope_api_key:
        # 无 Key：仅 BM25，向量部分置零向量（score 只反映关键词）
        vec = [0.0] * settings.embed_dim
        hits = get_kb().search(vec, top_k=req.top_k, tags=req.tags, query=req.query)
        return {"provider": "bm25-only(未配Key)", "hits": hits}
    vec = embed_texts([req.query])[0]
    hits = get_kb().search(vec, top_k=req.top_k, tags=req.tags, query=req.query)
    return {"provider": "vector+bm25", "hits": hits}


# ---------- 密令 ----------
@router.get("/codes")
def codes_list(status: str = ""):
    return {"codes": get_kb().list_codes_all(status=status)}


@router.post("/codes")
def codes_create(item: CodeItem):
    kb = get_kb()
    # 密令文本唯一：已存在则 400 拒绝（避免 INSERT OR REPLACE 静默覆盖）
    if any(c["text"] == item.text for c in kb.list_codes_all()):
        raise HTTPException(400, f"密令「{item.text}」已存在")
    try:
        kb.add_code(Code(**item.model_dump()))
    except Exception as e:
        raise HTTPException(400, f"新增失败：{e}")
    return {"ok": True}


@router.put("/codes/{code_id}")
def codes_update(code_id: int, item: CodeItem):
    if not get_kb().update_code(
            code_id, item.reward, item.status, item.valid_until, item.batch, item.remark):
        raise HTTPException(404, "密令不存在")
    return {"ok": True}


@router.delete("/codes/{code_id}")
def codes_delete(code_id: int):
    if not get_kb().delete_code(code_id):
        raise HTTPException(404, "密令不存在")
    return {"ok": True}


@router.post("/codes/batch")
def codes_batch(req: CodeBatchReq):
    """批量导入：每行一条，可带 | 分隔（密令|奖励|状态|有效期）。"""
    kb = get_kb()
    added, skipped, errors = 0, 0, []
    for line in req.lines.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        text = parts[0]
        if not text:
            continue
        if kb.search_codes(text) or any(c["text"] == text for c in kb.list_codes_all()):
            skipped += 1
            continue
        try:
            kb.add_code(Code(
                text=text,
                reward=parts[1] if len(parts) > 1 else "",
                status=parts[2] if len(parts) > 2 else "生效",
                valid_until=parts[3] if len(parts) > 3 else "",
                remark="管理后台批量导入",
            ))
            added += 1
        except Exception as e:
            errors.append(f"{text}: {e}")
    return {"ok": True, "added": added, "skipped": skipped, "errors": errors}


# ---------- 系统运维 / 模型 ----------
@router.get("/health")
def admin_health():
    from server.api.main import health

    return health()


@router.get("/llm/config")
def llm_config():
    return {
        "llm_base_url": settings.llm_base_url,
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "vision_model": settings.vision_model,
        "api_key_configured": bool(settings.dashscope_api_key),
        "embed_dim": settings.embed_dim,
        "bm25_weight": settings.bm25_weight,
    }


@router.post("/llm/test")
def llm_test(req: LLMTestReq):
    from server.core.llm import chat_stream

    try:
        text = "".join(chat_stream([{"role": "user", "content": req.prompt}]))
        return {"ok": True, "reply": text}
    except Exception as e:
        return {"ok": False, "reply": "", "error": str(e)}