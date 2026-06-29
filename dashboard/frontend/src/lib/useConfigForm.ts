// The shared "edit a guild's module config" hook. Every module panel uses it,
// so they all behave identically: load → edit a local draft → Save (PUT) or Reset.
//
// `project` maps the fetched config to the editable subset that the PUT accepts.
// For modules whose GET also returns server-managed lists (leveling rewards,
// automod word lists), project() strips them so editing a scalar never fights
// with a list mutation — the lists are read straight from `config` and changed
// through their own endpoints via useConfigAction().
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export function useConfigForm<TConfig, TDraft extends object>(opts: {
  queryKey: unknown[];
  path: string;
  project: (config: TConfig) => TDraft;
}) {
  const qc = useQueryClient();
  const query = useQuery<TConfig>({
    queryKey: opts.queryKey,
    queryFn: () => api.get<TConfig>(opts.path),
    staleTime: 30_000,
  });

  const serverDraft = query.data ? opts.project(query.data) : null;
  const signature = serverDraft ? JSON.stringify(serverDraft) : null;

  const [draft, setDraft] = useState<TDraft | null>(null);
  const [justSaved, setJustSaved] = useState(false);

  // Re-sync the local draft only when the *editable* fields change server-side
  // (keyed on `signature`), so a list mutation doesn't wipe in-progress edits.
  useEffect(() => {
    if (serverDraft) setDraft(serverDraft);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  const mutation = useMutation({
    mutationFn: (body: TDraft) => api.put<TConfig>(opts.path, body),
    onSuccess: (data) => {
      qc.setQueryData(opts.queryKey, data);
      setJustSaved(true);
    },
  });

  const dirty = !!draft && !!signature && JSON.stringify(draft) !== signature;

  function set<K extends keyof TDraft>(key: K, value: TDraft[K]) {
    setDraft((d) => (d ? { ...d, [key]: value } : d));
    setJustSaved(false);
  }

  return {
    config: query.data,
    draft,
    set,
    setDraft,
    dirty,
    justSaved,
    isLoading: query.isLoading,
    isError: query.isError,
    save: () => draft && mutation.mutate(draft),
    reset: () => {
      if (serverDraft) setDraft(serverDraft);
      setJustSaved(false);
    },
    saving: mutation.isPending,
    error: mutation.error ? (mutation.error as Error).message : null,
  };
}

/** For immediate-effect actions (add/remove a reward, word, etc.) that return the
 *  full updated config. Pass a thunk that performs the api call; the result is
 *  written back into the same query so the panel re-renders with fresh lists. */
export function useConfigAction<TConfig>(queryKey: unknown[]) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fn: () => Promise<TConfig>) => fn(),
    onSuccess: (data) => qc.setQueryData(queryKey, data),
  });
}
