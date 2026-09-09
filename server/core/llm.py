# -*- coding: utf-8 -*-
"""DashScope(OpenAI 兼容)客户端：向量化 + 流式对话 + 多模态看图。

密钥缺失时给出明确中文报错。视觉接口 P2 接入，此处预留 vision_client。
"""
import logging
from typing import Generator, List

from openai import OpenAI

from server.core.config import settings

log = logging.getLogger(__name__)

_client: OpenAI | None = None

# text-embedding-v3 单次请求最多 10 条输入，超了要分批
EMBED_BATCH_SIZE = 10


def get_openai_client() -> OpenAI:
    """懒加载单例。没配 Key 直接抛错，提示去 .env 配置。"""
    global _client
    if _client is None:
        if not settings.dashscope_api_key:
            raise RuntimeError(
                "DashScope API Key 未配置：请复制 .env.example 为 .env 并填入 DASHSCOPE_API_KEY"
            )
        _client = OpenAI(api_key=settings.dashscope_api_key, base_url=settings.llm_base_url)
    return _client


def embed_texts(texts: List[str]) -> List[List[float]]:
    """批量向量化，自动按 EMBED_BATCH_SIZE 分批。"""
    client = get_openai_client()
    vectors: List[List[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        resp = client.embeddings.create(
            model=settings.embedding_model, input=batch, dimensions=settings.embed_dim
        )
        # 按 index 排序保证与输入顺序一致
        ordered = sorted(resp.data, key=lambda d: d.index)
        vectors.extend([d.embedding for d in ordered])
        log.info("向量化进度: %d/%d", min(i + EMBED_BATCH_SIZE, len(texts)), len(texts))
    return vectors


def chat_stream(messages: List[dict]) -> Generator[str, None, None]:
    """流式对话，逐段 yield 文本增量。"""
    client = get_openai_client()
    stream = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        stream=True,
        temperature=0.3,  # 攻略咨询场景要稳，温度调低
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content