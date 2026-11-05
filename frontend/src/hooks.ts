import { useEffect, useState, type DependencyList } from 'react'

export function useFetch<T>(fn: () => Promise<T>, deps: DependencyList) {
  const [state, set] = useState<{ data?: T; error?: string; loading: boolean }>({ loading: true })
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let live = true
    set(s => ({ ...s, loading: true, error: undefined }))
    fn().then(d => { if (live) set({ data: d, loading: false }) })
      .catch(e => { if (live) set(s => ({ data: s.data, error: e?.message ?? 'Request failed', loading: false })) })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])
  return { ...state, reload: () => setTick(t => t + 1) }
}
