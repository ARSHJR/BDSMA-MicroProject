import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, Leaf } from 'lucide-react'
import { api } from '../api'
import { useFetch } from '../hooks'
import type { Card } from '../types'
import { ProductCard } from '../components/ProductCard'
import { ChartCard, ErrorBox, PageHead, Spinner, Stat } from '../components/ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
const axis = { fontSize: 11, fill: '#6f675d' }

export default function Sustainability() {
  const s = useFetch(() => api<any>('/api/sustainability'), [])
  if (s.error) return <ErrorBox message={s.error} onRetry={s.reload} />
  if (!s.data) return <Spinner />
  const d = s.data
  const tr = d.tradeoff.map((t: any) => ({ lambda: `${Math.round(t.lambda * 100)}%`, 'Avg longevity score': +t.avg_sustainability_score.toFixed(1), 'NDCG@10 (×1000)': +(t.ndcg_at_k ?? t['ndcg@k']) * 1000 }))
  const first = d.tradeoff[0], last = d.tradeoff[d.tradeoff.length - 1]
  return <div className="space-y-12">
    <PageHead eyebrow="SDG 12 · Responsible consumption & production" title="Sustainability insights" sub="How this platform nudges toward fewer, better, longer-lasting purchases — and exactly how far its evidence goes." />
    <div className="flex gap-3 rounded-2xl border border-gold/40 bg-[#f5edd6] p-4 text-sm" role="note"><AlertTriangle className="mt-0.5 shrink-0 text-gold" size={18} /><p><b>Honest limits.</b> {d.disclaimer} The dataset contains no verified material composition, certification or carbon data, so none is shown.</p></div>
    <section className="grid gap-4 md:grid-cols-2">{d.how_it_supports_sdg12.map((t: string, i: number) => <div key={i} className="flex gap-3 rounded-2xl border border-line bg-card p-5"><Leaf className="mt-0.5 shrink-0 text-sage" size={18} /><p className="text-sm">{t}</p></div>)}</section>
    <section><h2 className="mb-4 text-3xl">How the longevity proxy is computed</h2>
      <div className="grid gap-4 md:grid-cols-4">{Object.entries(d.weights).map(([k, v]) => <Stat key={k} label={k.replace(/_/g, ' ')} value={`${Math.round((v as number) * 100)}%`} hint="weight" />)}</div>
      <p className="mt-3 text-sm text-mute">Each rate is shrunk toward the catalogue mean (empirical Bayes, K={d.shrinkage_prior_strength}) so items with few reviews are not over-trusted; a visible “evidence” percentage accompanies every score. Corr(score, rating) = {d.corr_score_vs_rating}. {d.natural_fibre_items.toLocaleString()} items name a natural-fibre material in their text (shown as a label only — not scored as “eco”).</p></section>
    <div className="grid gap-6 lg:grid-cols-2">
      <ChartCard title="Average longevity proxy by category" sub="Computed from review evidence"><div className="h-80"><ResponsiveContainer><BarChart data={d.by_article_type.slice(0, 12)} layout="vertical" margin={{ left: 40 }}><CartesianGrid stroke="#e5ddd0" horizontal={false} /><XAxis type="number" domain={[40, 80]} tick={axis} /><YAxis type="category" dataKey="article_type" width={130} tick={axis} /><Tooltip /><Bar dataKey="avg_score" fill="#4b6b57" radius={[0, 6, 6, 0]} /></BarChart></ResponsiveContainer></div></ChartCard>
      <ChartCard title="Ranking trade-off as λ increases" sub="Held-out test lists (top-10): longevity gained vs. accuracy lost"><div className="h-80"><ResponsiveContainer><LineChart data={tr}><CartesianGrid stroke="#e5ddd0" vertical={false} /><XAxis dataKey="lambda" tick={axis} /><YAxis yAxisId="a" tick={axis} /><YAxis yAxisId="b" orientation="right" tick={axis} /><Tooltip /><Legend />
        <Line yAxisId="a" dataKey="Avg longevity score" stroke="#4b6b57" strokeWidth={2.5} /><Line yAxisId="b" dataKey="NDCG@10 (×1000)" stroke="#b4532a" strokeWidth={2.5} /></LineChart></ResponsiveContainer></div>
        <p className="mt-2 text-xs text-mute">From λ=0 to λ={last.lambda}: average longevity {first.avg_sustainability_score.toFixed(1)} → {last.avg_sustainability_score.toFixed(1)}; NDCG@10 {first['ndcg@k'].toFixed(4)} → {last['ndcg@k'].toFixed(4)}. The slider lets users choose their own point on this curve.</p></ChartCard>
    </div>
    <section><h2 className="text-3xl">Highest-evidence, longest-lasting picks</h2><p className="mb-5 text-sm text-mute">Items with ≥ 60% evidence confidence and the best proxy scores.</p>
      <div className="grid grid-cols-2 gap-5 md:grid-cols-4">{d.top_products.slice(0, 8).map((p: Card) => <ProductCard key={p.pid} p={p} />)}</div></section>
  </div>
}
