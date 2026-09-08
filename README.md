# snail-agent

最强蜗牛（游戏）攻略智能体 Demo —— 基于全套攻略知识库的智能问答（RAG）。

## 快速开始

新机器请先看 [docs/memory/env-setup.md](docs/memory/env-setup.md)。

```powershell
# 1. 配置密钥
Copy-Item .env.example .env   # 填入 DASHSCOPE_API_KEY

# 2. 建库 + 启动服务
python scripts/build_kb.py
python -m uvicorn server.api.main:app --reload --port 19240
```

访问 http://localhost:19240 打开聊天页，http://localhost:19240/admin 打开管理后台。

## 文档导航

| 文档 | 内容 |
|---|---|
| `docs/requirements/需求说明.md` | 需求说明（业务功能 + Demo 范围 + 验收标准） |
| `docs/design/` | 技术路线与详细设计（后续阶段） |
| `docs/reference/` | 游戏资料、攻略来源等参考资料 |
| `docs/memory/progress.md` | 当前进度（每次开发前后必看） |
| `docs/memory/decisions.md` | 技术决策记录 |

## 协作约定

- opencode 用户：会话开始先读 `AGENTS.md`，任务结束更新 `docs/memory/`
- 开工前 `git pull`，收工后 `git push`
- 禁止提交：`.env`、游戏攻略原文字（版权）、内网账号密码
