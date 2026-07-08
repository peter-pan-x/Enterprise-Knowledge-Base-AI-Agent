import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  CheckCircle2,
  Database,
  FileText,
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
};

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

function App() {
  const [messages, setMessages] = useState<Message[]>(starterMessages);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isReindexing, setIsReindexing] = useState(false);
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
      const response = await fetch("/api/documents");
      if (!response.ok) throw new Error("文档列表加载失败");
      const data = (await response.json()) as { documents: KnowledgeDocument[] };
      setDocuments(data.documents);
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "文档列表加载失败");
    }
  }

  useEffect(() => {
    void loadDocuments();
  }, []);

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
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: question, history })
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
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId ? { ...message, sources: eventData.sources } : message
              )
            );
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

    try {
      const response = await fetch("/api/documents", {
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

  async function handlePreview(document: KnowledgeDocument) {
    setDocumentError("");
    try {
      const response = await fetch(`/api/documents/${document.id}/preview`);
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
      const response = await fetch(`/api/documents/${document.id}`, { method: "DELETE" });
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

  async function handleReindex() {
    setIsReindexing(true);
    setDocumentError("");
    try {
      const response = await fetch("/api/rag/reindex", { method: "POST" });
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
    setMessages(starterMessages);
    setInput("");
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
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

        <section className="phasePanel" aria-label="当前阶段">
          <div className="phaseTitle">
            <CheckCircle2 size={16} />
            Phase 3
          </div>
          <p>当前阶段完成基础 RAG 闭环：切片、Embedding、Chroma 检索、基于文档回答、引用来源和无依据拒答。</p>
        </section>
      </aside>

      <section className="chatPanel">
        <header className="chatHeader">
          <div>
            <h1>企业知识库 AI 客服 Agent</h1>
            <p>上传企业文档后，系统会自动建立基础索引，并在回答中展示命中的知识来源。</p>
          </div>
          <div className="statusPill">Demo v0.3</div>
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
                    {message.role === "assistant" && message.sources && message.sources.length > 0 && (
                      <div className="sourceList">
                        <div className="sourceTitle">
                          <Database size={15} />
                          引用来源
                        </div>
                        {message.sources.map((source) => (
                          <div className="sourceItem" key={source.chunk_id}>
                            <strong>{source.filename}</strong>
                            <span>
                              片段 {source.chunk_index + 1}
                              {source.page_number ? ` · 第 ${source.page_number} 页` : ""} · 相似度{" "}
                              {(source.score * 100).toFixed(0)}%
                            </span>
                            <small>{source.preview}</small>
                          </div>
                        ))}
                      </div>
                    )}
                    {message.role === "assistant" && message.content && (
                      <div className="feedback">
                        <button type="button" title="有帮助">
                          <ThumbsUp size={15} />
                        </button>
                        <button type="button" title="没帮助">
                          <ThumbsDown size={15} />
                        </button>
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

          <aside className="knowledgePanel" aria-label="知识库管理">
            <div className="panelHeader">
              <div>
                <h2>知识库</h2>
                <p>上传 PDF、TXT 或 Markdown。解析成功后会自动切片、向量化并写入 Chroma。</p>
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

            <form className="uploadBox" onSubmit={handleUpload}>
              <label>
                <Upload size={18} />
                <span>{selectedFile ? selectedFile.name : "选择文档"}</span>
                <input
                  accept=".pdf,.txt,.md,.markdown"
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
                      <span className={`docStatus ${document.status}`}>
                        {document.status === "processed"
                          ? document.index_status === "indexed"
                            ? `已索引 ${document.indexed_chunks} 个片段`
                            : "待索引"
                          : "解析失败"}
                      </span>
                      {document.error_message && <small>{document.error_message}</small>}
                      {document.index_error_message && <small>{document.index_error_message}</small>}
                      <div className="documentActions">
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
          </aside>
        </div>
      </section>
    </main>
  );
}

export default App;
