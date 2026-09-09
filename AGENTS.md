# snail-agent 项目说明（opencode 自动读取）

> 本文件是 opencode 每次会话自动加载的项目上下文。**任何机器上打开本项目，先读本文件和 `docs/memory/` 下的记忆文件，再动手。**

## 项目是什么

最强蜗牛（游戏）攻略智能体：对「最强蜗牛」游戏的全套攻略内容做智能问答（RAG）的独立 AI 服务。玩家/运营可以在聊天页面提问，例如"新手前期刷哪个图""贵重品怎么选""这周抽奖周怎么打""XX 密令是什么"，智能体基于攻略知识库检索并给出引用来源的回答。

Demo 阶段范围：全套攻略建知识库（轻量检索：SQLite 向量近似 + 关键词/BM25 混检）+ RAG 问答 + 管理后台（知识库管理/系统运维/模型管理）+ 简单聊天网页。

## 技术栈

| 层 | 技术 |
|---|---|
| AI 服务 | Python 3.12 + FastAPI + SSE 流式 |
| 大模型 | 通义千问 API（DashScope，OpenAI 兼容接口），demo 用 qwen-plus |
| 向量化 | DashScope text-embedding-v3（检索用，OpenAI 兼容接口） |
| 知识库存储 | SQLite（系统内置 sqlite3，零依赖）：向量近似 + FTS5 关键词/BM25 混检（D4） |
| 文档解析 | PyMuPDF + pdfplumber（PDF 正文+表格），python-docx（Word），HTML/纯文本直接收 |
| 工具层 | 进程内 ToolRegistry，接口按 MCP 规范设计，三期拆独立 MCP server（沿用 devplan D5） |
| 管理后台 | 原生 HTML+JS（`web/admin/`），管理 API 前缀 `/api/admin/*`，随功能阶段配套（沿用 D17 思路） |
| 前端 | 单页 HTML+JS（原生 fetch + SSE） |

## 目录结构

```
snail-agent/
├── AGENTS.md            # 本文件：opencode 跨机器记忆入口
├── docs/
│   ├── design/          # 技术路线与详细设计（后续阶段）
│   ├── requirements/    # 需求说明
│   ├── reference/       # 游戏资料、攻略来源等参考资料
│   └── memory/          # ★ 记忆文件（每次会话必读、任务后必更新）
│       ├── progress.md  #   进度日志（倒序追加）
│       ├── decisions.md #   技术决策记录（ADR）
│       ├── env-setup.md #   新机器环境搭建步骤
│       └── account.md   #   账号密钥备忘（仅限私有仓库）
├── knowledge/raw/       # 攻略原文 PDF/Word/HTML（建库原料，gitignore 脱敏）
├── server/              # FastAPI AI 服务
│   └── core/models.py   # ★ 统一数据模型（跨模块数据唯一出处，禁止各模块重复定义）
├── web/                 # 聊天页面 + 管理后台
├── scripts/             # 建库等脚本
├── tools/               # 文档生成等辅助脚本
├── tests/               # pytest 用例（按 SDLC 测试阶段执行）
├── requirements.txt     # 运行依赖
├── requirements-dev.txt # 测试/开发依赖（pytest、httpx）
└── docker-compose.yml   # （预留，当前轻量方案不强制）
```

## 记忆机制（重要）

- **会话开始**：读 `docs/memory/progress.md` 了解进展，读 `decisions.md` 了解已定方案（不要推翻已有决策，除非用户要求）
- **边做边记（硬性规则）**：每完成一个阶段性动作、每确立一条新约定/决策，立即写入记忆文件并随代码提交，不许攒到收尾才补记
- **任务结束**：把本次做了什么、下一步是什么追加到 `progress.md`
- 这些文件随代码一起 git 提交，实现"公司/家里两台电脑无缝接续"

## 全局硬约定（两台电脑都必须遵守）

- **所有软件一律安装到 `D:\SoftWare\<软件名>`，禁止装 C 盘**（沿用 devplan D8、env-setup.md）
- **push 策略**：完成任务/阶段后**立即 `git push`**（用户授权：每次改完直接推送）；push 失败时提交先本地累积，下次任务开头补推（沿用 devplan D10）

## 开发约定

- 语言：代码注释、文档、commit message 用中文
- commit 格式：`<类型>: <中文描述>`，类型用 feat/fix/docs/chore/refactor
- **软件安装位置：一律装 `D:\SoftWare`，禁止装 C 盘**（两台电脑都遵守）
- 敏感信息不进仓库：`.env` 已 gitignore，密钥只放 `.env.example` 模板
- **保密红线**：本仓库虽为 private，但禁止提交游戏攻略原文字（涉及转载/版权，只留建库脚本与脱敏示例）；知识原文放 `knowledge/raw/`（gitignore）
- Python 包管理：先用 pip + requirements.txt（demo 够用）
- **统一数据模型**：跨模块数据一律定义在 `server/core/models.py`，禁止各模块重复定义（沿用 devplan D15）
- **新增依赖**：必须写进 requirements*.txt，并在技术栈表（或 decisions.md）注明选型理由；禁止引无理由的重型依赖

## 软件开发生命周期（SDLC）★严格按流程执行

> 项目从产品到测试发布，必须按五个阶段顺序推进，**禁止跳级**：需求未确认不进设计，设计未记录 ADR 不写代码，代码未过测试不发布。当前所处阶段见 `docs/memory/progress.md`。

| 阶段 | 必须产出 | 完成门槛 |
|---|---|---|
| ① 产品/需求 | `docs/requirements/` 需求说明（业务功能 + Demo 范围 + 验收标准） | 业务方确认，验收标准可衡量 |
| ② 设计 | `docs/design/` 技术路线与详细设计 + `decisions.md` 对应 ADR | 选型有理由，里程碑可拆解，ADR 已记录 |
| ③ 开发 | `server/` `web/` `scripts/` 代码，按 M1/M2/M3 里程碑推进 | 功能实现、接口可用；边做边记 progress.md |
| ④ 测试 | `tests/` pytest 用例 + 离线冒烟 | 关键接口用例通过，无回归（命令见下） |
| ⑤ 发布 | 新机器按 `env-setup.md` 一键跑通 + `/api/health` 检查 | 新机器按 env-setup 一键跑通 |

- 每完成一个阶段，在 `docs/memory/progress.md` 勾掉并记录产物，证据留在 git
- 阶段性改动须同步更新设计文档相关章节（改接口/新增 Agent/新增依赖都要改）
- 测试先保"离线可跑"：不依赖外部 API Key 的用例优先（如 /api/health 冒烟），依赖外部的用例用 fixture/mock 隔离

## 常用命令

```powershell
# Python 安装在 D:\SoftWare\Python312（见 docs/memory/env-setup.md）
$py = "D:\SoftWare\Python312\python.exe"

# 安装依赖（首次）
$py -m pip install -r requirements.txt
$py -m pip install -r requirements-dev.txt

# 建库（解析 knowledge/raw 下的攻略 → SQLite 知识库）
$py scripts/build_kb.py

# 跑测试（离线，不依赖 Key）
$py -m pytest tests/ -v

# 启动 AI 服务
$py -m uvicorn server.api.main:app --reload --port 19310
```

## 当前状态

见 `docs/memory/progress.md`。
