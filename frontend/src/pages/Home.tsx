import { Link } from 'react-router-dom'
import { ArrowRight, Leaf, Sparkles, TrendingUp } from 'lucide-react'
import { api, qs } from '../api'
import { useFetch } from '../hooks'
import { useUser } from '../UserContext'
import type { Card, RecResponse } from '../types'
import { ProductCard } from '../components/ProductCard'
import { ErrorBox, Loading } from '../components/ui'

export default function Home() {
  const { version, prefs } = useUser()
  const recs = useFetch(() => api<RecResponse>('/api/recommendations' + qs({ k: 8 })), [version])
  const top = useFetch(() => api<{ items: Card[] }>('/api/products' + qs({ sort: 'sustainability', min_sustainability: 70, page_size: 4 })), [])
  const onboarded = !!prefs && (prefs.types.length + prefs.genders.length + prefs.colours.length > 0)
  return <div className="space-y-16">
    <section className="grid items-center gap-10 md:grid-cols-5">
      <div className="md:col-span-3">
        <p className="text-xs font-semibold uppercase tracking-[.18em] text-accent">Responsible fashion discovery</p>
        <h1 className="mt-3 text-5xl leading-[1.05] md:text-7xl">Buy less.<br />Choose <em className="text-accent">better</em>.<br />Wear longer.</h1>
        <p className="mt-6 max-w-xl text-lg text-mute">Tell us what you love and we'll find pieces you'll wear for years — and let you know when you already have something similar.</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link to={onboarded ? '/for-you' : '/me'} className="btn">{onboarded ? 'See my picks' : 'Set up my style'} <ArrowRight size={16} /></Link>
          <Link to="/shop" className="btn-ghost">Browse catalogue</Link>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 md:col-span-2">
        {[[Sparkles, 'Picked for you', 'Recommendations that adapt to what you like, with a reason for every pick.'],
          [Leaf, 'Built to last', 'See which pieces customers say hold up well, wash after wash.'],
          [TrendingUp, "What's trending", 'Explore the styles and categories shoppers are talking about.']].map(([I, t, d]) => {
          const Icon = I as typeof Leaf
          return <div key={t as string} className="flex gap-4 rounded-2xl border border-line bg-card p-4"><Icon className="mt-1 shrink-0 text-accent" size={20} /><div><p className="font-medium">{t as string}</p><p className="text-sm text-mute">{d as string}</p></div></div>
        })}
      </div>
    </section>

    <section>
      <div className="mb-6 flex items-end justify-between"><div>
        <h2 className="text-3xl">{recs.data?.mode === 'personalised' ? 'Picked for you' : onboarded ? 'Matching your preferences' : 'Popular right now'}</h2>
        <p className="text-sm text-mute">{recs.data?.mode === 'cold_start' ? 'Our most loved pieces. Like a few items or set your style to get picks made for you.' : 'Updated as you browse and like items.'}</p></div>
        <Link to="/for-you" className="text-sm underline-offset-4 hover:underline">See all →</Link></div>
      {recs.error ? <ErrorBox message={recs.error} onRetry={recs.reload} /> : recs.loading && !recs.data ? <Loading rows={4} /> :
        <div className="grid grid-cols-2 gap-5 md:grid-cols-4">{recs.data!.items.map(p => <ProductCard key={p.pid} p={p} reasons={p.reasons} />)}</div>}
    </section>

    <section>
      <div className="mb-6"><h2 className="text-3xl">Built to last</h2><p className="text-sm text-mute">Top-rated for durability, based on what customers say in their reviews.</p></div>
      {top.error ? <ErrorBox message={top.error} onRetry={top.reload} /> : top.loading ? <Loading rows={4} /> :
        <div className="grid grid-cols-2 gap-5 md:grid-cols-4">{top.data!.items.map(p => <ProductCard key={p.pid} p={p} />)}</div>}
    </section>
  </div>
}
