# 每日开发进度记录

本文档用于记录企业知识库 AI 客服 Agent Demo 的每日开发进度、关键变更、验证结果和下一步计划。

## 项目当前阶段规划

1. 基础聊天闭环
2. 知识库上传与文档解析
3. RAG 核心闭环
4. 客服基础功能
5. 管理后台
6. Tool Calling / 企业系统模拟

---

## 2026-07-07 昨日开发摘要

### 开发阶段

- 阶段 0：需求收敛与开发计划整理
- 阶段 1：基础聊天闭环

### 完成内容

- 明确项目定位为“通用企业智能客服 Agent Demo”。
- 明确基础版目标：先做通用、可运行、可演示、可扩展的基础智能客服，而不是一开始做复杂企业级 SaaS。
- 明确 RAG 是核心能力，但第一版只做最常见、基础、通用的 RAG，方便未来迁移到其他企业项目。
- 将开发路线整理为 6 个阶段：
  1. 基础聊天闭环
  2. 知识库上传与文档解析
  3. RAG 核心闭环
  4. 客服基础功能
  5. 管理后台
  6. Tool Calling / 企业系统模拟
- 明确技术栈保留：
  - React
  - FastAPI
  - DeepSeek API
  - Embedding
  - Chroma
  - PostgreSQL + pgvector 作为 V1 增强方向
  - RAG
  - 简单 Tool Calling
- 完成阶段 1 基础聊天版本：
  - React 聊天界面
  - FastAPI 后端接口
  - DeepSeek / OpenAI-compatible LLM 调用封装
  - 流式输出
  - 无 API Key 时本地演示回复
- 初始化 Git 仓库并首次推送到 GitHub。

### 关键变更

- 更新需求文档，收敛为“通用基础版 RAG 智能客服 Agent”。
- 更新开发计划，改为 6 阶段推进。
- 更新 README，补充项目定位、技术栈和启动说明。
- 建立前后端基础项目结构。

### 验证结果

- 前端页面可访问。
- 后端健康检查接口正常。
- 前端可发送消息并显示后端回复。
- 首次 GitHub 推送成功。

### 遇到的问题

- 初次推送时 GitHub HTTPS 凭据无效，后通过本机 GitHub CLI keyring 账号完成推送。
- 后续检查发现部分中文内容存在编码损坏风险，需要统一清理为正常 UTF-8。

### 下一步

- 修复阶段 1 中文文案和日志中的编码问题。
- 进入阶段 2：知识库上传与文档解析。

---

## 2026-07-08 今日开发摘要

### 开发阶段

- 阶段 1 收尾修复
- 阶段 2：知识库上传与文档解析

### 完成内容

- 修复阶段 1 中的中文编码问题：
  - 后端 LLM system prompt
  - 本地演示回复
  - 前端聊天界面中文文案
  - 开发计划和开发日志文档
- 完成阶段 2 最小闭环：
  - 文档上传接口
  - 文档列表接口
  - 文档解析预览接口
  - 文档删除接口
  - PDF / TXT / Markdown 支持
  - 简单文本清洗
  - 本地文件和 JSON 元数据保存
  - 前端知识库管理区域
- 明确阶段 2 状态口径：
  - 当前同步处理只使用 `processed`、`failed`
  - `pending`、`processing`、`indexed` 放到阶段 3 或 V1 增强
- 更新 `.gitignore`，忽略本地上传数据目录 `backend/data/`。

### 关键变更

- 新增 `backend/app/api/documents.py`
- 新增 `backend/app/services/document_service.py`
- 新增 `backend/app/schemas/document.py`
- 更新 `backend/app/main.py`，注册文档管理接口
- 更新 `backend/requirements.txt`，加入：
  - `python-multipart`
  - `pypdf`
- 更新 `frontend/src/App.tsx`，增加知识库管理工作区
- 更新 `frontend/src/styles.css`，支持聊天区和知识库区并排布局
- 更新 `docs/development_plan.md`，恢复正常中文并修正阶段 2 计划口径
- 更新本开发日志

### 验证结果

- 后端编译通过：`python -m compileall app`
- 前端构建通过：`npm run build`
- 后端接口验证通过：
  - `/api/health`
  - `/api/documents`
  - `/api/documents/{id}/preview`
  - `DELETE /api/documents/{id}`
- 文档格式补测通过：
  - Markdown 上传、解析、预览、删除通过
  - TXT 上传、解析、预览、删除通过
  - PDF 上传、解析、预览、删除通过
- 关键源码和 Markdown 文档完成乱码扫描，未发现残留坏编码。

### 遇到的问题

- `document_service.py` 和开发计划文档曾出现中文编码损坏，已整体重写修复。
- 阶段 2 原计划中的状态 `pending / processing / indexed / failed` 与当前同步实现不一致，已调整为更贴合基础 Demo 的 `processed / failed`。
- PowerShell 终端有时会把 UTF-8 中文响应显示成乱码，后续以源码文件内容和接口验证结果为准。

### 当前结论

- 阶段 1 已完成。
- 阶段 2 的基础版闭环已完成。
- 当前项目已经具备：
  - 基础聊天
  - 文档上传
  - 文档解析
  - 文档列表
  - 解析预览
  - 删除文档

### 下一步

- 进入阶段 3：RAG 核心闭环。
- 阶段 3 优先实现：
  - 文本切片
  - chunk metadata
  - Embedding
  - Chroma 入库
  - Top-K 检索
  - RAG Prompt
  - 基于文档回答
  - 引用来源
  - 无依据拒答

---

## 2026-07-08 阶段 2 最终复查与推送前整理

### 复查结论

- 阶段 2 已完成，可以进入阶段 3。
- 阶段 2 范围内没有未完成项。
- 文本切片、Embedding、Chroma 入库、Top-K 检索、RAG Prompt、引用来源和无依据拒答属于阶段 3，不计入阶段 2 未完成项。

### 复查内容

- 对照阶段 2 验收标准重新检查功能范围。
- 检查后端文档上传、列表、解析预览、删除接口。
- 检查前端知识库管理区的上传、刷新、查看解析、删除交互。
- 检查开发计划和阶段 2 状态口径是否一致。

### 修复内容

- 修复前端上传成功后文件选择框未完全清空的小问题。
- 上传成功后同时清空 React 状态和真实 file input 值，避免用户连续选择同一个文件时不触发变化。

### 验证结果

- 后端编译通过：`python -m compileall backend/app`
- 前端构建通过：`npm run build`
- Markdown 上传、解析、预览、删除通过。
- TXT 上传、解析、预览、删除通过。
- PDF 上传、解析、预览、删除通过。
- 非法格式上传返回 `400`，拦截正常。
- 删除测试文档后列表恢复为空。
- 关键文件按 UTF-8 检查正常。

### 下一步

- 提交并推送当前阶段成果。
- 下一阶段开始开发 RAG 核心闭环。
