import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  apiRequest,
  AuthTokenResponse,
  loadAccessToken,
  saveAccessToken,
  UserProfile,
} from "@/api/client";

interface AuthContextValue {
  user: UserProfile | null;
  personas: UserProfile[];
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  switchDevPersona: (personaKey: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [personas, setPersonas] = useState<UserProfile[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const switchDevPersona = useCallback(
    async (personaKey: string) => {
      setError(null);
      const data = await apiRequest<AuthTokenResponse>("/auth/dev-switch-role", {
        method: "POST",
        body: JSON.stringify({ persona_key: personaKey }),
      });
      await saveAccessToken(data.access_token);
      setUser(data.user);
      await queryClient.invalidateQueries();
    },
    [queryClient]
  );

  const login = useCallback(
    async (email: string, password: string) => {
      setError(null);
      const data = await apiRequest<AuthTokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      await saveAccessToken(data.access_token);
      setUser(data.user);
      await queryClient.invalidateQueries();
    },
    [queryClient]
  );

  const logout = useCallback(async () => {
    await saveAccessToken(null);
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        if (__DEV__) {
          const devList = await apiRequest<UserProfile[]>(
            "/auth/dev-personas"
          ).catch(() => []);
          if (active) setPersonas(devList);
        }

        const existingToken = await loadAccessToken();
        if (existingToken) {
          const me = await apiRequest<UserProfile>("/auth/me");
          if (active) setUser(me);
        } else if (__DEV__) {
          await switchDevPersona("junior_employee");
        }
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to reach ExpenseIt backend."
          );
        }
      } finally {
        if (active) setIsLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [switchDevPersona]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      personas,
      isLoading,
      error,
      login,
      switchDevPersona,
      logout,
    }),
    [user, personas, isLoading, error, login, switchDevPersona, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
