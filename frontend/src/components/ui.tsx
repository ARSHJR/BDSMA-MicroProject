import { useState, type ReactNode } from 'react'
import { AlertTriangle, ImageOff, Inbox, Leaf } from 'lucide-react'

export function SafeImage({ src, alt, className = '' }: { src?: string; alt: string; className?: string }) {
  const [bad, setBad] = useState(false)
  if (!src || bad) {
    return <div className={`flex flex-col items-center justify-center gap-1 bg-[#ece5d8] text-mute ${className}`} role="img" aria-label={alt}>
      <ImageOff size={22} /><span className="text-[10px] uppercase tracking-wider">Image unavailable</span></div>
  }
  return <img src={src} alt={alt} loading="lazy" onError={() => setBad(true)} className={`object-cover ${className}`} referrerPolicy="no-referrer" />
}

export function Loading({ rows = 8 }: { rows?: number }) {
  return <div className="grid grid-cols-2 gap-5 md:grid-cols-3 lg:grid-cols-4" aria-busy="true" aria-label="Loading">
    {Array.from({ length: rows }).map((_, i) => <div key={i}><div className="shimmer aspect-[4/5] rounded-2xl" /><div className="shimmer mt-3 h-3 w-3/4 rounded" /><div className="shimmer mt-2 h-3 w-1/3 rounded" /></div>)}
  </div>
}

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return <div className="flex items-center gap-3 py-16 text-mute" role="status"><div className="h-5 w-5 animate-spin rounded-full border-2 border-line border-t-ink" />{label}</div>
}

export function Empty({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return <div className="flex flex-col items-center rounded-3xl border border-dashed border-line bg-card/60 px-6 py-16 text-center">
    <Inbox className="text-mute" size={30} /><h3 className="mt-3 text-xl">{title}</h3>
    {hint && <p className="mt-1 max-w-md text-sm text-mute">{hint}</p>}{action && <div className="mt-5">{action}</div>}</div>
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div role="alert" className="flex items-start gap-3 rounded-2xl border border-accent/30 bg-accent-soft px-5 py-4 text-sm">
    <AlertTriangle className="mt-0.5 shrink-0 text-accent" size={18} />
    <div className="flex-1"><p className="font-medium">Something went wrong</p><p className="text-mute">{message}. Is the API running on port 8000?</p></div>
    {onRetry && <button className="btn-ghost !py-1.5" onClick={onRetry}>Retry</button>}</div>
}

export function SusBadge({ score, compact }: { score: number; conf?: number; compact?: boolean }) {
  const tone = score >= 65 ? 'bg-sage-soft text-sage' : score >= 50 ? 'bg-[#efe9d3] text-gold' : 'bg-[#eee6e0] text-mute'
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${tone}`}
    title={`Durability rating ${score.toFixed(0)}/100, estimated from customer reviews`}>
    <Leaf size={11} />{compact ? score.toFixed(0) : `Built to last ${score.toFixed(0)}`}</span>
}

export function PageHead({ eyebrow, title, sub, right }: { eyebrow?: string; title: string; sub?: string; right?: ReactNode }) {
  return <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
    <div>{eyebrow && <p className="text-xs font-semibold uppercase tracking-[.18em] text-accent">{eyebrow}</p>}
      <h1 className="mt-1 text-4xl md:text-5xl">{title}</h1>{sub && <p className="mt-2 max-w-2xl text-mute">{sub}</p>}</div>{right}</header>
}

export function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return <div className="rounded-2xl border border-line bg-card p-5"><p className="text-xs uppercase tracking-wider text-mute">{label}</p>
    <p className="mt-1 font-display text-3xl">{typeof value === 'number' ? value.toLocaleString() : value}</p>{hint && <p className="mt-1 text-xs text-mute">{hint}</p>}</div>
}

export function ChartCard({ title, sub, children, banner }: { title: string; sub?: string; children: ReactNode; banner?: string }) {
  return <section className="rounded-3xl border border-line bg-card p-6">
    <h3 className="text-xl">{title}</h3>{sub && <p className="mb-3 text-sm text-mute">{sub}</p>}
    {banner && <p className="mb-3 rounded-lg bg-accent-soft px-3 py-1.5 text-xs font-medium text-accent">{banner}</p>}{children}</section>
}

export const PALETTE = ['#1a1612', '#b4532a', '#4b6b57', '#b08a2e', '#6f675d', '#8a5a44', '#7d9a86', '#d19a6a']
export const money = (p: number | null) => p == null ? 'Price n/a' : `$${p.toFixed(2)}`
