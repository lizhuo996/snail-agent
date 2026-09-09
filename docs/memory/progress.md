# 进度日志（倒序追加，最新在上面）

> 格式：`## 日期 | 机器` + 完成 / 下一步

## 2026-09-09 | 开发机（修复密令"一直思考中"）

**问题**：用户发密令后页面一直"思考中"。
**排查**：后端三类密令场景实测均正常（具体码 0s 命中、库外码 7.5s RAG、泛指 0s 列全部）→ 确定为前端两处：
1. **结构性 bug**：SSE `sources` 事件的 data 是裸数组（`_sse("sources", [...])`），前端 `if (evt.sources)` 永远不成立，来源分支永不执行；且旧版页面是 `startsWith('data:')` bug 的缓存 JS，所有事件都不解析 → 一直"思考中"
2. 页面缓存：StaticFiles 默认无 cache 头，浏览器缓存旧 JS；旧版 JS 的 `startsWith('data:')` 解析 bug 一直命中
**修复**：
- `web/index.html`：`processBlock` 用 `Array.isArray(evt)` 识别 sources 事件（兼容裸数组 data）
- `main.py`：`_NoCachePages` 中间件给 `/`、`/index.html`、`/admin` 加 `Cache-Control: no-store`（StaticFiles headers 参数当前 starlette 版本不支持，改中间件）
- 验证：页面响应头 no-store、新版 JS 已含 Array.isArray 判断、密令 SSE 全事件正常、30 pytest 全过

**下一步**
- [ ] 用户刷新页面（Ctrl+F5）后重新发密令确认
- [ ] 其余同前（补充真实攻略 / QQ 渠道）

## 2026-09-09 | 开发机（真实 Boss 表入库 + clear 误删密令修复）

**完成**
- 盘点材料库：`knowledge/raw/` 下 3 份（1 篇脱敏 txt + 2 张真实 Boss 表截图 NO.1-20，此前一直被 build_kb 跳过图片没入库）
- 用 `build_kb.py --image-channel vl` 把两张 Boss 表 qwen-vl 解析入库（打「资料速查,进阶玩法」标签），当前库：3 文档 / 14 块 / 76 密令
- **修复 bug**：`KB.clear()` 原本连 codes 表一起删，全量重建会把 76 条密令清空 → 改为只清 documents/chunks，密令保留；`test_clear` 补断言（clear 后密令仍在）
- 真实问答验证：问"NO.1 魔神龙怎么解封/奖励" → 回答正确（神龙降神50次+20龙珠；魔龙角奖励）且 sources 引用 Boss 表来源

**下一步**
- [ ] Boss 表 20 个魔王全部可答（NO.11-20 已入库，抽查命中）
- [ ] 用户补充更多真实攻略（文字/图片均可，图片会自动走 vl 入库）
- [ ] QQ 渠道对接（等确认）

## 2026-09-09 | 开发机（P2 多模态/文档解析落地）

**完成**
- `server/core/vision.py`：ImageReader 接口 + 双通道——qwen-vl（OpenAI 兼容 image_url base64）+ PaddleOCR（可选依赖延迟导入）；read_image(path, channel) 支持 vl/ocr/auto
- `server/rag/parser.py`：图片经 vision 解析，回填 source_type="image" 与 meta.image_channel
- 场景A（对话直接解析）：`POST /api/chat-upload`（multipart：question+files+url+text）→ 解析并入上下文（标注"优先作为最新依据"）+ SSE `parsed` 事件回显；`/api/parse`、`/api/parse-url` 独立工具接口
- 场景B（建库批量）：`scripts/build_kb.py` 默认解析图片（--no-images 关，--image-channel 切通道），支持 --urls 网页批量入库
- 聊天页：附件多选 chips + 链接输入条，有附件走 chat-upload，parsed 卡片回显
- 新增依赖 python-multipart；30 个 pytest 全过
- ADR：D14（对话侧解析流程）、D15（vision 双通道实现）、D16（BM25 极小语料修复）；设计文档 P2 标记已落地

**下一步**
- [ ] 真实冒烟：重启服务验证 /api/chat-upload（含一张真实攻略截图走 qwen-vl）
- [ ] 用户提供真实攻略 → build_kb 全量重建（图片走 OCR）
- [ ] QQ 渠道对接（仍属 P2 预留，等用户确认是否本期做）

