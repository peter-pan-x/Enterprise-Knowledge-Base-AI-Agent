import { FormEvent, useMemo, useState } from "react";
import { Bot, CheckCircle2, MessageSquarePlus, Send, ThumbsDown, ThumbsUp, User } from "lucide-react";

type Role = "user" | "assistant";

type Message = {
  id: string;
  role: Role;
  content: string;
};

const starterMessages: Message[] = [
  {
    id: "welcome",
    role: "assistant",
    content:
      "你好，我是企业知识库 AI 客服 Agent 的基础版本。当前阶段先打通聊天链路，后续会逐步接入文档上传、RAG 检索、引用来源和工具调用。"
  }
];

function App() {
  const [messages, setMessages] = useState<Message[]>(starterMessages);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);

  const history = useMemo(
    () =>
      messages
        .filter((message) => message.id !== "welcome")
        .map((message) => ({ role: message.role, content: message.content })),
    [messages]
  );

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
      { id: assistantId, role: "assistant", content: "" }
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

  function startNewConversation() {
    if (isStreaming) return;
    setMessages(starterMessages);
    setInput("");
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">EA</div>
          <div>
            <strong>Knowledge Agent</strong>
            <span>基础聊天版本</span>
          </div>
        </div>

        <button className="newChatButton" type="button" onClick={startNewConversation}>
          <MessageSquarePlus size={18} />
          新建会话
        </button>

        <section className="phasePanel" aria-label="当前阶段">
          <div className="phaseTitle">
            <CheckCircle2 size={16} />
            Phase 1
          </div>
          <p>先打通前后端聊天链路，再逐步接入文档上传、RAG 和工具调用。</p>
        </section>
      </aside>

      <section className="chatPanel">
        <header className="chatHeader">
          <div>
            <h1>企业知识库 AI 客服 Agent</h1>
            <p>当前版本用于验证基础聊天流程，RAG 能力将在下一阶段加入。</p>
          </div>
          <div className="statusPill">Demo v0.1</div>
        </header>

        <div className="messages">
          {messages.map((message) => (
            <article className={`message ${message.role}`} key={message.id}>
              <div className="avatar" aria-hidden="true">
                {message.role === "assistant" ? <Bot size={18} /> : <User size={18} />}
              </div>
              <div className="bubble">
                <p>{message.content || "正在生成回复..."}</p>
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
            placeholder="输入一个客服问题，先验证基础聊天链路..."
            rows={2}
          />
          <button type="submit" disabled={isStreaming || !input.trim()} title="发送">
            <Send size={20} />
          </button>
        </form>
      </section>
    </main>
  );
}

export default App;
