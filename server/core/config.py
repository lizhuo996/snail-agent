# -*- coding: utf-8 -*-
"""全局配置：从 .env + 独立密钥文件读取，代码中不出现任何写死的密钥/地址。

密钥优先级（高→低）：
1. secrets/dashscope.key 单独密钥文件（gitignore，用户选定方案）
2. .env 的 DASHSCOPE_API_KEY（兜底保留）
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 仓库根目录（server/ 的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 单独密钥文件路径（gitignore）
SECRETS_KEY_FILE = BASE_DIR / "secrets" / "dashscope.key"


class Settings(BaseSettings):
    # 大模型（OpenAI 兼容接口；本地默认 Ollama，生产切云端/内网 vLLM 只改这几个值）
    dashscope_api_key: str = ""
    llm_base_url: str = "http://localhost:11434/v1"  # 本地 Ollama OpenAI 兼容端点
    llm_model: str = "qwen2.5:7b"
    embedding_model: str = "nomic-embed-text"
    vision_model: str = ""  # 多模态看图（P2 启用，本地暂未拉模型则留空）

    # 知识库 SQLite 落盘路径（相对仓库根）
    kb_db_path: str = "data/kb.sqlite3"

    # 服务
    ai_service_port: int = 19310

    # 检索参数
    top_k_default: int = 5
    embed_dim: int = 768  # nomic-embed-text 维度（云端 text-embedding-v3 是 1024）
    bm25_weight: float = 0.4  # 混检：向量权重为 1-bm25_weight，默认 α=0.6 向量

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def model_post_init(self, __context):
        """实例化后兜底：secrets/dashscope.key 存在且非空则覆盖 .env 的值。"""
        try:
            key = SECRETS_KEY_FILE.read_text(encoding="utf-8-sig").strip()
            if key:
                self.dashscope_api_key = key
        except FileNotFoundError:
            pass

    @property
    def kb_db_abs(self) -> Path:
        """知识库 DB 的绝对路径。"""
        p = Path(self.kb_db_path)
        return p if p.is_absolute() else BASE_DIR / p


settings = Settings()