## 2026-09-09 | 开发机（P3 管理后台 v1）

**完成（管理后台第一版，25 个 pytest 全过）**
- 后端 `/api/admin/*`（routes_admin.py）：
  - 知识库：stats / 文档列表 / 删除 / 分块加标签 / 标签统计 / 全量重建（subprocess 跑 build_kb.py）/ 检索测试（真 embedding，无 Key 退化为 BM25）
  - 密令：列表（按状态）、新增（重复 400 拒绝）、编辑、删除、批量导入（每行一条 `密令|奖励|状态|有效期`）
  - 运维：/health、/llm/config（只读）、/llm/test（测试对话）
- 前端 `web/admin/index.html`：单页 4 Tab（知识库/密令/运维/模型），复用 19310 端口（不占新端口）
- KB 层扩展管理方法：list_documents/delete_document/list_chunks/set_chunk_tags/all_tags/list_codes_all/update_code/delete_code
- **发现并修复 BM25 语料过小 bug**：rank-bm25 新版本小语料 idf 为负 → min-max 归一化；单文档无区分度时给基准 0.5，避免搜索全空
- 服务重启冒烟：admin health/kb stats/76 密令/Key 状态全部正常

**下一步**
- [ ] 浏览器 http://127.0.0.1:19310/admin 体验管理后台
- [ ] 真实攻略入库后，用后台「重建」+「检索测试」验证
- [ ] 密令批量导入（从后台粘贴，或运营提供奖励后补充）
- [ ] P2：图片/多模态解析（视觉模型已在配置中）

## 2026-09-09 | 开发机（端口调整 19240 → 19310）

**完成**
- 用户反馈：snail-agent 与 devplan-agent 抢端口 —— 19240 是 devplan 的端口
- 服务端口调整为 **19310**：`server/core/config.py`、AGENTS.md、README、.env.example、设计文档、decisions.md(D1 备注)、env-setup.md 全部同步
- 前端 fetch 均为同源相对路径，无端口硬编码，无需改

**下一步**
- [ ] 浏览器打开 http://127.0.0.1:19310 验证（旧的 19240 不再用）
- [ ] 真实攻略放 knowledge/raw 后重建知识库

## 2026-09-09 | 开发机（前端 SSE 解析再加固）

**完成**
- 用户反馈页面提示"服务端未返回内容"，排查确认：服务端正常（RAG 3s/密令 431ms），根因是前端 SSE 解析仍有盲区
- 重构前端解析：提取 `processBlock` 统一处理；流末尾不完整块（无尾随 `\n\n`）不再丢弃，收尾补处理一次
- error 事件在解析层直接 throw，catch 统一渲染错误（含 HTTP 非 200 时附响应体前 200 字）；兜底提示保留
- 移除误加的重复 `} catch (e) {}`，修复 JS 结构（node --check 通过）
- 重启服务实测：httpx 流式读取 731 字符正常结束；19 个 pytest 全过

**下一步**
- [ ] 浏览器 Ctrl+F5 强刷后验证聊天；若仍异常，请把控制台报错发我
- [ ] 真实攻略放 knowledge/raw 后重建知识库
- [ ] 密令奖励待运营核实补充（P3 管理后台落地后可自行维护）

## 2026-09-09 | 开发机（修复前端“思考中” + 密令批量入库）

**完成**
- **修复“一直显示思考中”**：前端 SSE 解析 bug —— 用 `part.startsWith('data:')` 判断整块，但 SSE 块以 `event:` 开头，导致事件永远解析不到。改为块内取 `data:` 行解析（web/index.html）
- 加兜底：流结束仍无内容时提示“服务端未返回内容”，不再停在思考中
- **密令批量入库**：用户提供 76 条兑换码 → `scripts/seed_codes.py`（可重复执行去重），reward 未知留空待运营补充；`/api/codes` 查询正常
- 聊天密令分支增强：精确命中返回该码；含“密令/兑换码/口令”且无精确命中时列出全部生效密令（走 query_codes，不花 LLM 调用）
- 密令输出格式：reward 为空显示“奖励待补充”，前端卡片解析稳定
- 19 个 pytest 全过；服务重启后实测“有什么密令？”返回 76 条

**下一步**
- [ ] 浏览器 http://127.0.0.1:19310 验证聊天（密令与 RAG 两个场景）
- [ ] 真实攻略放 knowledge/raw 后重建知识库
- [ ] 密令奖励待运营核实补充（管理后台 P3 落地后可自行维护）

