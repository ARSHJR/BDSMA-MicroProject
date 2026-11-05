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
  cold_start: ['Popular picks', 'Our most loved pieces. Set your style or like a few items to personalise.'],
  preferences: ['Based on your style', 'Chosen from the styles you told us you like.'],
  personalised: ['Made for you', 'Based on what you have liked and saved.'],
} as const
const GROUPS = ['', 'Clothing', 'Accessories', 'Footwear']

export default function ForYou() {
  const { version, prefs } = useUser()
  const [sus, setSus] = useState<number | null>(null)
  const [group, setGroup] = useState('')
    const s = sus ?? prefs?.sustain ?? 0.3
  const recs = useFetch(() => api<RecResponse>('/api/recommendations' + qs({ k: 24, sustain: s, category_group: group })), [version, s, group])
  return <div>
    <PageHead eyebrow="Personalised" title="Picked for you" sub="Recommendations that update as you like, save and browse." />
    <div className="mb-8 grid gap-4 md:grid-cols-[1fr_auto]">
      <div className="rounded-3xl border border-line bg-card p-5">
        <label className="flex items-center justify-between text-sm font-medium"><span className="flex items-center gap-2"><Leaf size={16} className="text-sage" />Prioritise pieces built to last</span><span className="font-display text-xl">{Math.round(s * 100)}%</span></label>
        <input aria-label="Sustainability weight" type="range" min={0} max={1} step={0.05} value={s} onChange={e => setSus(Number(e.target.value))} className="mt-2 w-full accent-[#4b6b57]" />
        <p className="mt-1 text-xs text-mute">Slide right to see more durable pieces first. Slide left to focus only on your taste.</p>
      </div>
      <div className="flex flex-wrap items-start gap-2 md:flex-col">{GROUPS.map(g => <button key={g} onClick={() => setGroup(g)} className={`pill ${group === g ? '!border-ink !bg-ink !text-paper' : 'hover:border-ink'}`}>{g || 'All'}</button>)}</div>
    </div>
    {recs.data && <div className="mb-6 flex flex-wrap items-center gap-3 text-sm"><span className="pill !border-accent !text-accent">{MODE_TEXT[recs.data.mode][0]}</span>
      <span className="text-mute">{MODE_TEXT[recs.data.mode][1]}</span></div>}
    {recs.error ? <ErrorBox message={recs.error} onRetry={recs.reload} /> : recs.loading && !recs.data ? <Loading rows={12} /> :
      recs.data!.items.length === 0 ? <Empty title="No recommendations" hint="Try a different category." action={<Link to="/shop" className="btn">Browse catalogue</Link>} /> :
        <div className={`grid grid-cols-2 gap-5 transition-opacity md:grid-cols-3 xl:grid-cols-4 ${recs.loading ? 'opacity-50' : ''}`}>
          {recs.data!.items.map(p => <div key={p.pid}><ProductCard p={p} reasons={p.reasons} />
</div>)}
        </div>}
  </div>
}
