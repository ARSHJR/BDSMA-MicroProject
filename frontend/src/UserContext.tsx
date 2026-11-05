import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from './api'
import type { Prefs } from './types'

interface Ctx {
  reactions: Record<string, 'like' | 'dislike'>
  wishlist: number[]
  prefs: Prefs | null
  version: number            // bumps whenever behaviour changes -> recommendation views refetch
  react: (pid: number, r: 'like' | 'dislike') => Promise<void>
  toggleWish: (pid: number) => Promise<void>
  track: (pid: number, event: 'view' | 'click') => void
  savePrefs: (p: Prefs) => Promise<void>
  ready: boolean
}
const C = createContext<Ctx>(null as unknown as Ctx)
export const useUser = () => useContext(C)

export function UserProvider({ children }: { children: ReactNode }) {
  const [reactions, setReactions] = useState<Ctx['reactions']>({})
  const [wishlist, setWishlist] = useState<number[]>([])
  const [prefs, setPrefs] = useState<Prefs | null>(null)
  const [version, setVersion] = useState(0)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    Promise.all([api<{ reactions: Ctx['reactions']; wishlist: number[] }>('/api/reactions'), api<Prefs>('/api/preferences')])
      .then(([r, p]) => { setReactions(r.reactions); setWishlist(r.wishlist); setPrefs(p) })
      .catch(() => { /* backend offline: pages show their own error state */ })
      .finally(() => setReady(true))
  }, [])

  const react = useCallback(async (pid: number, r: 'like' | 'dislike') => {
    const cur = reactions[pid]
    const event = cur === r ? 'clear_reaction' : r
    await api('/api/interactions', { method: 'POST', json: { pid, event } })
    setReactions(s => { const n = { ...s }; if (event === 'clear_reaction') delete n[pid]; else n[pid] = r; return n })
    setVersion(v => v + 1)
  }, [reactions])

  const toggleWish = useCallback(async (pid: number) => {
    const on = wishlist.includes(pid)
    if (on) await api(`/api/wishlist/${pid}`, { method: 'DELETE' })
    else await api('/api/wishlist', { method: 'POST', json: { pid } })
    setWishlist(w => on ? w.filter(x => x !== pid) : [pid, ...w])
    setVersion(v => v + 1)
  }, [wishlist])

  const track = useCallback((pid: number, event: 'view' | 'click') => {
    api('/api/interactions', { method: 'POST', json: { pid, event } }).then(() => setVersion(v => v + 1)).catch(() => {})
  }, [])

  const savePrefs = useCallback(async (p: Prefs) => {
    const saved = await api<Prefs>('/api/preferences', { method: 'PUT', json: p })
    setPrefs(saved); setVersion(v => v + 1)
  }, [])

  const value = useMemo(() => ({ reactions, wishlist, prefs, version, react, toggleWish, track, savePrefs, ready }),
    [reactions, wishlist, prefs, version, react, toggleWish, track, savePrefs, ready])
  return <C.Provider value={value}>{children}</C.Provider>
}
