# Enterprise Knowledge Base AI Agent

一个通用企业智能客服 Agent Demo。

项目目标不是一开始做完整企业级 SaaS，而是先完成最常见、最基础、可扩展的智能客服流程：

```text
用户提问 -> RAG 检索企业知识库 -> LLM 基于文档回答 -> 展示引用来源 -> 无答案时记录知识缺口
```

RAG 是本项目核心能力，但基础版只做通用标准流程，不追求复杂算法。后续可以在此基础上扩展混合检索、Rerank、业务系统工具调用、工单、订单、CRM / ERP 集成等能力。

## 技术栈

- React
- FastAPI
- DeepSeek API
- Embedding
- Chroma：基础 Demo 默认向量数据库
- PostgreSQL + pgvector：V1 增强版向量数据库方案
- RAG
- 简单 Tool Calling

## 当前阶段

v0.6 完整 Demo：

- PDF、扫描 PDF、文字图片、TXT、Markdown、CSV、Word、Excel 文档解析
- 格式感知清洗、页眉页脚去重、切片、Embedding 和 Chroma 索引
- 基于知识库的流式问答、来源引用和无依据拒答
- 历史会话、回答反馈、知识缺口和转人工请求
- Dashboard、对话详情、反馈、知识缺口和运行日志后台
- Mock 订单查询、工单创建和工具调用日志
- OpenAI-compatible LLM 配置；未配置 API Key 时使用本地演示回复
- 多知识库的新增、编辑、启停与删除保护；文档级检索启停
- 可配置欢迎语、无答案兜底、转人工话术、自动转人工关键词、未命中自动转人工与模型补充规则
- 渠道与业务系统适配器接口：部署时接入淘宝、抖店、CRM、ERP 或订单系统，无需改 RAG 核心

## 交付到新公司的方式

本仓库是通用版，不包含任何客户资料、API Key 或数据库内容。交付时复制项目后：配置 `.env`、创建管理员、上传该公司的资料，并按开放平台权限实现 `ChannelAdapter` 和 `BusinessAdapter`。核心 RAG、会话、审计和客服策略无需重写。

渠道接入和订单/工单系统目前提供的是稳定的扩展接口，不内置淘宝、抖店等平台的真实连接器；这部分必须在目标公司取得其开放平台授权、确认业务字段和人工服务流程后实现。

## 本地启动

### 1. 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

如需接入 DeepSeek，在 `backend/.env` 中填写：

```env
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=你的 API Key
LLM_MODEL=deepseek-chat
```

本地演示会初始化 `admin/admin123` 与 `user/user123` 两个账号；生产部署前必须在 `backend/.env` 设置随机 `AUTH_SECRET`，并替换初始账号密码。

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

打开：

```text
http://localhost:5173
```

支持的知识库文件：`.pdf`、`.png`、`.jpg`、`.jpeg`、`.webp`、`.bmp`、`.tif`、`.tiff`、`.txt`、`.md`、`.markdown`、`.csv`、`.docx`、`.xlsx`、`.xls`。

### 3. 验证

```bash
cd backend
python -m unittest discover -s tests -v

cd ..\frontend
npm run build
```

管理后台可设置欢迎语、兜底与转人工策略；普通客服用户只会读取欢迎语，不会读取关键词和模型规则等管理配置。

检索会过滤低置信度向量结果；如客户资料规模或术语明显不同，可在 `.env` 用 `RAG_MIN_SCORE` 调整阈值，并用真实常见问法做回归测试。

## 六阶段开发路线

1. 阶段 1：基础聊天闭环  
   React 聊天界面 + FastAPI 后端 + DeepSeek API，先让 AI 聊天能跑。

2. 阶段 2：知识库上传与文档解析  
   上传 PDF / TXT / Markdown，展示文档列表、文档状态，并解析出文本。

3. 阶段 3：RAG 核心闭环  
   文本切片、Embedding、Chroma 向量入库、Top-K 检索、Prompt 拼接、引用来源、无依据拒答。

4. 阶段 4：客服基础功能  
   聊天记录、历史会话、用户反馈、知识缺口记录、转人工入口。

5. 阶段 5：管理后台  
   Dashboard、知识库管理、文档管理、对话记录、反馈记录、知识缺口列表、RAG 检索日志。

6. 阶段 6：Tool Calling / 企业系统模拟  
   订单查询 Mock API、创建工单 Mock API、工具调用记录、自然语言结果返回。

优先先完成阶段 1-3。阶段 3 完成后，项目就已经具备 GitHub、简历和面试展示价值。

## 基础版不做什么

- 不做复杂多租户 SaaS。
- 不做真实 CRM / ERP / OA 集成。
- 不做复杂权限体系。
- 不做高并发和高可用架构。
- 不做混合检索、Rerank、多路召回等高级 RAG。

这些能力都可以作为后续扩展方向。
