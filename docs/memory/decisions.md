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

## D8 多模态/文档解析能力：场景 A（对话直接解析）+ 场景 B（建库批量解析）都要
- 日期：2026-09-08
- 背景：用户要求智能体"可以直接看网页、文档、图片、文本，需要解析图片内容"，确认两种场景都要。
- 决策：
  1. 场景 A：聊天接口支持用户上传图片/文档、粘贴网页链接/文本，智能体解析后结合知识库回答；
  2. 场景 B：建库阶段把这些格式作为原材料自动解析收录进知识库；
  3. 统一的解析层（server/rag/parser.py 等）封装各类格式提取文本，两种场景复用同一套解析函数；
  4. 解析结果统一走"轻量混检"入库或拼进对话上下文（2.4）。

## D9 图片内容解析：多模态大模型 + 离线 OCR 双通道，按需切换
- 日期：2026-09-08
- 背景：用户确认图片解析"两者都要"（多模 + 离线 OCR）。
- 决策：
  1. **多模态通道**：用通义千问 qwen-vl（DashScope 多模态）直接看懂图片、提取语义，走 OpenAI 兼容接口 image_url，无需本地重型依赖；适合对话中理解用户截图；
  2. **离线 OCR 通道**：用 PaddleOCR 本地批量提取文字，离线可跑，适合建库时大量攻略截图文字化；
  3. 通道策略：对话单张/少量图用多模；批量建库优先离线 OCR；
  4. PaddleOCR 依赖较重（paddlepaddle），列为**可选依赖**（requirements-ocr.txt），代码可选导入；未装时回退多模态通道或明确报错，不影响基础环境；
  5. embedding 仍用 text-embedding-v3 对提取出的文本做索引（同一套 D3）。

## D10 文档/网页解析格式扩展：PDF/Word/Excel/PPT/HTML/文本
- 日期：2026-09-08
- 背景：用户确认文档/文本类要支持"更多格式（含 Excel/PPT 等）"。
- 决策：解析层（server/rag/parser.py）按扩展名分发：
  - 网页：httpx 抓取 + BeautifulSoup 提取正文（去导航/广告）；
  - PDF：pymupdf + pdfplumber；Word：python-docx；Excel：openpyxl/pandas（含多 sheet）；PPT：python-pptx；纯文本：直接；
  - 新增依赖：httpx、pandas、python-pptx（openpyxl、beautifulsoup4 已在要求中），写入 requirements.txt；PaddleOCR 单独 requirements-ocr.txt（D9）。

## D11 分阶段演进规划 P0→P3（设计评审结论）
- 日期：2026-09-08
- 背景：设计阶段需要把开发拆成可演示的里程碑，遵循"阶段渐进、每阶段留口子、成果可见"原则。
- 决策（详见 `docs/design/技术路线与详细设计_v0.1.md`）：
  1. P0 地基：服务骨架 + `/api/health` + 离线测试；
  2. P1 知识库 + RAG 问答（第一个可见成果）：建库脚本 + 检索混检 + SSE 问答 + 引用来源；
  3. P2 多模态/文档解析：对话直接解析（上传/链接/文本）+ 建库批量解析，图片多模 + 离线 OCR 双通道；
  4. P3 管理后台 + 增强：/admin（知识库管理/系统运维/模型管理）+ 分类过滤 + 结构化速查；
  5. 统一数据模型（Document/Chunk/ParsedContent 在 server/core/models.py）；parser/ImageReader/SqliteStore/ToolRegistry 预留扩展口子。
