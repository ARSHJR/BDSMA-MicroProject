import { Heart, ThumbsDown, ThumbsUp, Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useUser } from '../UserContext'
import type { Card, Reason } from '../types'
import { SafeImage, SusBadge, money } from './ui'

export function ProductCard({ p, reasons, onOpen }: { p: Card; reasons?: Reason[]; onOpen?: () => void }) {
  const { reactions, wishlist, react, toggleWish } = useUser()
  const r = reactions[p.pid]
  const wished = wishlist.includes(p.pid)
  return <article className="card-lift fade-in group relative flex flex-col overflow-hidden rounded-2xl border border-line bg-card" data-testid="product-card">
    <Link to={`/product/${p.pid}`} onClick={onOpen} className="relative block aspect-[4/5] overflow-hidden bg-[#ece5d8]">
      <SafeImage src={p.image} alt={p.title} className="h-full w-full transition duration-500 group-hover:scale-105" />
    </Link>
    <button aria-label={wished ? 'Remove from wishlist' : 'Save to wishlist'} aria-pressed={wished} onClick={() => toggleWish(p.pid)}
      className="absolute right-3 top-3 grid h-9 w-9 place-items-center rounded-full bg-card/90 shadow transition hover:scale-110">
      <Heart size={17} className={wished ? 'fill-accent text-accent' : ''} /></button>
    <div className="flex flex-1 flex-col gap-2 p-4">
      <p className="text-[11px] uppercase tracking-wider text-mute">{p.brand} · {p.article_type}</p>
      <Link to={`/product/${p.pid}`} onClick={onOpen} className="line-clamp-2 text-sm font-medium leading-snug hover:text-accent">{p.title}</Link>
      <div className="mt-auto flex items-center justify-between pt-1">
        <span className="text-sm font-semibold">{money(p.price)}</span>
        {p.avg_rating != null && <span className="flex items-center gap-1 text-xs text-mute"><Star size={12} className="fill-gold text-gold" />{p.avg_rating.toFixed(1)} ({p.n_ratings.toLocaleString()})</span>}
      </div>
      <div className="flex items-center justify-between">
        <SusBadge score={p.sustainability_score} conf={p.sus_confidence} compact />
        <div className="flex gap-1">
          <button aria-label="Like" aria-pressed={r === 'like'} onClick={() => react(p.pid, 'like')} className={`grid h-8 w-8 place-items-center rounded-full transition hover:bg-sage-soft ${r === 'like' ? 'bg-sage-soft text-sage' : 'text-mute'}`}><ThumbsUp size={15} /></button>
          <button aria-label="Dislike" aria-pressed={r === 'dislike'} onClick={() => react(p.pid, 'dislike')} className={`grid h-8 w-8 place-items-center rounded-full transition hover:bg-accent-soft ${r === 'dislike' ? 'bg-accent-soft text-accent' : 'text-mute'}`}><ThumbsDown size={15} /></button>
        </div>
      </div>
      {reasons && reasons.length > 0 && <ul className="mt-1 space-y-1 border-t border-line pt-2 text-[11.5px] leading-snug text-mute">
        {reasons.slice(0, 2).map((x, i) => <li key={i} className="flex gap-1.5"><span className={x.type === 'sustainability' ? 'text-sage' : 'text-accent'}>●</span><span>{x.text}</span></li>)}</ul>}
    </div>
  </article>
}
