# 技术决策记录（ADR）

> 原则：已定的决策不要随意推翻；要变更时先在此文件追加新条目说明理由，再改代码。

## D1 做成独立 Python + FastAPI 服务，核心定位 = 攻略智能问答（RAG）
- 日期：2026-09-08
- 背景：用户要求做一个"最强蜗牛"攻略智能体，核心就是智能问答，属于"简单需求"。
- 决策：新建独立 FastAPI 服务（端口 19310），核心能力 = 基于攻略知识库的 RAG 问答；不引入数据分析/DCA 等 devplan 的重能力。
- 备注（2026-09-09）：端口由 19240 调整为 19310 —— 19240 是 devplan-agent 的端口，避免两个服务互相抢占；变更点见 progress.md。

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
  4. P3 管理后台 + 增强：/admin（知识库管理/系统运维/模型管理）+ 多标签过滤 + 结构化速查；
  5. 统一数据模型（Document/Chunk/ParsedContent 在 server/core/models.py）；parser/ImageReader/SqliteStore/ToolRegistry 预留扩展口子。

## D12 分类标签采用多标签设计（一个问题可能多个标签）
- 日期：2026-09-08
- 背景：用户确认需要分类标签，并强调"一个问题可能多个标签"。
- 决策：
  1. 标签为**多标签**：一条攻略内容（Chunk）可挂多个标签；聊天页提问可同时选多个标签过滤；
  2. 过滤语义：检索带 `tags` 参数时**任一标签命中即返回**（OR），并保留标签供前端分类展示；
  3. 初版标签体系：新手入门 / 系统解析 / 探索地图 / 周活动 / 资料速查 / 进阶玩法；
  4. 管理后台可维护标签（增删标签、给条目重新打标）；
  5. 数据模型：`Chunk.tags: list`（替代单一 `category`），落库 JSON 列。

## D13 密令做结构化接口（独立表 + 查询工具 + 管理后台维护）
- 日期：2026-09-08
- 背景：密令（兑换码）更新频繁、藏身攻略长文，靠 RAG 全文检索易不准/答出过期码；用户确认要结构化接口。
- 决策：
  1. 独立密令表：`text(密令) | reward(奖励) | status(生效/停用/已过期) | valid_until | batch/来源 | remark`；
  2. 注册 MCP 规范工具 `query_codes`（D5 ToolRegistry）供问答链路精确查表；
  3. 密令问题回答返回 码+奖励+当前是否生效，比全文检索准且快；
  4. 管理后台提供 密令管理（新增/批量导入/停用/设有效期），密令仍可同时带「资料速查」标签入知识库，两条路径互不冲突；
  5. 数据模型 `server/core/models.py` 定义 `Code`（D13）。

## D14 对话侧解析（P2 场景A）：「附件解析为纯文本并入上下文 + SSE parsed 事件」
- 日期：2026-09-09
- 背景：P2 要求聊天页能发图/发文档/贴链接后直接回答，且要"回显解析出的文本摘录"。
- 决策：
  1. 新增 `POST /api/chat-upload`（multipart：question + files + url + text），复用 `_stream` 问答流，不破坏现有 JSON `/api/chat`；
  2. 解析结果统一 `ParsedContent`，以**文本形式**并入 user 上下文（标注"用户上传的补充材料，优先作为最新依据"），不单独建库；
  3. 问答流新增 `parsed` SSE 事件，回显每个附件的标题与前 200 字摘录；
  4. `POST /api/parse`（文件）、`POST /api/parse-url`（链接）独立成工具接口，管理后台/前端可复用；
  5. 新增依赖 `python-multipart`（multipart 表单解析）。

## D15 图片双通道实现：`vision.py` ImageReader 接口（qwen-vl + PaddleOCR）
- 日期：2026-09-09
- 背景：D9 定了"多模态 + 离线 OCR"双通道策略，P2 需落地为代码。
- 决策：
  1. `server/core/vision.py`：`ImageReader` 抽象 + `VLImageReader`（qwen-vl，OpenAI 兼容 image_url 传 base64 data URI）+ `PaddleImageReader`（PaddleOCR 可选依赖，延迟导入）；
  2. 通道策略 `read_image(path, channel)`：`vl`/`ocr`/`auto`（有 Key 用多模，否则 OCR）；对话默认 auto，建库默认 ocr（`--image-channel` 可切）；
  3. `parser.parse_path(..., image_channel=...)` 图片走 vision，产出 `ParsedContent(source_type="image")`；
  4. `scripts/build_kb.py` 默认解析图片（`--no-images` 关闭），并支持 `--urls` 网页批量入库；
  5. PaddleOCR 未装时抛"明确报错"提示安装 requirements-ocr.txt，不静默失败。

## D16 rank-bm25 极小语料打分异常修复（min-max 归一化）
- 日期：2026-09-09
- 背景：rank-bm25 新版本在语料极小（尤其单文档）时 idf 为负，`score > 0` 过滤会把唯一/少量命中全部滤空，导致检索返回空。
- 决策：
  1. `_bm25_rank` 改为 min-max 归一化，把得分映射到 [0,1]，与向量分同量纲，负分也能正确排序；不再用 `>0` 过滤；
  2. 单文档/全等分场景（bmax<=bmin）且确有词命中时，给唯一文档基准分 0.5 参与融合，避免搜索全空；
  3. 融合侧直接使用归一化 b 加权（移除旧的 bmax 二次归一）。
