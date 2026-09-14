# 新机器环境搭建（snail-agent）

> 目标：全新机器从零把 snail-agent 跑通。软装位置统一 `D:\SoftWare`（D8）。
> 模型：**本地 Ollama**（默认，D17），不依赖云端 API Key。

## 1. 安装 Git

```powershell
git --version   # 已装 D:\SoftWare\Git 的跳过
```

## 2. 安装 Python 3.12（D:\SoftWare\Python312）

```powershell
& "D:\SoftWare\Python312\python.exe" --version
```

## 3. 安装并启动 Ollama（D:\SoftWare\Ollama）

```powershell
# 安装后启动服务（Windows 下 Ollama 默认开机自启，也可手动拉模型）
& "D:\SoftWare\Ollama\ollama.exe" serve   # 或直接启动 "Ollama app"
# 拉取对话模型 + embedding 模型（RTX 2060 SUPER 8GB 用 7B，显存更大可换 14B）
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

## 4. 项目依赖安装

```powershell
cd D:\Project\snail-agent
& "D:\SoftWare\Python312\python.exe" -m pip install -r requirements.txt
& "D:\SoftWare\Python312\python.exe" -m pip install -r requirements-dev.txt
```

## 5. 密钥（可选）

本地 Ollama 无需 Key。若后续切云端 DashScope：`Copy-Item .env.example .env` 并在 `secrets/dashscope.key` 填 Key（优先级最高，D17）。

## 6. 建库

```powershell
# 先把攻略材料放入 knowledge/raw/ 下的对应子目录
& "D:\SoftWare\Python312\python.exe" scripts/build_kb.py
```

## 7. 启动服务

```powershell
& "D:\SoftWare\Python312\python.exe" -m uvicorn server.api.main:app --reload --port 19310
```

访问 http://localhost:19310 （聊天页）、/admin（管理后台）。

## 常见问题

### Ollama 未启动 / 模型未拉
- `ollama list` 应有 qwen2.5:7b 与 nomic-embed-text；无则按第 3 步拉取。

### 建库空 / 检索无结果
- 确认 knowledge/raw/ 下已放置攻略材料且格式受支持（PDF/Word/HTML/文本）。

### 从云端切回 / 本地切云端
- 本地 → 云端：改 `server/core/config.py` 的 base_url/model/embedding_model/embed_dim，或走 .env 覆盖（LLM_BASE_URL/LLM_MODEL/EMBEDDING_MODEL）。
- 注意 embed 维度不同需 `scripts/build_kb.py` 全量重建库。
