import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

import type { components } from "./generated";

export type UserProfile = components["schemas"]["UserProfile"];
export type AuthTokenResponse = components["schemas"]["AuthTokenResponse"];
export type ExpenseClaim = components["schemas"]["ExpenseClaim"];
export type ExtractedReceipt = components["schemas"]["ExtractedReceipt"];
export type MonthlyQuotaSummary = components["schemas"]["MonthlyQuotaSummary"];
export type NotificationItem = components["schemas"]["NotificationItem"];
export type PolicyLimitsResponse = components["schemas"]["PolicyLimitsResponse"];
export type MockPreset = components["schemas"]["MockScanRequest"]["preset"];

const TOKEN_KEY = "expenseit_jwt_token";

export const API_BASE_URL = (
  process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

let memoryToken: string | null = null;

export async function saveAccessToken(token: string | null): Promise<void> {
  memoryToken = token;
  if (Platform.OS === "web") {
    if (typeof window !== "undefined") {
      if (token) window.localStorage.setItem(TOKEN_KEY, token);
      else window.localStorage.removeItem(TOKEN_KEY);
    }
    return;
  }
  if (token) {
    await SecureStore.setItemAsync(TOKEN_KEY, token);
  } else {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
  }
}

export async function loadAccessToken(): Promise<string | null> {
  if (memoryToken) return memoryToken;
  if (Platform.OS === "web") {
    if (typeof window !== "undefined") {
      memoryToken = window.localStorage.getItem(TOKEN_KEY);
    }
    return memoryToken;
  }
  memoryToken = await SecureStore.getItemAsync(TOKEN_KEY);
  return memoryToken;
}

export function createIdempotencyKey(prefix = "req"): string {
  const rand = Math.random().toString(36).slice(2, 10);
  return `${prefix}-${Date.now()}-${rand}`;
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await loadAccessToken();
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errBody = await response.json().catch(() => null);
    const msg =
      errBody?.error?.message ||
      errBody?.detail ||
      `HTTP ${response.status} on ${path}`;
    throw new Error(msg);
  }

  return (await response.json()) as T;
}

