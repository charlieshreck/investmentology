import { useState, type FormEvent } from "react";

interface LoginProps {
  onLogin: (password: string) => Promise<boolean>;
  error: string | null;
}

export function Login({ onLogin, error }: LoginProps) {
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!password.trim() || submitting) return;
    setSubmitting(true);
    await onLogin(password);
    setSubmitting(false);
  };

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--color-base)",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 360,
          padding: "var(--space-xl)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "var(--space-2xl)" }}>
          <div
            style={{
              fontSize: "var(--text-2xl)",
              fontWeight: 700,
              background: "var(--gradient-active)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              marginBottom: "var(--space-md)",
            }}
          >
            Investmentology
          </div>
          <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
            Sign in to continue
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoFocus
            style={{
              width: "100%",
              padding: "var(--space-lg)",
              background: "var(--color-surface-1)",
              border: "1px solid var(--glass-border)",
              borderRadius: "var(--radius-sm)",
              color: "var(--color-text)",
              fontFamily: "var(--font-sans)",
              fontSize: "var(--text-base)",
              outline: "none",
              marginBottom: "var(--space-lg)",
            }}
          />

          {error && (
            <div
              style={{
                color: "var(--color-error)",
                fontSize: "var(--text-sm)",
                textAlign: "center",
                marginBottom: "var(--space-lg)",
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={!password.trim() || submitting}
            style={{
              width: "100%",
              padding: "var(--space-lg)",
              background: password.trim() && !submitting ? "var(--gradient-active)" : "var(--color-surface-2)",
              border: "none",
              borderRadius: "var(--radius-sm)",
              color: password.trim() && !submitting ? "#fff" : "var(--color-text-muted)",
              fontSize: "var(--text-base)",
              fontWeight: 600,
              cursor: password.trim() && !submitting ? "pointer" : "not-allowed",
            }}
          >
            {submitting ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
