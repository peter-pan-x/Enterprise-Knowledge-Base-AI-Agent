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

v0.1 基础聊天版本：

- React 用户聊天界面
- FastAPI 后端服务
- 流式聊天响应
- OpenAI-compatible LLM 配置
- 未配置 API Key 时使用本地演示回复，方便先打通流程

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
