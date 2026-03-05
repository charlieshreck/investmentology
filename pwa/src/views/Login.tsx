import { useState, type FormEvent } from "react";

interface LoginProps {
  onLogin: (password: string, email: string) => Promise<boolean>;
  onRegister: (email: string, password: string, displayName?: string) => Promise<boolean>;
  error: string | null;
}

export function Login({ onLogin, onRegister, error }: LoginProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!password.trim() || !email.trim() || submitting) return;
    setSubmitting(true);
    if (mode === "register") {
      await onRegister(email, password, displayName);
    } else {
      await onLogin(password, email);
    }
    setSubmitting(false);
  };

  const inputStyle = {
    width: "100%",
    padding: "var(--space-lg)",
    background: "var(--color-surface-1)",
    border: "1px solid var(--glass-border)",
    borderRadius: "var(--radius-sm)",
    color: "var(--color-text)",
    fontFamily: "var(--font-sans)",
    fontSize: "var(--text-base)" as const,
    outline: "none",
    marginBottom: "var(--space-md)",
  };

  const canSubmit = password.trim() && email.trim();

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
      <div style={{ width: "100%", maxWidth: 360, padding: "var(--space-xl)" }}>
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
            {mode === "login" ? "Sign in to continue" : "Create your account"}
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Email field (always shown but optional for legacy login) */}
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoFocus
            style={inputStyle}
          />

          {mode === "register" && (
            <input
              type="text"
              placeholder="Display name (optional)"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              style={inputStyle}
            />
          )}

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ ...inputStyle, marginBottom: "var(--space-lg)" }}
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
            disabled={!canSubmit || submitting}
            style={{
              width: "100%",
              padding: "var(--space-lg)",
              background: canSubmit && !submitting ? "var(--gradient-active)" : "var(--color-surface-2)",
              border: "none",
              borderRadius: "var(--radius-sm)",
              color: canSubmit && !submitting ? "#fff" : "var(--color-text-muted)",
              fontSize: "var(--text-base)",
              fontWeight: 600,
              cursor: canSubmit && !submitting ? "pointer" : "not-allowed",
            }}
          >
            {submitting
              ? (mode === "login" ? "Signing in..." : "Creating account...")
              : (mode === "login" ? "Sign In" : "Create Account")}
          </button>
        </form>

        <div style={{ textAlign: "center", marginTop: "var(--space-lg)" }}>
          <button
            onClick={() => setMode(mode === "login" ? "register" : "login")}
            style={{
              background: "none",
              border: "none",
              color: "var(--color-accent-bright)",
              fontSize: "var(--text-sm)",
              cursor: "pointer",
              textDecoration: "underline",
            }}
          >
            {mode === "login" ? "Create an account" : "Already have an account? Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}