## 2026-09-09 | 开发机（配置真 Key + 全链路实测通过）

**完成（真 Key 配置 + 端到端验证）**
- 用户提供 docs/reference 下阿里云百炼 apiKey csv（含真实 Key 与专属 endpoint），已配置：
  - Key → `secrets/dashscope.key`（gitignore）
  - 专属兼容 endpoint（ws-9spiuint1t7qzds8.cn-beijing.maas.aliyuncs.com/compatible-mode/v1）→ `.env`（gitignore）
  - `.gitignore` 新增 `docs/reference/*apiKey*.csv`，敏感 csv 确认不入库
- 实测连通：embedding 1024 维 OK（HTTP 200）、qwen-plus 对话流式 OK
- [ ] 用脱敏示例建真实知识库（真 embedding）→ 启动服务(19240→后改19310) → /api/health `api_key_configured: True`
- **发现并修复 bug**：检索 score 为 numpy.float32 导致 SSE JSON 序列化失败（`Object of type float32 is not JSON serializable`），kb.py 改为 `float()` 强转
- 全链路验证通过：sources（来源+相关度 0.6）→ delta 流式回答 → done

**下一步**
- [ ] 用户把真实攻略放入 `knowledge/raw/` 后，`scripts/build_kb.py` 重建知识库（会清掉脱敏示例）
- [ ] 密令数据提供后录入 codes 表，演示 query_codes
- [ ] 进 P2：图片/多模态解析、QQ 聊天渠道对接

## 2026-09-09 | 开发机（密钥单独存放）

**完成（Key 单独存放）**
- 用户选定方案：DashScope API Key 单独放 `secrets/dashscope.key`（独立密钥文件，.env 保持不变）
- `server/core/config.py` 支持密钥优先级：secrets/dashscope.key > .env 的 DASHSCOPE_API_KEY，读取用 utf-8-sig 兼容 BOM
- `.gitignore` 新增 `secrets/*`（仅放行 `dashscope.key.example` 模板可提交）
- 模板 `secrets/dashscope.key.example` 已提交；真 key 文件 gitignore，本机文件为占位 `sk-paste-your-key-here`
- 新增测试 `test_secrets_key_file_priority`（19 个 pytest 全过）

**下一步**
- [ ] 在 `D:\Work\project\agent\snail-agent\secrets\dashscope.key` 填入真实 Key（阿里云百炼平台获取）
- [ ] 跑 `scripts/build_kb.py` 建真实攻略库 + 实测 RAG 问答质量
- [ ] 进 P2：图片/多模态解析、QQ 聊天渠道对接

## 2026-09-09 | 开发机（③开发 P0+P1 骨架）

**完成（P0 地基 + P1 核心骨架，全部离线测试通过）**
- `server/core/config.py`：配置中心（DashScope key/模型/检索参数/KB 路径，读 .env）
- `server/core/models.py`：统一数据模型 Document/Chunk(tags 多标签)/ParsedContent/Code（D11/D12/D13）
- `server/core/llm.py`：OpenAI 兼容客户端（embed_texts 分批向量化/chat_stream 流式），Key 缺失中文报错
- `server/rag/parser.py`：PDF/Word/Excel/PPT/HTML/txt/md 解析分发，图片 P2 占位
- `server/rag/chunker.py`：500/上限800/重叠80，句子边界切分
- `server/rag/kb.py`：SQLite 库 documents/chunks/codes 三表 + numpy 余弦 + rank-bm25 混检（w=0.4）+ 多标签 OR 过滤 + codes 结构化查询（D4/D13）
- `server/api/main.py`：FastAPI + /api/health + /api/kb/stats + 静态聊天页
- `server/api/routes_chat.py`：/api/chat SSE 流式（密令提问先走 query_codes 精确回答，密令卡片支持复制一行一条）+ /api/codes
- `scripts/build_kb.py`：解析→切块→向量化→入库，支持 --keep/--tags/--skip-embed
- `web/index.html`：手机端风格聊天页，SSE 流式渲染 + 来源标注 + 密令卡片复制
- 依赖补齐安装：python-pptx、beautifulsoup4、rank-bm25（已进 requirements.txt）
- 18 个 pytest 全部通过；已用脱敏示例跑通建库全流程；uvicorn 启服务 /api/health 正常
- 测试中发现并修复：scripts 里 server 不在 sys.path、无扩展名文件（.gitkeep）误入建库、clear 多语句执行问题

