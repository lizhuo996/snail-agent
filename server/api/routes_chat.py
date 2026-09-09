# -*- coding: utf-8 -*-
"""RAG 问答接口：检索知识库 → 拼 prompt → SSE 流式回答（要求附来源）。"""
import json
import logging
from typing import Generator, List, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from server.core.llm import chat_stream, embed_texts
from server.rag import kb as kb_mod

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

SYSTEM_PROMPT = (
    "你是「最强蜗牛」攻略助手。只依据提供的【攻略依据】回答用户问题，"
    "回答要准确、口语化、面向玩家。回答中如引用具体来源，用【来源：文件名】标注。"
    "如果依据不足以回答，直接说明“知识库中没有查到相关信息”，不要编造。"
)

_kb: kb_mod.KB | None = None


def get_kb() -> kb_mod.KB:
    global _kb
    if _kb is None:
        _kb = kb_mod.KB()
    return _kb


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    tags: Optional[List[str]] = Field(default=None, description="多标签过滤（D12，任一命中即可）")


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/kb/stats")
def kb_stats():
    """知识库状态（前端页头/管理后台展示用）。"""
    return get_kb().stats()


@router.get("/codes")
def codes(keyword: str = ""):
    """密令精确查询（query_codes）。"""
    return {"codes": get_kb().search_codes(keyword)}


@router.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _stream(req.question, req.top_k, req.tags),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _stream(question: str, top_k: int, tags: Optional[List[str]]) -> Generator[str, None, None]:
    try:
        # 1. 密令提问优先走结构化（D13）：精确命中直接答；泛指“有什么密令”则列表全部
        hits = get_kb().search_codes(question)
        if not hits and any(w in question for w in ("密令", "兑换码", "口令")):
            hits = get_kb().search_codes()  # 全部生效中
        if hits:
            lines = []
            for c in hits:
                reward = c["reward"].strip() or "奖励待补充"
                lines.append(f"密令【{c['text']}】：{reward}（{c['status']}）")
            yield _sse("sources", [{"source": f"密令库 共{len(hits)}条生效", "clause": "query_codes", "score": 1.0}])
            yield _sse("delta", {"content": "查到以下生效中的密令：\n\n" + "\n".join(lines)})
            yield _sse("done", {})
            return

        # 2. 常规 RAG：向量化 → 混检 → 拼上下文 → 流式生成
        q_vec = embed_texts([question])[0]
        hits = get_kb().search(q_vec, top_k=top_k, tags=tags, query=question)
        context = "\n\n".join(
            f"【{h['title'] or h['section'] or '未知'}·第{h['page'] or '?'}部分·相关度{h['score']}】\n{h['text']}"
            for h in hits
        )
        # 先把引用来源推给前端展示
        yield _sse(
            "sources",
            [{"source": h.get("title", ""), "clause": h.get("section", ""), "page": h.get("page"),
              "score": h.get("score", 0.0)} for h in hits],
        )

        messages: List[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"【攻略依据】\n{context or '（知识库为空）'}\n\n【问题】\n{question}"},
        ]
        for delta in chat_stream(messages):
            yield _sse("delta", {"content": delta})
        yield _sse("done", {})
    except RuntimeError as e:
        log.warning("问答失败: %s", e)
        yield _sse("error", {"message": str(e)})
    except Exception as e:
        log.exception("问答异常")
        yield _sse("error", {"message": f"服务异常: {e}"})