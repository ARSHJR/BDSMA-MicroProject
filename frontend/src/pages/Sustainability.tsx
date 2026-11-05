import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Leaf, Recycle, Search, ThumbsUp } from 'lucide-react'
import { api } from '../api'
import { useFetch } from '../hooks'
import type { Card } from '../types'
import { ProductCard } from '../components/ProductCard'
import { ChartCard, ErrorBox, PageHead, Spinner } from '../components/ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
const axis = { fontSize: 11, fill: '#6f675d' }
const TIPS = [
  [Leaf, 'Built to last', 'Every product shows a durability rating based on what customers say about wear, fit and returns.'],
  [Recycle, 'Already own something similar?', 'We let you know when an item is like something on your wishlist, before you buy.'],
  [Search, 'Longer-lasting alternatives', 'On each product page, see similar pieces that customers say hold up better.'],
  [ThumbsUp, 'You are in control', 'Use the slider on your For you page to put durable pieces first.'],
] as const

export default function Sustainability() {
  const s = useFetch(() => api<any>('/api/sustainability'), [])
  if (s.error) return <ErrorBox message={s.error} onRetry={s.reload} />
  if (!s.data) return <Spinner />
  const d = s.data
  return <div className="space-y-12">
    <PageHead eyebrow="Responsible fashion" title="Buy less, wear longer" sub="The longer you wear something, the less waste it creates. Here is how we help you choose pieces that last." />
    <section className="grid gap-4 md:grid-cols-2">{TIPS.map(([I, t, x]) => <div key={t} className="flex gap-3 rounded-2xl border border-line bg-card p-5"><I className="mt-0.5 shrink-0 text-sage" size={18} /><div><p className="font-medium">{t}</p><p className="text-sm text-mute">{x}</p></div></div>)}</section>
    <ChartCard title="Most durable categories" sub="Average durability rating from customer reviews"><div className="h-80"><ResponsiveContainer><BarChart data={d.by_article_type.slice(0, 12)} layout="vertical" margin={{ left: 40 }}><CartesianGrid stroke="#e5ddd0" horizontal={false} /><XAxis type="number" domain={[40, 80]} tick={axis} /><YAxis type="category" dataKey="article_type" width={130} tick={axis} /><Tooltip /><Bar dataKey="avg_score" name="Durability rating" fill="#4b6b57" radius={[0, 6, 6, 0]} /></BarChart></ResponsiveContainer></div></ChartCard>
    <section><h2 className="text-3xl">Built to last</h2><p className="mb-5 text-sm text-mute">Pieces with plenty of reviews and the best durability ratings.</p>
      <div className="grid grid-cols-2 gap-5 md:grid-cols-4">{d.top_products.slice(0, 8).map((p: Card) => <ProductCard key={p.pid} p={p} />)}</div></section>
  </div>
}
