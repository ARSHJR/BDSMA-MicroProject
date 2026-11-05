import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Heart, Info, Recycle, ThumbsDown, ThumbsUp } from 'lucide-react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { api } from '../api'
import { useFetch } from '../hooks'
import { useUser } from '../UserContext'
import type { ProductDetail } from '../types'
import { ProductCard } from '../components/ProductCard'
import { ErrorBox, SafeImage, Spinner, SusBadge, money } from '../components/ui'

const SENT_COL: Record<string, string> = { positive: '#4b6b57', neutral: '#b08a2e', negative: '#b4532a' }
const LABELS: Record<string, string> = { rating_quality: 'Rated quality', durability_signals: 'Durability mentions', fit_reliability: 'Fit reliability (fewer returns)', versatility: 'Versatility' }

export default function Product() {
  const { pid } = useParams()
  const { reactions, wishlist, react, toggleWish, track, version } = useUser()
  const d = useFetch(() => api<ProductDetail>(`/api/products/${pid}`), [pid, version === 0 ? 0 : wishlist.length])
  useEffect(() => { if (pid) track(Number(pid), 'view'); window.scrollTo(0, 0) }, [pid]) // eslint-disable-line
  if (d.error) return <ErrorBox message={d.error} onRetry={d.reload} />
  if (!d.data) return <Spinner />
  const p = d.data
  const r = reactions[p.pid]; const wished = wishlist.includes(p.pid)
  const sent = Object.entries(p.reviews.sentiment).map(([name, value]) => ({ name, value }))
  return <div className="space-y-14">
    <nav className="text-xs text-mute"><Link to="/shop" className="hover:underline">Shop</Link> / <Link to={`/shop?article_type=${encodeURIComponent(p.article_type)}`} className="hover:underline">{p.article_type}</Link></nav>
    <div className="grid gap-10 md:grid-cols-2">
      <div className="overflow-hidden rounded-3xl border border-line bg-card"><SafeImage src={p.image_hires || p.image} alt={p.title} className="aspect-[4/5] w-full" /></div>
      <div className="fade-in">
        <p className="text-xs uppercase tracking-[.18em] text-accent">{p.brand}</p>
        <h1 className="mt-2 text-3xl leading-tight md:text-4xl">{p.title}</h1>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-mute">
          <span className="font-display text-3xl text-ink">{money(p.price)}</span>
          {p.avg_rating != null && <span>★ {p.avg_rating.toFixed(1)} · {p.n_ratings.toLocaleString()} ratings</span>}
          <SusBadge score={p.sustainability_score} conf={p.sus_confidence} />
        </div>
        <div className="mt-4 flex flex-wrap gap-2"><span className="pill">{p.category_group}</span><span className="pill">{p.article_type}</span><span className="pill">{p.gender}</span>
          {p.colour && <span className="pill">{p.colour}</span>}{p.materials.map(m => <span key={m} className="pill">{m}</span>)}</div>
        <div className="mt-6 flex flex-wrap gap-3">
          <button className={r === 'like' ? 'btn !bg-sage' : 'btn-ghost'} aria-pressed={r === 'like'} onClick={() => react(p.pid, 'like')}><ThumbsUp size={16} />{r === 'like' ? 'Liked' : 'Like'}</button>
          <button className={r === 'dislike' ? 'btn !bg-accent' : 'btn-ghost'} aria-pressed={r === 'dislike'} onClick={() => react(p.pid, 'dislike')}><ThumbsDown size={16} />Not for me</button>
          <button className="btn-ghost" aria-pressed={wished} onClick={() => toggleWish(p.pid)}><Heart size={16} className={wished ? 'fill-accent text-accent' : ''} />{wished ? 'Saved' : 'Save to wishlist'}</button>
        </div>

        {p.already_saved_similar.length > 0 && <div className="mt-6 rounded-2xl border border-sage/30 bg-sage-soft p-4" role="note">
          <p className="flex items-center gap-2 font-medium text-sage"><Recycle size={16} />You may already have something like this</p>
          <p className="mt-1 text-sm">Before buying, check: {p.already_saved_similar.map((a, i) => <span key={a.pid}>{i > 0 && ', '}<Link className="underline" to={`/product/${a.pid}`}>{a.title.slice(0, 48)}…</Link> ({Math.round((a.similarity ?? 0) * 100)}% similar)</span>)}</p></div>}

        <section className="mt-8 rounded-2xl border border-line bg-card p-5">
          <h3 className="flex items-center gap-2 text-lg">Built to last <span className="font-sans text-sm text-mute">{p.sustainability_score.toFixed(0)}/100</span></h3>
          <p className="mb-3 flex gap-1.5 text-xs text-mute"><Info size={13} className="mt-0.5 shrink-0" />Based on ratings and what customers say in {p.n_text_reviews} reviews.</p>
          {Object.entries(p.sustainability_breakdown).map(([k, v]) => <div key={k} className="mb-2"><div className="flex justify-between text-xs"><span>{LABELS[k] ?? k}</span><span>{Math.round(v * 100)}%</span></div>
            <div className="h-1.5 rounded bg-line"><div className="h-1.5 rounded bg-sage transition-all" style={{ width: `${v * 100}%` }} /></div></div>)}
          <p className="mt-3 text-xs text-mute">Reviews on durability: {p.signals.durability_praise_reviews} positive · {p.signals.durability_complaint_reviews} complaints · {p.signals.fit_or_return_complaint_reviews} fit or return issues</p>
        </section>
        {(p.features || p.description) && <section className="mt-6"><h3 className="text-lg">Details</h3><p className="mt-1 text-sm leading-relaxed text-mute">{p.features || p.description}</p></section>}
      </div>
    </div>

    <section className="grid gap-8 md:grid-cols-2">
      <div><h3 className="text-2xl">What reviewers say</h3><p className="mb-3 text-xs text-mute">Customer reviews</p>
        {sent.length === 0 ? <p className="text-sm text-mute">No text reviews for this item.</p> :
          <div className="flex items-center gap-6"><div className="h-36 w-36"><ResponsiveContainer><PieChart><Pie data={sent} dataKey="value" innerRadius={34} outerRadius={60} paddingAngle={2}>{sent.map(s => <Cell key={s.name} fill={SENT_COL[s.name]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></div>
            <ul className="text-sm">{sent.map(s => <li key={s.name}><span className="mr-2 inline-block h-2 w-2 rounded-full" style={{ background: SENT_COL[s.name] }} />{s.name}: {s.value}</li>)}</ul></div>}
      </div>
      <div className="space-y-3">{p.reviews.top_reviews.map((rv, i) => <blockquote key={i} className="rounded-2xl border border-line bg-card p-4 text-sm"><p className="text-gold">{'★'.repeat(Math.round(rv.rating))}</p><p className="mt-1 text-mute">“{rv.text}”</p></blockquote>)}</div>
    </section>

    {p.longevity_alternatives.length > 0 && <section><h2 className="text-3xl">Longer-lasting alternatives</h2><p className="mb-5 text-sm text-mute">Similar pieces that customers say last longer.</p>
      <div className="grid grid-cols-2 gap-5 md:grid-cols-4">{p.longevity_alternatives.map(a => <div key={a.pid}><ProductCard p={a} /><p className="mt-1 text-center text-xs text-sage">Lasts longer</p></div>)}</div></section>}
    <section><h2 className="text-3xl">Related pieces</h2><p className="mb-5 text-sm text-mute">Similar styles, and pieces other shoppers liked too.</p>
      <div className="grid grid-cols-2 gap-5 md:grid-cols-4">{p.related.slice(0, 8).map(a => <ProductCard key={a.pid} p={a} />)}</div></section>
  </div>
}
