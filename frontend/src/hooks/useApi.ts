"use client";

// This is a generic fetch hook whose caller-supplied `deps` array is spread into
// the effect, which the exhaustive-deps rule can't statically verify. That is the
// intended contract, so the rule is disabled for this file only.
/* eslint-disable react-hooks/exhaustive-deps */
import { useCallback, useEffect, useState } from "react";

export interface ApiState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  reload: () => Promise<void>;
}

/** Minimal fetch-on-mount hook with a manual reload. */
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetcher());
    } catch (err) {
      setError(err as Error);
    } finally {
      setLoading(false);
    }
  }, deps);

  useEffect(() => {
    void load();
  }, [load]);

  return { data, error, loading, reload: load };
}