**下一步**
- [ ] 配 .env：DASHSCOPE_API_KEY 后，跑 `scripts/build_kb.py` 建真实攻略库并实测 RAG 问答质量
- [ ] 进 P2：图片/多模态解析、QQ 聊天渠道对接
- [ ] 真实攻略材料来源/版权边界确认（demo 阶段用脱敏示例）

## 2026-09-08 | 开发机（密令复制功能补充）

**完成（密令复制功能）**
- 用户确认：密令需要复制功能，复制出来是一行一条密令
- 聊天效果图（01）密令卡片新增「📋 复制全部密令」按钮 + JS（navigator.clipboard / execCommand 兜底），仅复制生效中的纯密令文本，一行一条
- 需求说明 2.6 补充「复制功能」，验收标准新增第 12 条
- 设计文档 P3 预留口子补充复制实现

**下一步**
- [ ] 等你确认效果是否符合预期
- [ ] 确认后进 ③开发：P0 地基 → P1 建库+RAG 问答

## 2026-09-08 | 开发机（UI 效果图）

**完成（功能效果图）**
- 新增 `web/mockups/` 目录，4 张可浏览器打开的高保真 HTML 原型：
  - `00-索引.html`：导航页，展示各效果图卡片
  - `01-聊天问答页.html`：玩家主界面（手机端），含多标签过滤（多选）、上传图片/文档/粘贴链接、来源引用卡片、密令结构化卡片、SSE 流式占位
  - `02-知识库管理后台.html`：管理员侧栏 + 文档列表/多标签维护/重建索引/检索测试
  - `03-密令管理后台.html`：密令列表/新增/批量导入/停用/有效期筛选
  - `04-模型与系统运维.html`：LLM/Embedding/多模态配置 + /api/health 健康卡片 + 解析/OCR 任务状态 + 日志
- 所有页面游戏风格深色 UI（#ffd76a 主色），可双击直接打开

**下一步**
- [ ] 等你确认效果是否符合预期，有调整反馈
- [ ] 确认后进 ③开发：P0 地基 → P1 建库+RAG 问答

## 2026-09-08 | 开发机（当前阶段：②设计完善，多标签+密令结构化已澄清，待确认后进开发）

**完成（密令结构化接口需求确认）**
- 向用户解释"密令结构化接口"含义，用户确认需要
- 需求说明新增 2.6 节「密令结构化接口」：独立密令表 + `query_codes` 查询工具 + 管理后台维护
- 设计文档同步：统一模型新增 `Code`；P3 管理后台加密令管理；扩展口子 ToolRegistry 明确注册 query_codes
- 新增 ADR D13（密令结构化）
- 验收标准新增第 11 条（密令精确返回）

**下一步**
- [ ] 业务方确认需求说明 + 设计文档
- [ ] 确认后进 ③开发：P0 地基 → P1 建库+RAG 问答
- [ ] 攻略材料准备（knowledge/raw/，版权红线：只留脚本+脱敏示例）

## 2026-09-08 | 开发机（当前阶段：②设计完善，多标签需求已澄清，待业务方确认后进开发）

**完成（分类标签需求澄清：多标签）**
- 向用户解释 OCR 概念并确认分类标签
- 澄清关键点：**一个问题可能多个标签** → 标签采用多标签设计
- 需求说明新增 2.5 节「分类标签（多标签）」：初版标签体系 + 多标签语义（一条内容多标签 / 提问多标签 OR 过滤 / 管理后台维护）
- 设计文档同步：Chunk.category → Chunk.tags: list；检索支持 tags OR 过滤；P3 管理后台标签维护
- 新增 ADR D12（多标签设计）
- 验收标准新增第 10 条（多标签）

**下一步**
- [ ] 业务方确认需求说明 + 设计文档
- [ ] 确认后进 ③开发：P0 地基 → P1 建库+RAG 问答
- [ ] 攻略材料准备（knowledge/raw/，版权红线：只留脚本+脱敏示例）

## 2026-09-08 | 开发机（当前阶段：②设计完成，待需求业务方确认后进开发）

> ⚠️ 注意：`7882845` 提交本地已完成，push 因网络失败（连不上 github.com），待网络恢复后补推。

