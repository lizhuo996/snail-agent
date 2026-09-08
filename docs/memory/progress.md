# 进度日志（倒序追加，最新在上面）

> 格式：`## 日期 | 机器` + 完成 / 下一步

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
- [ ] 业务方确认需求说明（重点：Demo 范围、攻略版权边界、是否要分类标签、密令结构化接口）
- [ ] 确认后进 ②设计：技术路线与详细设计 + 里程碑 M1/M2/M3
- [ ] M0 管理骨架 + P1 知识库检索/RAG 问答开发

## 2026-09-08 | 开发机（仓库初始化）

**完成**
- 创建 snail-agent 仓库（本地，master 分支），尚无提交
- 参考 devplan-agent 规范搭建骨架
