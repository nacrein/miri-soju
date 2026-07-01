// Session state, backed by React Query. The browser never decides if you're
// logged in, it asks /api/auth/me and trusts the cookie-backed answer.
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "../api/client";
import type { Session } from "../lib/types";

export function useSession() {
  return useQuery<Session | null>({
    queryKey: ["session"],
    queryFn: async () => {
      try {
        return await api.get<Session>("/auth/me");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null; // logged out, not an error
        throw e;
      }
    },
    staleTime: 60_000,
    retry: false,
  });
}

/** Full-page redirect into the Discord OAuth flow. */
export function loginRedirect(): void {
  window.location.href = "/api/auth/login";
}

export function useLogout() {
  const qc = useQueryClient();
  return async () => {
    await api.post("/auth/logout");
    qc.clear();
    window.location.href = "/";
  };
}