**完成（设计阶段：技术路线与详细设计 v0.1）**
- 新增 `docs/design/技术路线与详细设计_v0.1.md`：P0→P3 四段式演进（每阶段含范围/可见成果/预留口子/验收/测试）
  - P0 地基（服务骨架+离线测试）→ P1 知识库+RAG 问答（建库+引用来源）→ P2 多模态/文档解析（对话+建库双场景，图片多模+OCR 双通道）→ P3 管理后台+增强（分类过滤+结构化速查）
- 技术架构总览图（api/orchestrator/rag/core/admin 分层）
- 关键模块详细设计：统一模型（Document/Chunk/ParsedContent）、SQLite 向量近似+FTS5/BM25 混检融合、parser 分发+图片双通道、管理存储 repository 模式
- 技术选型全景表（含选型理由+备选路径，符合依赖纪律）

**下一步**
- [ ] 业务方确认需求说明 + 设计文档
- [ ] 确认后进 ③开发：P0 地基 → P1 建库+RAG 问答
- [ ] 攻略材料准备（knowledge/raw/，版权红线：只留脚本+脱敏示例）

## 2026-09-08 | 开发机（当前阶段：①需求澄清，待业务方确认）

**完成（多模态/文档解析能力需求澄清）**
- 澄清核心增强需求（用户确认 3 点）：
  1. 场景 = **两者都要**：既能建库时批量解析网页/图片/文档，也能在对话中让智能体直接"看"用户发的网页/图片/文档/文本并回答
  2. 图片解析 = **多模态大模型（qwen-vl）+ 离线 OCR（PaddleOCR）双通道**，按需切换
  3. 文档格式 = **更多格式**（含 Excel/PPT 等）
- 需求说明新增 2.4 节「多模态/文档解析能力」；更新知识库格式、聊天页（上传/链接/文本）、管理后台（解析任务/OCR）、验收标准（对话解析+建库解析）、Demo 范围
- 新增 ADR D8（场景 A 对话 + 场景 B 建库都要）、D9（图片双通道多模+OCR）、D10（文档/网页格式扩展）
- 依赖落地：requirements.txt 增 httpx/pandas/python-pptx 等；新增 requirements-ocr.txt（PaddleOCR 可选，避免拖慢基础环境）

**下一步**
- [ ] 业务方确认需求说明（重点：Demo 范围、攻略版权边界、是否要分类标签、密令结构化接口、离线 OCR 是否常驻启用）
- [ ] 确认后进 ②设计：技术路线与详细设计 + 里程碑 M1/M2/M3
- [ ] M0 管理骨架 + P1 知识库检索/RAG 问答开发

## 2026-09-08 | 开发机（当前阶段：①需求澄清，待业务方确认）

**完成（项目初始化 + 需求澄清）**
- 熟悉参考智能体 devplan-agent 的开发规范（AGENTS.md / SDLC / 记忆机制 / 目录结构 / 统一数据模型）
- 澄清核心需求（用户确认 4 点）：
  1. 技术栈 = FastAPI + LLM API + **轻量检索**（SQLite 向量近似 + 关键词/BM25 混检），不用 Milvus
  2. 大模型 = 通义千问 DashScope（OpenAI 兼容）
  3. 首期建库 = **全套攻略**
  4. 管理后台 = **需要**（随功能阶段配套）
- 建立仓库骨架：AGENTS.md、README、.gitignore、.env.example、requirements、目录结构
- 编写需求说明 docs/requirements/需求说明.md（核心能力 RAG 问答 + 聊天页 + 管理后台 + 验收标准 + Demo 范围）
- 新增 ADR D1~D7（定位/FastAPI+LLM/embedding/SQLite轻量检索/工具层预留/管理后台/SDLC）

**下一步**
- [x] 已建远端私有仓 https://github.com/lizhuo996/snail-agent 并 push master（0f79128）
- [ ] 业务方确认需求说明（重点：Demo 范围、攻略版权边界、是否要分类标签、密令结构化接口）
- [ ] 确认后进 ②设计：技术路线与详细设计 + 里程碑 M1/M2/M3
- [ ] M0 管理骨架 + P1 知识库检索/RAG 问答开发

## 2026-09-08 | 开发机（仓库初始化）

**完成**
- 创建 snail-agent 仓库（本地，master 分支），尚无提交
- 参考 devplan-agent 规范搭建骨架
