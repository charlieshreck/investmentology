import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Bot, User, Zap } from "lucide-react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { apiFetch } from "../utils/apiClient";

interface Message {
  role: "user" | "assistant";
  content: string;
  latency?: number;
  contextKeys?: string[];
}

export function Assistant() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { role: "user", content: text };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await apiFetch<{ reply: string; context_keys: string[]; latency_ms: number }>(
        "/api/invest/assistant/chat",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            history: messages.slice(-10).map(m => ({ role: m.role, content: m.content })),
          }),
        },
      );
      setMessages(prev => [...prev, {
        role: "assistant",
        content: res.reply,
        latency: res.latency_ms,
        contextKeys: res.context_keys,
      }]);
    } catch (e: any) {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: `Error: ${e.message}`,
      }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const suggestions = [
    "What should I be worried about?",
    "How's my portfolio doing?",
    "What's the strongest buy right now?",
    "How much cash should I hold?",
  ];

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <ViewHeader
        title="Assistant"
        right={
          <div style={{
            display: "flex", alignItems: "center", gap: 4,
            fontSize: 9, fontWeight: 700, textTransform: "uppercase",
            letterSpacing: "0.06em", color: "var(--color-text-muted)",
          }}>
            <Zap size={10} />
            Fast AI
          </div>
        }
      />

      {/* Messages */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "var(--space-md)",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-md)",
        }}
      >
        {messages.length === 0 && (
          <div style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "var(--space-lg)",
            padding: "var(--space-xl)",
          }}>
            <div style={{
              width: 48, height: 48, borderRadius: "50%",
              background: "rgba(99, 102, 241, 0.12)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Bot size={24} color="var(--color-accent-bright)" />
            </div>
            <div style={{
              textAlign: "center",
              color: "var(--color-text-muted)",
              fontSize: "var(--text-sm)",
              lineHeight: 1.6,
              maxWidth: 280,
            }}>
              Ask me anything about your portfolio, positions, recommendations, or market conditions.
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, width: "100%", maxWidth: 320 }}>
              {suggestions.map(s => (
                <button
                  key={s}
                  onClick={() => { setInput(s); inputRef.current?.focus(); }}
                  style={{
                    padding: "8px 12px",
                    background: "var(--color-surface-1)",
                    border: "1px solid var(--glass-border)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--color-text-secondary)",
                    fontSize: "var(--text-xs)",
                    textAlign: "left",
                    cursor: "pointer",
                    transition: "border-color 0.2s",
                  }}
                  onMouseEnter={e => (e.currentTarget.style.borderColor = "var(--color-accent)")}
                  onMouseLeave={e => (e.currentTarget.style.borderColor = "var(--glass-border)")}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        <AnimatePresence>
          {messages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              style={{
                display: "flex",
                gap: 10,
                alignItems: "flex-start",
              }}
            >
              <div style={{
                width: 28, height: 28, borderRadius: "50%",
                background: msg.role === "user"
                  ? "rgba(99, 102, 241, 0.12)"
                  : "rgba(52, 211, 153, 0.12)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                marginTop: 2,
              }}>
                {msg.role === "user"
                  ? <User size={14} color="var(--color-accent-bright)" />
                  : <Bot size={14} color="var(--color-success)" />
                }
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: "var(--text-sm)",
                  lineHeight: 1.6,
                  color: "var(--color-text)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}>
                  {msg.content}
                </div>
                {msg.latency && (
                  <div style={{
                    fontSize: 9,
                    color: "var(--color-text-muted)",
                    marginTop: 4,
                    fontFamily: "var(--font-mono)",
                  }}>
                    {(msg.latency / 1000).toFixed(1)}s
                    {msg.contextKeys && msg.contextKeys.length > 0 && (
                      <> · {msg.contextKeys.join(", ")}</>
                    )}
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {loading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{ display: "flex", gap: 10, alignItems: "center" }}
          >
            <div style={{
              width: 28, height: 28, borderRadius: "50%",
              background: "rgba(52, 211, 153, 0.12)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Bot size={14} color="var(--color-success)" />
            </div>
            <div style={{
              display: "flex", gap: 4,
              color: "var(--color-text-muted)",
              fontSize: "var(--text-xs)",
            }}>
              <span style={{ animation: "pulse-glow 1.5s ease-in-out infinite" }}>Thinking</span>
              <span style={{ animation: "pulse-glow 1.5s ease-in-out infinite 0.2s" }}>.</span>
              <span style={{ animation: "pulse-glow 1.5s ease-in-out infinite 0.4s" }}>.</span>
              <span style={{ animation: "pulse-glow 1.5s ease-in-out infinite 0.6s" }}>.</span>
            </div>
          </motion.div>
        )}
      </div>

      {/* Input */}
      <div style={{
        padding: "var(--space-sm) var(--space-md)",
        paddingBottom: "calc(var(--nav-height) + var(--safe-bottom) + var(--space-sm))",
        borderTop: "1px solid var(--glass-border)",
        background: "var(--color-surface-0)",
      }}>
        <div style={{
          display: "flex",
          gap: 8,
          alignItems: "flex-end",
          background: "var(--color-surface-1)",
          borderRadius: "var(--radius-md)",
          border: "1px solid var(--glass-border)",
          padding: "8px 12px",
        }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your portfolio..."
            rows={1}
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              outline: "none",
              color: "var(--color-text)",
              fontSize: "var(--text-sm)",
              fontFamily: "inherit",
              resize: "none",
              lineHeight: 1.5,
              maxHeight: 120,
              overflow: "auto",
            }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            style={{
              width: 32, height: 32,
              borderRadius: "50%",
              border: "none",
              background: input.trim() && !loading
                ? "var(--color-accent)"
                : "var(--color-surface-2)",
              color: input.trim() && !loading
                ? "#fff"
                : "var(--color-text-muted)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: input.trim() && !loading ? "pointer" : "not-allowed",
              flexShrink: 0,
              transition: "background 0.2s",
            }}
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
