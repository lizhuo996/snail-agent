# 新机器环境搭建（snail-agent）

> 目标：全新机器从零把 snail-agent 跑通。软装位置统一 `D:\SoftWare`（D8）。
> 与 devplan-agent 基本一致，唯一差异：本方案**不需要 Docker/Milvus**。

## 1. Git 安装

```powershell
# 安装 Git for Windows 到 D:\SoftWare\Git
git --version
```

## 2. Python 安装

```powershell
# 安装 Python 3.12 到 D:\SoftWare\Python312
& "D:\SoftWare\Python312\python.exe" --version
```

## 3. 项目依赖安装

```powershell
cd D:\Work\project\agent\snail-agent
& "D:\SoftWare\Python312\python.exe" -m pip install -r requirements.txt
& "D:\SoftWare\Python312\python.exe" -m pip install -r requirements-dev.txt
```

## 4. 配置密钥

```powershell
Copy-Item .env.example .env
# 编辑 .env 填入 DASHSCOPE_API_KEY
```

## 5. 建库

```powershell
# 先把攻略材料放入 knowledge/raw/ 下的对应子目录
& "D:\SoftWare\Python312\python.exe" scripts/build_kb.py
```

## 6. 启动服务

```powershell
& "D:\SoftWare\Python312\python.exe" -m uvicorn server.api.main:app --reload --port 19240
```

访问 http://localhost:19240 （聊天页）、/admin（管理后台）。

## 常见问题

### API Key 未配置
- 确认 .env 已创建且 DASHSCOPE_API_KEY 正确；缺失时 /api/health 会如实反映未配置。

### 建库空 / 检索无结果
- 确认 knowledge/raw/ 下已放置攻略材料且格式受支持（PDF/Word/HTML/文本）。
