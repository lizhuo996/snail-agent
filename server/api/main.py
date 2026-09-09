# -*- coding: utf-8 -*-
"""FastAPI 入口：健康检查、RAG 问答、静态聊天页。"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from server.api import routes_admin, routes_chat, routes_upload
from server.core.config import settings, BASE_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="最强蜗牛攻略智能体 Demo", version="0.1.0")

# demo 阶段允许所有来源跨域；上线后收紧
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_chat.router)
app.include_router(routes_upload.router)
app.include_router(routes_admin.router)


@app.get("/api/health")
def health():
    """部署后第一件事：确认依赖连通。llm 只查密钥是否配置，不发真实请求。"""
    from server.rag.kb import KB

    try:
        kb = KB()
        kbstats = kb.stats()
        kb.close()
    except Exception as e:  # 兜底：DB 异常不影响 health 主流程
        kbstats = {"error": str(e)[:200]}

    return {
        "service": "up",
        "version": "0.1.0",
        "kb": kbstats,
        "llm": {
            "base_url": settings.llm_base_url,
            "model": settings.llm_model,
            "api_key_configured": bool(settings.dashscope_api_key),
        },
    }


# 静态聊天页放最后挂载，避免吞掉 /api/* 路由
_web_dir = BASE_DIR / "web"
if _web_dir.exists():
    app.mount("/", StaticFiles(directory=str(_web_dir), html=True), name="web")


# no-cache：聊天页 JS 迭代快，杜绝浏览器缓存旧版导致 SSE 解析异常
class _NoCachePages(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        if request.url.path in ("/", "/index.html", "/admin", "/admin/index.html"):
            resp.headers["Cache-Control"] = "no-store"
            resp.headers["Pragma"] = "no-cache"
        return resp


app.add_middleware(_NoCachePages)