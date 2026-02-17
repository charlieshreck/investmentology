import { useState, useCallback, useEffect } from "react";

interface AuthState {
  isAuthenticated: boolean | null; // null = checking
  error: string | null;
  login: (password: string) => Promise<boolean>;
  logout: () => Promise<void>;
}

export function useAuth(): AuthState {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Check auth on mount
  useEffect(() => {
    fetch("/api/invest/auth/check")
      .then((r) => r.json())
      .then((data) => setIsAuthenticated(data.authenticated === true))
      .catch(() => setIsAuthenticated(false));
  }, []);

  const login = useCallback(async (password: string): Promise<boolean> => {
    setError(null);
    try {
      const res = await fetch("/api/invest/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (data.ok) {
        setIsAuthenticated(true);
        return true;
      }
      setError(data.error || "Login failed");
      return false;
    } catch {
      setError("Network error");
      return false;
    }
  }, []);

  const logout = useCallback(async () => {
    await fetch("/api/invest/auth/logout", { method: "POST" });
    setIsAuthenticated(false);
  }, []);

  return { isAuthenticated, error, login, logout };
}
