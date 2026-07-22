import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  CheckCircle2,
  Database,
  FileText,
  Headphones,
  History,
  LayoutDashboard,
  MessageSquarePlus,
  RefreshCw,
  Send,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  Upload,
  User
} from "lucide-react";

type Role = "user" | "assistant";
type AppRole = "user" | "admin";

type AuthSession = {
  accessToken: string;
  user: { id: string; username: string; role: AppRole };
};

type RagSource = {
  document_id: string;
  filename: string;
  chunk_id: string;
  chunk_index: number;
  page_number?: number | null;
  score: number;
  preview: string;
};

type Message = {
  id: string;
  role: Role;
  content: string;
  sources?: RagSource[];
  serverMessageId?: string;
  feedback?: "helpful" | "unhelpful";
  handoffRequested?: boolean;
  toolName?: string;
};

type ConversationSummary = {
  id: string;
  title: string;
  updated_at: string;
  message_count: number;
};

type DocumentStatus = "processed" | "failed";
type DocumentIndexStatus = "not_indexed" | "indexed" | "failed";

type KnowledgeDocument = {
  id: string;
  filename: string;
  content_type: string;
  status: DocumentStatus;
  size_bytes: number;
  text_length: number;
  created_at: string;
  error_message?: string | null;
  index_status: DocumentIndexStatus;
  indexed_chunks: number;
  index_error_message?: string | null;
  is_enabled: boolean;
  knowledge_base_id: string;
  category: string;
};

type KnowledgeBase = {
  id: string;
  name: string;
  product_name: string;
  description: string;
  is_enabled: boolean;
  created_at: string;
};

type DashboardMetrics = {
  document_count: number;
  today_conversation_count: number;
  feedback_count: number;
  knowledge_gap_count: number;
  handoff_count: number;
};

type AdminEntry = Record<string, string | number | null>;

type ServicePolicy = {
  welcome_message: string;
  no_answer_message: string;
  handoff_message: string;
  handoff_keywords: string;
  sensitive_keywords: string;
  auto_handoff_on_no_answer: boolean;
  assistant_instructions: string;
};

const AUTH_STORAGE_KEY = "knowledge-agent-auth";

async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const stored = localStorage.getItem(AUTH_STORAGE_KEY);
  const headers = new Headers(init.headers);
  if (stored) {
    const session = JSON.parse(stored) as AuthSession;
    headers.set("Authorization", `Bearer ${session.accessToken}`);
  }
  return fetch(input, { ...init, headers });
}

const starterMessages: Message[] = [
  {
    id: "welcome",
    role: "assistant",
    content:
      "你好，我是企业知识库 AI 客服 Agent。当前阶段已经接入基础 RAG：上传文档后，我会先检索知识库，再基于命中的片段回答，并展示引用来源。"
  }
];

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function LoginPage({ onLogin }: { onLogin: (session: AuthSession) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail ?? "登录失败");
      const session: AuthSession = { accessToken: data.access_token, user: data.user };
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
      onLogin(session);
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="loginShell">
      <form className="loginCard" onSubmit={submit}>
        <div className="brandMark">EA</div>
        <h1>Knowledge Agent</h1>
        <p>登录后访问企业知识库客服工作台。</p>
        <label>用户名<input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" /></label>
        <label>密码<input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" /></label>
        {error && <div className="errorBox">{error}</div>}
        <button type="submit" disabled={loading}>{loading ? "登录中" : "登录"}</button>
        <small>请输入管理员提供的账号和密码。</small>
      </form>
    </main>
  );
}

