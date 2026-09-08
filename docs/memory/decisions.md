# 技术决策记录（ADR）

> 原则：已定的决策不要随意推翻；要变更时先在此文件追加新条目说明理由，再改代码。

## D1 做成独立 Python + FastAPI 服务，核心定位 = 攻略智能问答（RAG）
- 日期：2026-09-08
- 背景：用户要求做一个"最强蜗牛"攻略智能体，核心就是智能问答，属于"简单需求"。
- 决策：新建独立 FastAPI 服务（端口 19240），核心能力 = 基于攻略知识库的 RAG 问答；不引入数据分析/DCA 等 devplan 的重能力。

## D2 Demo 阶段用通义千问 API（DashScope，OpenAI 兼容接口），生产可切私有化
- 日期：2026-09-08
- 理由：demo 无 GPU 资源，API 便宜可验证全流程；DashScope 提供 OpenAI 兼容接口，切自建 vLLM 只改 base_url 与模型名，代码不动。
- 约束：demo 只允许收录脱敏/可公开攻略，禁止把版权原文提交仓库。

## D3 向量化用 DashScope text-embedding-v3（OpenAI 兼容接口）
- 日期：2026-09-08
- 理由：与 LLM 同一厂商同一接口，少维护本地 embedding 模型，中文检索效果满足游戏攻略场景。

## D4 知识库存储 = SQLite（向量近似 + FTS5 关键词/BM25 混检），不引外部向量库
- 日期：2026-09-08
- 背景：用户明确"轻量检索方案"，且攻略问答是"简单需求"，无需 Milvus 的重部署（对比 devplan D3 用 Milvus）。
- 决策：
  1. 用系统内置 sqlite3 建库，零依赖落盘；向量存 BLOB，用 numpy 做余弦相似度近似检索；
  2. 建 FTS5 表做关键词检索，配合 rank-bm25 评分，与向量 score 混检（加权融合）取 Top-K；
  3. 建库脚本 scripts/build_kb.py，解析 PDF/Word/HTML/文本 → SQLite；
  4. 依赖：numpy（相似度）、rank-bm25（BM25），均为轻量，已写入 requirements.txt。
- 升级路径：数据规模上来后，可无痛切 Milvus/pgvector，只换 repository 实现。

## D5 工具层沿用 devplan 思路：进程内 ToolRegistry，接口对齐 MCP 规范，三期拆独立 server
- 日期：2026-09-08
- 理由：当前问答场景暂时不需要工具调用；预留统一工具 schema（name/description/inputSchema），后续加"密令查询/装备查询"等结构化工具时按 MCP 规范接入，可平移到 FastMCP server。

## D6 管理后台（/admin）随功能阶段配套（沿用 devplan D17 思路）
- 日期：2026-09-08
- 决策：
  1. 独立 `/admin` 页面（原生 HTML+JS，`web/admin/`），管理 API 前缀 `/api/admin/*`；
  2. 模块随阶段配套：M0 骨架 + 系统运维 + 模型管理 → P1+ 知识库管理；
  3. 存储：Demo 用 SQLite（内置 sqlite3 零依赖），落盘路径 gitignore 不入库；生产可切其它库只换 repository；
  4. 模型配置（base_url/model/Key）运行时可编辑，持久化本地 `.env` 覆盖键，重启生效，不进代码不进 git；
  5. demo 单管理员，登录/角色鉴权后期补。

## D7 SDLC 阶段门禁：需求→设计→开发→测试→发布，严格顺序执行（沿用 devplan D15）
- 日期：2026-09-08
- 决策：
  1. 五阶段（①需求 ②设计 ③开发 ④测试 ⑤发布）各有必须产出与完成门槛，定义见 AGENTS.md「软件开发生命周期」节；当前阶段见 progress.md；
  2. 需求未确认不进设计；设计未记录 ADR 不写代码；代码未过 pytest 不视为完成；
  3. 新增依赖必须写入 requirements*.txt 并注明选型理由；
  4. 跨模块数据模型统一放在 `server/core/models.py`，禁止各模块重复定义。
