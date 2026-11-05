import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Leaf } from 'lucide-react'
import { api, qs } from '../api'
import { useFetch } from '../hooks'
import { useUser } from '../UserContext'
import type { RecResponse } from '../types'
import { ProductCard } from '../components/ProductCard'
import { Empty, ErrorBox, Loading, PageHead } from '../components/ui'

const MODE_TEXT = {
  cold_start: ['Cold start', 'No history yet, so the engine falls back to popularity (Bayesian rating × √ratings). Set your style or like a few items.'],
  preferences: ['Preference-based', 'Ranking uses your onboarding choices plus popularity until you interact with products.'],
  personalised: ['Personalised hybrid', 'Content similarity + collaborative neighbours + your preferences, re-ranked for sustainability and diversity.'],
} as const
const GROUPS = ['', 'Clothing', 'Accessories', 'Footwear']

export default function ForYou() {
  const { version, prefs } = useUser()
  const [sus, setSus] = useState<number | null>(null)
  const [group, setGroup] = useState('')
  const [open, setOpen] = useState<number | null>(null)
  const s = sus ?? prefs?.sustain ?? 0.3
  const recs = useFetch(() => api<RecResponse>('/api/recommendations' + qs({ k: 24, sustain: s, category_group: group })), [version, s, group])
  return <div>
    <PageHead eyebrow="Personalised" title="Picked for you" sub="Every pick is computed by the backend from your likes, dislikes, views, wishlist and preferences — and explained." />
    <div className="mb-8 grid gap-4 md:grid-cols-[1fr_auto]">
      <div className="rounded-3xl border border-line bg-card p-5">
        <label className="flex items-center justify-between text-sm font-medium"><span className="flex items-center gap-2"><Leaf size={16} className="text-sage" />Sustainability weight (λ)</span><span className="font-display text-xl">{Math.round(s * 100)}%</span></label>
        <input aria-label="Sustainability weight" type="range" min={0} max={1} step={0.05} value={s} onChange={e => setSus(Number(e.target.value))} className="mt-2 w-full accent-[#4b6b57]" />
        <p className="mt-1 text-xs text-mute">final score = (1−λ)·relevance + λ·longevity proxy. At 0% only taste matters; at 100% the longest-lasting-looking items in your candidate set win.</p>
      </div>
      <div className="flex flex-wrap items-start gap-2 md:flex-col">{GROUPS.map(g => <button key={g} onClick={() => setGroup(g)} className={`pill ${group === g ? '!border-ink !bg-ink !text-paper' : 'hover:border-ink'}`}>{g || 'All'}</button>)}</div>
    </div>
    {recs.data && <div className="mb-6 flex flex-wrap items-center gap-3 text-sm"><span className="pill !border-accent !text-accent">{MODE_TEXT[recs.data.mode][0]}</span>
      <span className="text-mute">{MODE_TEXT[recs.data.mode][1]}</span><span className="text-xs text-mute">· {recs.data.n_signals} signals · {recs.data.latency_ms} ms</span></div>}
    {recs.error ? <ErrorBox message={recs.error} onRetry={recs.reload} /> : recs.loading && !recs.data ? <Loading rows={12} /> :
      recs.data!.items.length === 0 ? <Empty title="No recommendations" hint="Try a different category." action={<Link to="/shop" className="btn">Browse catalogue</Link>} /> :
        <div className={`grid grid-cols-2 gap-5 transition-opacity md:grid-cols-3 xl:grid-cols-4 ${recs.loading ? 'opacity-50' : ''}`}>
          {recs.data!.items.map(p => <div key={p.pid}><ProductCard p={p} reasons={p.reasons} />
            <button className="mt-1 w-full text-center text-[11px] text-mute underline-offset-2 hover:underline" onClick={() => setOpen(open === p.pid ? null : p.pid)}>{open === p.pid ? 'Hide' : 'Show'} score breakdown</button>
            {open === p.pid && <dl className="mt-1 grid grid-cols-2 gap-x-3 rounded-xl bg-card p-3 text-[11px] text-mute">
              <dt>Relevance</dt><dd className="text-right text-ink">{p.relevance.toFixed(3)}</dd>
              <dt>Content sim.</dt><dd className="text-right text-ink">{p.parts.content}</dd><dt>Collaborative</dt><dd className="text-right text-ink">{p.parts.cf}</dd>
              <dt>Preference</dt><dd className="text-right text-ink">{p.parts.pref}</dd><dt>Popularity</dt><dd className="text-right text-ink">{p.parts.pop}</dd>
              <dt>Final</dt><dd className="text-right font-semibold text-ink">{p.score.toFixed(3)}</dd></dl>}</div>)}
        </div>}
  </div>
}