function AdminPanel() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [feedback, setFeedback] = useState<AdminEntry[]>([]);
  const [gaps, setGaps] = useState<AdminEntry[]>([]);
  const [handoffs, setHandoffs] = useState<AdminEntry[]>([]);
  const [ragLogs, setRagLogs] = useState<AdminEntry[]>([]);
  const [toolLogs, setToolLogs] = useState<AdminEntry[]>([]);
  const [conversationRecords, setConversationRecords] = useState<ConversationSummary[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<{ title: string; messages: Message[] } | null>(null);
  const [policy, setPolicy] = useState<ServicePolicy | null>(null);
  const [policySaving, setPolicySaving] = useState(false);
  const [error, setError] = useState("");

  async function loadAdminData() {
    setError("");
    try {
      const responses = await Promise.all([
        apiFetch("/api/admin/dashboard"),
        apiFetch("/api/admin/feedback"),
        apiFetch("/api/admin/knowledge-gaps"),
        apiFetch("/api/admin/handoffs"),
        apiFetch("/api/rag/logs"),
        apiFetch("/api/customer-service/conversations"),
        apiFetch("/api/tools/logs"),
        apiFetch("/api/service-policy")
      ]);
      if (responses.some((response) => !response.ok)) throw new Error("管理后台数据加载失败");
      const [metricsData, feedbackData, gapData, handoffData, ragData, conversationData, toolData, policyData] = await Promise.all(
        responses.map((response) => response.json())
      );
      setMetrics(metricsData);
      setFeedback(feedbackData.feedback);
      setGaps(gapData.knowledge_gaps);
      setHandoffs(handoffData.handoffs);
      setRagLogs(ragData.logs);
      setConversationRecords(conversationData.conversations);
      setToolLogs(toolData.logs);
      setPolicy(policyData);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "管理后台数据加载失败");
    }
  }

  useEffect(() => {
    void loadAdminData();
  }, []);

  async function inspectConversation(conversation: ConversationSummary) {
    try {
      const response = await apiFetch(`/api/customer-service/conversations/${conversation.id}`);
      if (!response.ok) throw new Error("对话详情加载失败");
      const data = await response.json();
      setSelectedConversation({ title: conversation.title, messages: data.messages });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "对话详情加载失败");
    }
  }

  async function updateGapStatus(entry: AdminEntry) {
    const nextStatus = entry.status === "resolved" ? "open" : "resolved";
    const response = await apiFetch(`/api/admin/knowledge-gaps/${entry.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: nextStatus })
    });
    if (!response.ok) {
      setError("知识缺口状态更新失败");
      return;
    }
    setGaps((current) => current.map((item) => item.id === entry.id ? { ...item, status: nextStatus } : item));
  }

  async function savePolicy(event: FormEvent) {
    event.preventDefault();
    if (!policy || policySaving) return;
    setPolicySaving(true);
    try {
      const response = await apiFetch("/api/service-policy", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(policy)
      });
      if (!response.ok) throw new Error("客服策略保存失败");
      setPolicy(await response.json() as ServicePolicy);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "客服策略保存失败");
    } finally {
      setPolicySaving(false);
    }
  }

  const cards = metrics
    ? [
        ["文档", metrics.document_count],
        ["今日会话", metrics.today_conversation_count],
        ["用户反馈", metrics.feedback_count],
        ["知识缺口", metrics.knowledge_gap_count],
        ["转人工", metrics.handoff_count]
      ]
    : [];

  return (
    <section className="adminPanel">
      <header className="chatHeader">
        <div>
          <h1>管理后台</h1>
          <p>查看知识库客服运行指标、用户反馈、未解决问题和检索记录。</p>
        </div>
        <button className="adminRefresh" type="button" onClick={() => void loadAdminData()}>
          <RefreshCw size={16} />刷新数据
        </button>
      </header>
      <div className="adminContent">
        {error && <div className="errorBox">{error}</div>}
        <section className="metricGrid">
          {cards.map(([label, value]) => (
            <article className="metricCard" key={label}>
              <span>{label}</span><strong>{value}</strong>
            </article>
          ))}
        </section>
        {policy && <form className="servicePolicyForm" onSubmit={savePolicy}>
          <h2>客服策略与话术</h2>
          <label>欢迎语<textarea value={policy.welcome_message} onChange={(event) => setPolicy({ ...policy, welcome_message: event.target.value })} /></label>
          <label>无答案兜底语<textarea value={policy.no_answer_message} onChange={(event) => setPolicy({ ...policy, no_answer_message: event.target.value })} /></label>
          <label>转人工提示语<textarea value={policy.handoff_message} onChange={(event) => setPolicy({ ...policy, handoff_message: event.target.value })} /></label>
          <label>自动转人工关键词（英文逗号分隔）<input value={policy.handoff_keywords} onChange={(event) => setPolicy({ ...policy, handoff_keywords: event.target.value })} /></label>
          <label>敏感词（英文逗号分隔）<input value={policy.sensitive_keywords} onChange={(event) => setPolicy({ ...policy, sensitive_keywords: event.target.value })} /></label>
          <label className="policyCheckbox"><input type="checkbox" checked={policy.auto_handoff_on_no_answer} onChange={(event) => setPolicy({ ...policy, auto_handoff_on_no_answer: event.target.checked })} />知识库未命中时自动转人工</label>
          <label className="widePolicyField">模型补充规则<textarea value={policy.assistant_instructions} onChange={(event) => setPolicy({ ...policy, assistant_instructions: event.target.value })} /></label>
          <button type="submit" disabled={policySaving}>{policySaving ? "保存中" : "保存客服策略"}</button>
        </form>}
        <div className="adminGrid">
          <section className="adminList">
            <h2>对话记录<span>{conversationRecords.length}</span></h2>
            {conversationRecords.length === 0 ? <div className="emptyState">暂无对话记录</div> : conversationRecords.slice(0, 8).map((conversation) => (
              <button className="adminConversation" key={conversation.id} type="button" onClick={() => void inspectConversation(conversation)}>
                <strong>{conversation.title}</strong>
                <small>{conversation.message_count} 条消息</small>
              </button>
            ))}
          </section>
          <section className="adminList">
            <h2>知识缺口<span>{gaps.length}</span></h2>
            {gaps.length === 0 ? <div className="emptyState">暂无知识缺口</div> : gaps.slice(0, 8).map((entry, index) => (
              <article key={String(entry.id ?? index)}>
                <strong>{String(entry.question ?? "-")}</strong>
                <small>状态：{entry.status === "resolved" ? "已解决" : "待处理"}</small>
                <button className="gapAction" type="button" onClick={() => void updateGapStatus(entry)}>
                  {entry.status === "resolved" ? "重新打开" : "标记已解决"}
                </button>
              </article>
            ))}
          </section>
          <AdminList title="用户反馈" entries={feedback} primary="rating" secondary="conversation_id" empty="暂无反馈" />
          <AdminList title="转人工请求" entries={handoffs} primary="status" secondary="conversation_id" empty="暂无转人工请求" />
          <AdminList title="RAG 检索日志" entries={ragLogs} primary="query" secondary="source_count" empty="暂无检索日志" />
          <AdminList title="工具调用日志" entries={toolLogs} primary="tool_name" secondary="created_at" empty="暂无工具调用日志" />
        </div>
        {selectedConversation && (
          <section className="conversationInspector">
            <h2>{selectedConversation.title}</h2>
            {selectedConversation.messages.map((message) => (
              <article key={message.id}>
                <strong>{message.role === "user" ? "用户" : "AI"}</strong>
                <p>{message.content}</p>
                {message.sources && message.sources.length > 0 && (
                  <small>引用：{message.sources.slice(0, 2).map((source) => source.filename).join("、")}{message.sources.length > 2 ? ` 等 ${message.sources.length} 份文档` : ""}</small>
                )}
              </article>
            ))}
          </section>
        )}
      </div>
    </section>
  );
}

function AdminList({ title, entries, primary, secondary, empty }: { title: string; entries: AdminEntry[]; primary: string; secondary: string; empty: string }) {
  return (
    <section className="adminList">
      <h2>{title}<span>{entries.length}</span></h2>
      {entries.length === 0 ? <div className="emptyState">{empty}</div> : entries.slice(0, 8).map((entry, index) => (
        <article key={String(entry.id ?? index)}>
          <strong>{String(entry[primary] ?? "-")}</strong>
          <small>{secondary}: {String(entry[secondary] ?? "-")}</small>
        </article>
      ))}
    </section>
  );
}

function App() {
  const [session, setSession] = useState<AuthSession | null>(() => {
    const stored = localStorage.getItem(AUTH_STORAGE_KEY);
    return stored ? JSON.parse(stored) as AuthSession : null;
  });
  const [authChecked, setAuthChecked] = useState(false);
  const [view, setView] = useState<"chat" | "admin">("chat");
  const [messages, setMessages] = useState<Message[]>(starterMessages);
  const [welcomeMessage, setWelcomeMessage] = useState(starterMessages[0].content);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [activeKnowledgeBase, setActiveKnowledgeBase] = useState("default");
  const [documentCategory, setDocumentCategory] = useState("general");
  const [knowledgeBaseName, setKnowledgeBaseName] = useState("");
  const [productName, setProductName] = useState("");
  const [knowledgeBaseDescription, setKnowledgeBaseDescription] = useState("");
  const [editingKnowledgeBaseId, setEditingKnowledgeBaseId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isReindexing, setIsReindexing] = useState(false);
  const [reprocessingId, setReprocessingId] = useState<string | null>(null);
  const [documentError, setDocumentError] = useState("");
  const [preview, setPreview] = useState("");
  const [previewTitle, setPreviewTitle] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const history = useMemo(
    () =>
      messages
        .filter((message) => message.id !== "welcome")
        .map((message) => ({ role: message.role, content: message.content })),
    [messages]
  );

  async function loadDocuments() {
    setDocumentError("");
    try {
      const response = await apiFetch("/api/documents");
      if (!response.ok) throw new Error("文档列表加载失败");
      const data = (await response.json()) as { documents: KnowledgeDocument[] };
      setDocuments(data.documents);
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "文档列表加载失败");
    }
  }

  async function loadKnowledgeBases() {
    try {
      const response = await apiFetch("/api/knowledge-bases");
      if (!response.ok) throw new Error("知识库列表加载失败");
      const data = await response.json() as { knowledge_bases: KnowledgeBase[] };
      setKnowledgeBases(data.knowledge_bases);
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "知识库列表加载失败");
    }
  }

  async function loadConversations() {
    try {
      const response = await apiFetch("/api/customer-service/conversations");
      if (!response.ok) throw new Error("历史会话加载失败");
      const data = (await response.json()) as { conversations: ConversationSummary[] };
      setConversations(data.conversations);
    } catch {
      // History is secondary; document and chat errors remain independently visible.
    }
  }

  useEffect(() => {
    if (!session) {
      setAuthChecked(true);
      return;
    }
    void apiFetch("/api/auth/me").then((response) => {
      if (!response.ok) {
        localStorage.removeItem(AUTH_STORAGE_KEY);
        setSession(null);
      }
    }).finally(() => setAuthChecked(true));
    if (session.user.role === "admin") { void loadDocuments(); void loadKnowledgeBases(); }
    void loadConversations();
  }, [session]);

  useEffect(() => {
    if (!session) return;
    void apiFetch("/api/service-policy/public").then(async (response) => {
      if (!response.ok) return;
      const policy = await response.json() as Pick<ServicePolicy, "welcome_message">;
      setWelcomeMessage(policy.welcome_message);
      setMessages((current) => current.map((message) => message.id === "welcome" ? { ...message, content: policy.welcome_message } : message));
    });
  }, [session]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const question = input.trim();
    if (!question || isStreaming) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: question
    };
    const assistantId = crypto.randomUUID();

    setMessages((current) => [
      ...current,
      userMessage,
      { id: assistantId, role: "assistant", content: "", sources: [] }
    ]);
    setInput("");
    setIsStreaming(true);

    try {
      const response = await apiFetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // End users do not select a knowledge base; search spans all enabled bases.
        body: JSON.stringify({ message: question, history, conversation_id: conversationId })
      });

      if (!response.ok || !response.body) {
        throw new Error("聊天服务暂时不可用");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const eventText of events) {
          const line = eventText.split("\n").find((item) => item.startsWith("data: "));
          if (!line) continue;
          const eventData = JSON.parse(line.slice(6));
          if (eventData.type === "sources") {
            setConversationId(eventData.conversation_id);
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, sources: eventData.sources, serverMessageId: eventData.assistant_message_id }
                  : message
              )
            );
          }
          if (eventData.type === "done") {
            void loadConversations();
          }
          if (eventData.type === "delta") {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, content: message.content + eventData.content }
                  : message
              )
            );
          }
          if (eventData.type === "tool") {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId ? { ...message, toolName: eventData.tool_name } : message
              )
            );
          }
          if (eventData.type === "handoff") {
            setMessages((current) =>
              current.map((message) => message.id === assistantId ? { ...message, handoffRequested: true } : message)
            );
          }
          if (eventData.type === "error") {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId ? { ...message, content: eventData.message || "回答生成失败，请稍后重试。" } : message
              )
            );
            void loadConversations();
          }
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "聊天服务暂时不可用";
      setMessages((current) =>
        current.map((item) =>
          item.id === assistantId ? { ...item, content: `请求失败：${message}` } : item
        )
      );
    } finally {
      setIsStreaming(false);
    }
  }

  async function handleUpload(event: FormEvent) {
    event.preventDefault();
    if (!selectedFile || isUploading) return;

    setIsUploading(true);
    setDocumentError("");

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("knowledge_base_id", activeKnowledgeBase);
    formData.append("category", documentCategory);

    try {
      const response = await apiFetch("/api/documents", {
        method: "POST",
        body: formData
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail ?? "文档上传失败");
      }
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      await loadDocuments();
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "文档上传失败");
    } finally {
      setIsUploading(false);
    }
  }

  async function saveKnowledgeBase(event: FormEvent) {
    event.preventDefault();
    if (!knowledgeBaseName.trim() || !productName.trim()) return;
    setDocumentError("");
    try {
      const isEditing = editingKnowledgeBaseId !== null;
      const response = await apiFetch(isEditing ? `/api/knowledge-bases/${editingKnowledgeBaseId}` : "/api/knowledge-bases", {
        method: isEditing ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: knowledgeBaseName.trim(), product_name: productName.trim(), description: knowledgeBaseDescription.trim() })
      });
      if (!response.ok) throw new Error(isEditing ? "更新知识库失败" : "创建知识库失败");
      const saved = await response.json() as KnowledgeBase;
      setKnowledgeBases((current) => isEditing ? current.map((item) => item.id === saved.id ? saved : item) : [saved, ...current]);
      setActiveKnowledgeBase(saved.id);
      setKnowledgeBaseName("");
      setProductName("");
      setKnowledgeBaseDescription("");
      setEditingKnowledgeBaseId(null);
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "知识库保存失败");
    }
  }

  function startKnowledgeBaseEdit(item: KnowledgeBase) {
    setEditingKnowledgeBaseId(item.id);
    setKnowledgeBaseName(item.name);
    setProductName(item.product_name);
    setKnowledgeBaseDescription(item.description ?? "");
  }

  function cancelKnowledgeBaseEdit() {
    setEditingKnowledgeBaseId(null);
    setKnowledgeBaseName("");
    setProductName("");
    setKnowledgeBaseDescription("");
  }

  async function setKnowledgeBaseEnabled(item: KnowledgeBase) {
    setDocumentError("");
    try {
      const response = await apiFetch(`/api/knowledge-bases/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_enabled: !item.is_enabled })
      });
      if (!response.ok) throw new Error("更新知识库状态失败");
      const saved = await response.json() as KnowledgeBase;
      setKnowledgeBases((current) => current.map((entry) => entry.id === saved.id ? saved : entry));
      if (!saved.is_enabled && activeKnowledgeBase === saved.id) {
        const fallback = knowledgeBases.find((entry) => entry.id !== saved.id && entry.is_enabled);
        if (fallback) setActiveKnowledgeBase(fallback.id);
      }
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "更新知识库状态失败");
    }
  }

  async function deleteKnowledgeBase(item: KnowledgeBase) {
    if (item.id === "default" || !window.confirm(`确定删除知识库“${item.product_name} · ${item.name}”吗？其中存在文档时系统会阻止删除。`)) return;
    setDocumentError("");
    try {
      const response = await apiFetch(`/api/knowledge-bases/${item.id}`, { method: "DELETE" });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail ?? "删除知识库失败");
      }
      setKnowledgeBases((current) => current.filter((entry) => entry.id !== item.id));
      if (activeKnowledgeBase === item.id) setActiveKnowledgeBase("default");
      if (editingKnowledgeBaseId === item.id) cancelKnowledgeBaseEdit();
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "删除知识库失败");
    }
  }

  async function handlePreview(document: KnowledgeDocument) {
    setDocumentError("");
    try {
      const response = await apiFetch(`/api/documents/${document.id}/preview`);
      if (!response.ok) throw new Error("解析预览加载失败");
      const data = (await response.json()) as { preview: string };
      setPreviewTitle(document.filename);
      setPreview(data.preview || "这个文档没有解析出可预览文本。");
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "解析预览加载失败");
    }
  }

  async function handleDelete(document: KnowledgeDocument) {
    setDocumentError("");
    try {
      const response = await apiFetch(`/api/documents/${document.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error("文档删除失败");
      if (previewTitle === document.filename) {
        setPreview("");
        setPreviewTitle("");
      }
      await loadDocuments();
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "文档删除失败");
    }
  }

  async function handleReprocess(document: KnowledgeDocument) {
    if (reprocessingId) return;
    setReprocessingId(document.id);
    setDocumentError("");
    try {
      const response = await apiFetch(`/api/documents/${document.id}/reprocess`, { method: "POST" });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail ?? "文档重新解析失败");
      }
      await loadDocuments();
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "文档重新解析失败");
    } finally {
      setReprocessingId(null);
    }
  }

  async function toggleDocument(document: KnowledgeDocument) {
    setDocumentError("");
    try {
      const response = await apiFetch(`/api/documents/${document.id}/enabled`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_enabled: !document.is_enabled })
      });
      if (!response.ok) throw new Error("文档状态更新失败");
      const updated = await response.json();
      setDocuments((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "文档状态更新失败");
    }
  }

  async function handleReindex() {
    setIsReindexing(true);
    setDocumentError("");
    try {
      const response = await apiFetch("/api/rag/reindex", { method: "POST" });
      if (!response.ok) throw new Error("重新索引失败");
      await loadDocuments();
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "重新索引失败");
    } finally {
      setIsReindexing(false);
    }
  }

  function startNewConversation() {
    if (isStreaming) return;
    setMessages([{ ...starterMessages[0], content: welcomeMessage }]);
    setView("chat");
    setConversationId(null);
    setInput("");
  }

  async function openConversation(id: string) {
    if (isStreaming) return;
    try {
      const response = await apiFetch(`/api/customer-service/conversations/${id}`);
      if (!response.ok) throw new Error("历史会话加载失败");
      const data = await response.json();
      setConversationId(id);
      setMessages(
        data.messages.map((message: Message & { id: string }) => ({
          ...message,
          serverMessageId: message.role === "assistant" ? message.id : undefined
        }))
      );
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "历史会话加载失败");
    }
  }

  async function submitFeedback(message: Message, rating: "helpful" | "unhelpful") {
    if (!conversationId || !message.serverMessageId) return;
    try {
      const response = await apiFetch("/api/customer-service/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: conversationId,
          message_id: message.serverMessageId,
          rating
        })
      });
      if (!response.ok) throw new Error("反馈提交失败");
      setMessages((current) =>
        current.map((item) => (item.id === message.id ? { ...item, feedback: rating } : item))
      );
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "反馈提交失败");
    }
  }

  async function requestHandoff(message: Message) {
    if (!conversationId || !message.serverMessageId || message.handoffRequested) return;
    try {
      const response = await apiFetch("/api/customer-service/handoffs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conversation_id: conversationId, message_id: message.serverMessageId })
      });
      if (!response.ok) throw new Error("转人工请求提交失败");
      setMessages((current) =>
        current.map((item) =>
          item.id === message.id ? { ...item, handoffRequested: true } : item
        )
      );
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "转人工请求提交失败");
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
  }

  function logout() {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    setSession(null);
    setMessages([{ ...starterMessages[0], content: welcomeMessage }]);
    setConversationId(null);
    setConversations([]);
    setView("chat");
  }

  if (!authChecked) {
    return <main className="loginShell">正在验证登录状态…</main>;
  }

  if (!session) {
    return <LoginPage onLogin={(nextSession) => { setSession(nextSession); setAuthChecked(true); }} />;
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">EA</div>
          <div>
            <strong>Knowledge Agent</strong>
            <span>RAG 基础版</span>
          </div>
        </div>

        <button className="newChatButton" type="button" onClick={startNewConversation}>
          <MessageSquarePlus size={18} />
          新建会话
        </button>

        {session.user.role === "admin" && (
          <button className="newChatButton" type="button" onClick={() => setView("admin")}>
            <LayoutDashboard size={18} />
            管理后台
          </button>
        )}

        <div className="sessionUser">
          <span>{session.user.username} · {session.user.role === "admin" ? "管理员" : "用户"}</span>
          <button type="button" onClick={logout}>退出</button>
        </div>

        <section className="phasePanel" aria-label="当前阶段">
          <div className="phaseTitle">
            <CheckCircle2 size={16} />
            Phase 6
          </div>
          <p>已接入会话闭环、管理后台，以及订单查询和工单创建 Mock 工具。</p>
        </section>

        <section className="historyPanel" aria-label="历史会话">
          <div className="historyTitle"><History size={15} />历史会话</div>
          <div className="historyList">
            {conversations.length === 0 ? (
              <span className="historyEmpty">还没有历史会话</span>
            ) : conversations.map((conversation) => (
              <button
                className={conversation.id === conversationId ? "active" : ""}
                key={conversation.id}
                type="button"
                onClick={() => void openConversation(conversation.id)}
              >
                <strong>{conversation.title}</strong>
                <small>{conversation.message_count} 条消息</small>
              </button>
            ))}
          </div>
        </section>
      </aside>

      {view === "admin" && session.user.role === "admin" && <AdminPanel />}
      {view === "chat" && <section className="chatPanel">
        <header className="chatHeader">
          <div>
            <h1>企业知识库 AI 客服 Agent</h1>
            <p>上传企业文档后，系统会自动建立基础索引，并在回答中展示命中的知识来源。</p>
          </div>
          <div className="statusPill">Demo v0.6</div>
        </header>

        <div className="workspace">
          <section className="conversation" aria-label="聊天窗口">
            <div className="messages">
              {messages.map((message) => (
                <article className={`message ${message.role}`} key={message.id}>
                  <div className="avatar" aria-hidden="true">
                    {message.role === "assistant" ? <Bot size={18} /> : <User size={18} />}
                  </div>
                  <div className="bubble">
                    <p>{message.content || "正在检索知识库并生成回复..."}</p>
                    {message.toolName && <div className="toolBadge">工具调用：{message.toolName}</div>}
                    {message.role === "assistant" && message.sources && message.sources.length > 0 && (
                      <div className="sourceList">
                        <div className="sourceTitle">
                          <Database size={15} />
                          引用来源（{message.sources.length}）
                        </div>
                        {message.sources.slice(0, 2).map((source) => (
                          <div className="sourceItem" key={source.chunk_id}>
                            <strong>{source.filename}</strong>
                            {source.page_number && <span>第 {source.page_number} 页</span>}
                          </div>
                        ))}
                        {message.sources.length > 2 && <small className="moreSources">另有 {message.sources.length - 2} 个命中来源未展开</small>}
                      </div>
                    )}
                    {message.role === "assistant" && message.content && message.serverMessageId && (
                      <div className="feedback">
                        <button
                          className={message.feedback === "helpful" ? "selected" : ""}
                          type="button"
                          title="有帮助"
                          onClick={() => void submitFeedback(message, "helpful")}
                        >
                          <ThumbsUp size={15} />
                        </button>
                        <button
                          className={message.feedback === "unhelpful" ? "selected" : ""}
                          type="button"
                          title="没帮助"
                          onClick={() => void submitFeedback(message, "unhelpful")}
                        >
                          <ThumbsDown size={15} />
                        </button>
                        {message.sources?.length === 0 && !message.toolName && (
                          <button className="handoffButton" type="button" onClick={() => void requestHandoff(message)}>
                            <Headphones size={15} />
                            {message.handoffRequested ? "已申请人工" : "转人工"}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </article>
              ))}
            </div>

            <form className="composer" onSubmit={handleSubmit}>
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void handleSubmit(event);
                  }
                }}
                placeholder="输入一个客服问题，例如：7 天内可以退款吗？"
                rows={2}
              />
              <button type="submit" disabled={isStreaming || !input.trim()} title="发送">
                <Send size={20} />
              </button>
            </form>
          </section>

          {session.user.role === "admin" && <aside className="knowledgePanel" aria-label="知识库管理">
            <div className="panelHeader">
              <div>
                <h2>知识库</h2>
                <p>上传 PDF、图片、TXT、Markdown、CSV、Word 或 Excel。解析后自动清洗、切片并写入 Chroma。</p>
              </div>
              <div className="panelActions">
                <button className="iconButton" type="button" onClick={() => void loadDocuments()} title="刷新">
                  <RefreshCw size={18} />
                </button>
                <button
                  className="iconButton"
                  type="button"
                  onClick={() => void handleReindex()}
                  disabled={isReindexing}
                  title="重建索引"
                >
                  <Database size={18} />
                </button>
              </div>
            </div>

            <form className="knowledgeBaseForm" onSubmit={saveKnowledgeBase}>
              <input value={productName} onChange={(event) => setProductName(event.target.value)} placeholder="产品名称" />
              <input value={knowledgeBaseName} onChange={(event) => setKnowledgeBaseName(event.target.value)} placeholder="知识库名称，例如：售后资料" />
              <input value={knowledgeBaseDescription} onChange={(event) => setKnowledgeBaseDescription(event.target.value)} placeholder="说明（可选），例如：退换货、保修与维修政策" />
              <div className="knowledgeBaseFormActions">
                <button type="submit" disabled={!productName.trim() || !knowledgeBaseName.trim()}>{editingKnowledgeBaseId ? "保存知识库" : "新增知识库"}</button>
                {editingKnowledgeBaseId && <button type="button" className="secondaryAction" onClick={cancelKnowledgeBaseEdit}>取消编辑</button>}
              </div>
            </form>

            <div className="documentList">
              {knowledgeBases.map((item) => {
                const documentCount = documents.filter((document) => document.knowledge_base_id === item.id).length;
                return <article className="documentItem knowledgeBaseItem" key={item.id}>
                  <div className="documentBody">
                    <strong>{item.product_name} · {item.name}</strong>
                    {item.description && <small>{item.description}</small>}
                    <small>{item.is_enabled ? "检索已启用" : "检索已停用"} · {documentCount} 份文档</small>
                    <div className="documentActions">
                      <button type="button" onClick={() => void setKnowledgeBaseEnabled(item)}>{item.is_enabled ? "停用知识库" : "启用知识库"}</button>
                      <button type="button" className="secondaryAction" onClick={() => startKnowledgeBaseEdit(item)}>编辑</button>
                      {item.id !== "default" && <button type="button" className="dangerAction" onClick={() => void deleteKnowledgeBase(item)}>删除</button>}
                    </div>
                  </div>
                </article>;
              })}
            </div>

            <form className="uploadBox" onSubmit={handleUpload}>
              <select value={activeKnowledgeBase} onChange={(event) => setActiveKnowledgeBase(event.target.value)} aria-label="上传知识库">
                {knowledgeBases.filter((item) => item.is_enabled).map((item) => <option key={item.id} value={item.id}>{item.product_name} · {item.name}</option>)}
              </select>
              <input value={documentCategory} onChange={(event) => setDocumentCategory(event.target.value)} placeholder="分类：售前/售后/原料/证书" />
              <label>
                <Upload size={18} />
                <span>{selectedFile ? selectedFile.name : "选择文档"}</span>
                <input
                  accept=".pdf,.txt,.md,.markdown,.csv,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff,.docx,.xlsx,.xls"
                  ref={fileInputRef}
                  type="file"
                  onChange={handleFileChange}
                />
              </label>
              <button type="submit" disabled={!selectedFile || isUploading}>
                {isUploading ? "上传中" : "上传解析"}
              </button>
            </form>

            {documentError && <div className="errorBox">{documentError}</div>}

            <div className="documentList">
              {documents.length === 0 ? (
                <div className="emptyState">还没有文档。先上传一份售后政策、FAQ 或产品说明。</div>
              ) : (
                documents.map((document) => (
                  <article className="documentItem" key={document.id}>
                    <div className="documentIcon">
                      <FileText size={18} />
                    </div>
                    <div className="documentBody">
                      <strong>{document.filename}</strong>
                      <span>
                        {formatFileSize(document.size_bytes)} · 解析文本 {document.text_length} 字
                      </span>
                      <span className={`retrievalStatus ${document.is_enabled ? "enabled" : "disabled"}`}>
                        {document.is_enabled ? "检索已启用" : "检索已停用"}
                      </span>
                      <span className={`docStatus ${document.status}`}>
                        {document.status === "processed"
                          ? document.index_status === "indexed"
                            ? `已索引 ${document.indexed_chunks} 个片段`
                            : document.index_status === "failed"
                              ? "索引失败"
                              : "待索引"
                          : "解析失败"}
                      </span>
                      {document.error_message && <small>{document.error_message}</small>}
                      {document.index_error_message && <small>{document.index_error_message}</small>}
                      <div className="documentActions">
                        {document.status === "failed" && (
                          <button disabled={reprocessingId !== null} type="button" onClick={() => void handleReprocess(document)}>
                            {reprocessingId === document.id ? "OCR 解析中" : "OCR 重试"}
                          </button>
                        )}
                        <button type="button" onClick={() => void toggleDocument(document)}>
                          {document.is_enabled ? "停用检索" : "启用检索"}
                        </button>
                        <button type="button" onClick={() => void handlePreview(document)}>
                          查看解析
                        </button>
                        <button type="button" onClick={() => void handleDelete(document)} title="删除">
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                  </article>
                ))
              )}
            </div>

            {previewTitle && (
              <section className="previewBox">
                <div className="previewTitle">{previewTitle}</div>
                <pre>{preview}</pre>
              </section>
            )}
          </aside>}
        </div>
      </section>}
    </main>
  );
}

export default App;
