# -*- coding: utf-8 -*-
"""图片双通道解析（P2）：

- 多模态通道（默认）：qwen-vl，走 OpenAI 兼容接口 image_url（看懂图 + 提取语义）
- OCR 通道（可选）：PaddleOCR 离线，批量文字提取、不依赖网络

通道策略：对话单张/少量 → 多模态（含语义）；批量建库 → OCR 优先（省钱稳定）。
对外统一 ImageReader 接口（可替换/新增通道）。
"""
import base64
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from server.core.config import settings

log = logging.getLogger(__name__)

# 通用提示词：让模型把图片里与游戏攻略相关的内容都念出来
_VL_PROMPT = (
    "请详细描述这张图片的内容。如果是游戏截图/攻略图，把图中可见的文字、数值、"
    "标题、步骤尽量完整地转录出来；如果是图表/装备信息，逐条列出；"
    "如果只是普通图片，简要描述即可。"
)


class ImageReader(ABC):
    """图片→文本 统一接口。"""

    name: str = "base"

    @abstractmethod
    def read(self, image_path: str | Path) -> str:
        """返回图中提取的文本。"""


class VLImageReader(ImageReader):
    """多模态通道：qwen-vl（OpenAI 兼容 image_url，base64 data URI）。"""

    name = "qwen-vl"

    def read(self, image_path: str | Path) -> str:
        from openai import OpenAI

        if not settings.dashscope_api_key:
            raise RuntimeError("未配置 DashScope Key，无法使用多模态解析")
        client = OpenAI(api_key=settings.dashscope_api_key, base_url=settings.llm_base_url)
        b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
        mime = _mime_of(Path(image_path).suffix)
        resp = client.chat.completions.create(
            model=settings.vision_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": _VL_PROMPT},
                ],
            }],
            temperature=0.1,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            raise RuntimeError("多模态解析返回为空（qwen-vl）")
        return text


class PaddleImageReader(ImageReader):
    """OCR 通道：PaddleOCR 离线（可选依赖，装 requirements-ocr.txt 后可用）。"""

    name = "paddle-ocr"

    def __init__(self):
        self._ocr = None
        try:
            from paddleocr import PaddleOCR  # 可选依赖，延迟导入

            self._ocr = PaddleOCR(
                use_angle_cls=True, lang="ch", show_log=False, use_gpu=False)
            self._cls = True
        except ImportError as e:
            raise RuntimeError(
                "PaddleOCR 未安装：执行 pip install -r requirements-ocr.txt（含 paddlepaddle）"
            ) from e

    def read(self, image_path: str | Path) -> str:
        if self._ocr is None:
            self.__init__()
        result = self._ocr.ocr(str(image_path), cls=self._cls)
        # PaddleOCR 3.x 返回 [[[box, (text, score)], ...], ...]
        lines: list[str] = []
        for page in result or []:
            for item in page or []:
                txt = item[1][0] if isinstance(item[1], (list, tuple)) else ""
                if txt:
                    lines.append(txt)
        return "\n".join(lines)


def read_image(image_path: str | Path, channel: str = "auto") -> tuple[str, str]:
    """按通道解析图片，返回 (文本, 通道名)。

    channel: auto(有 Key 用多模，否则 OCR) / vl / ocr
    """
    reader = get_reader(channel)
    return reader.read(image_path), reader.name


def get_reader(channel: str = "auto") -> ImageReader:
    if channel == "vl":
        return VLImageReader()
    if channel == "ocr":
        return PaddleImageReader()
    # auto：有 Key 用多模（对话语义更好），可强制切 OCR 批量
    if settings.dashscope_api_key:
        return VLImageReader()
    return PaddleImageReader()


def _mime_of(ext: str) -> str:
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
    }.get(ext.lower(), "image/png")