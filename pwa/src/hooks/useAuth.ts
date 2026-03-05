import { useState, useCallback, useEffect } from "react";

interface AuthState {
  isAuthenticated: boolean | null; // null = checking
  userId: number | null;
  error: string | null;
  login: (password: string, email?: string) => Promise<boolean>;
  register: (email: string, password: string, displayName?: string) => Promise<boolean>;
  logout: () => Promise<void>;
}

export function useAuth(): AuthState {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [userId, setUserId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Check auth on mount
  useEffect(() => {
    fetch("/api/invest/auth/check")
      .then((r) => r.json())
      .then((data) => {
        setIsAuthenticated(data.authenticated === true);
        setUserId(data.userId ?? null);
      })
      .catch(() => setIsAuthenticated(false));
  }, []);

  const login = useCallback(async (password: string, email?: string): Promise<boolean> => {
    setError(null);
    try {
      const body: Record<string, string> = { password };
      if (email) body.email = email;
      const res = await fetch("/api/invest/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (data.ok) {
        setIsAuthenticated(true);
        setUserId(data.userId ?? null);
        return true;
      }
      setError(data.error || "Login failed");
      return false;
    } catch {
      setError("Network error");
      return false;
    }
  }, []);

  const register = useCallback(async (email: string, password: string, displayName?: string): Promise<boolean> => {
    setError(null);
    try {
      const res = await fetch("/api/invest/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, display_name: displayName || "" }),
      });
      const data = await res.json();
      if (data.ok) {
        setIsAuthenticated(true);
        setUserId(data.userId ?? null);
        return true;
      }
      setError(data.error || "Registration failed");
      return false;
    } catch {
      setError("Network error");
      return false;
    }
  }, []);

  const logout = useCallback(async () => {
    await fetch("/api/invest/auth/logout", { method: "POST" });
    setIsAuthenticated(false);
    setUserId(null);
  }, []);

  return { isAuthenticated, userId, error, login, register, logout };
}
