# 账号密钥备忘（仅限私有仓库）

> 敏感信息一律放 `.env`（已 gitignore），本文件只记录"在哪里申请、Key 缺了找谁"的备忘，绝不写真实密钥。

## DashScope（通义千问 + embedding）

- 控制台：https://dashscope.console.aliyun.com/
- 用途：LLM（qwen-plus）+ 向量化（text-embedding-v3）
- 配置位置：`.env` 的 `DASHSCOPE_API_KEY`
- 缺失表现：`/api/health` 的 llm.api_key_configured = false；问答接口报"Key 未配置"

## GitHub（仓库）

- 仓库：https://github.com/lizhuo996/snail-agent（私有，待建）
- 推送需有 repo 权限的 PAT（Classic）或 SSH key
