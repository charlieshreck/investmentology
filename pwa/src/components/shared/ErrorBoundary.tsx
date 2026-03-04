import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  viewName?: string;
  onError?: (error: Error, info: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/** App-level boundary — shows reload button. */
export class AppErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[AppErrorBoundary]", error, info);
    this.props.onError?.(error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          height: "100%", display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", gap: 12,
          background: "var(--color-base)", color: "var(--color-text)",
          padding: 24, textAlign: "center",
        }}>
          <span style={{ fontSize: 14, fontWeight: 600 }}>Something went wrong</span>
          <span style={{ fontSize: 12, color: "var(--color-text-muted)", maxWidth: 320 }}>
            {this.state.error?.message}
          </span>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: 8, padding: "8px 20px", borderRadius: 8,
              background: "var(--color-accent)", color: "#fff",
              border: "none", fontSize: 13, fontWeight: 600, cursor: "pointer",
            }}
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

/** View-level boundary — shows retry button without full reload. */
export class ViewErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[ViewErrorBoundary:${this.props.viewName ?? "unknown"}]`, error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          height: "100%", display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", gap: 10,
          color: "var(--color-text)", padding: 24, textAlign: "center",
        }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>
            {this.props.viewName ? `${this.props.viewName} failed to load` : "View failed to load"}
          </span>
          <span style={{ fontSize: 11, color: "var(--color-text-muted)", maxWidth: 300 }}>
            {this.state.error?.message}
          </span>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              marginTop: 6, padding: "6px 16px", borderRadius: 6,
              background: "var(--color-surface)", color: "var(--color-text)",
              border: "1px solid var(--color-border)", fontSize: 12,
              fontWeight: 500, cursor: "pointer",
            }}
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

/** Overlay-level boundary — closes overlay on error. */
export class OverlayErrorBoundary extends Component<Props & { onClose?: () => void }, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[OverlayErrorBoundary]", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: 24, textAlign: "center",
          color: "var(--color-text)", display: "flex",
          flexDirection: "column", alignItems: "center", gap: 10,
        }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>Failed to load stock details</span>
          <span style={{ fontSize: 11, color: "var(--color-text-muted)", maxWidth: 300 }}>
            {this.state.error?.message}
          </span>
          <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              style={{
                padding: "6px 16px", borderRadius: 6,
                background: "var(--color-surface)", color: "var(--color-text)",
                border: "1px solid var(--color-border)", fontSize: 12,
                fontWeight: 500, cursor: "pointer",
              }}
            >
              Retry
            </button>
            <button
              onClick={() => this.props.onClose?.()}
              style={{
                padding: "6px 16px", borderRadius: 6,
                background: "transparent", color: "var(--color-text-muted)",
                border: "1px solid var(--color-border)", fontSize: 12,
                fontWeight: 500, cursor: "pointer",
              }}
            >
              Close
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
