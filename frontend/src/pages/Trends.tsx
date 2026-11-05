import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Upload } from 'lucide-react'
import { api } from '../api'
import { useFetch } from '../hooks'
import { ChartCard, ErrorBox, PageHead, PALETTE, Spinner, Stat } from '../components/ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
const SENT_COL: Record<string, string> = { positive: '#4b6b57', neutral: '#b08a2e', negative: '#b4532a' }
const axis = { fontSize: 11, fill: '#6f675d' }

function Social({ d }: { d: any }) {
  const tags: string[] = useMemo(() => [...new Set<string>(d.hashtag_trend.map((r: any) => r.hashtag))], [d])
  const rows = useMemo(() => {
    const m: Record<string, any> = {}
    d.hashtag_trend.forEach((r: any) => { (m[r.month] ??= { month: r.month })[r.hashtag] = r.posts })
    return Object.values(m).sort((a: any, b: any) => a.month.localeCompare(b.month))
  }, [d])
  const sent = Object.entries(d.sentiment_distribution).map(([name, value]) => ({ name, value }))
  return <div className="space-y-6">
    <p className={`rounded-xl px-4 py-2 text-sm font-medium ${d.is_synthetic ? 'bg-accent-soft text-accent' : 'bg-sage-soft text-sage'}`} role="note">{d.banner}</p>
    <div className="grid gap-4 md:grid-cols-3"><Stat label="Posts analysed" value={d.n_posts} hint={`${d.date_range[0]} → ${d.date_range[1]}`} />
      <Stat label="Positive share" value={`${Math.round(100 * (d.sentiment_distribution.positive ?? 0) / d.n_posts)}%`} /><Stat label="Top hashtag" value={d.top_hashtags[0]?.hashtag ?? '—'} hint={`${d.top_hashtags[0]?.posts ?? 0} posts`} /></div>
    <div className="grid gap-6 lg:grid-cols-2">
      <ChartCard title="Hashtag volume over time" banner={d.is_synthetic ? 'Demonstration data' : undefined}>
        <div className="h-72"><ResponsiveContainer><LineChart data={rows}><CartesianGrid stroke="#e5ddd0" vertical={false} /><XAxis dataKey="month" tick={axis} /><YAxis tick={axis} /><Tooltip /><Legend />
          {tags.map((t, i) => <Line key={t} dataKey={t} stroke={PALETTE[i % PALETTE.length]} dot={false} strokeWidth={2} />)}</LineChart></ResponsiveContainer></div></ChartCard>
      <ChartCard title="Sentiment of posts" sub="VADER compound score" banner={d.is_synthetic ? 'Demonstration data' : undefined}>
        <div className="h-72"><ResponsiveContainer><BarChart data={sent}><CartesianGrid stroke="#e5ddd0" vertical={false} /><XAxis dataKey="name" tick={axis} /><YAxis tick={axis} /><Tooltip />
          <Bar dataKey="value" radius={[6, 6, 0, 0]}>{sent.map(s => <Cell key={s.name} fill={SENT_COL[s.name]} />)}</Bar></BarChart></ResponsiveContainer></div></ChartCard>
    </div>
    <div className="grid gap-6 lg:grid-cols-2">
      <ChartCard title="Top hashtags" sub="posts · likes · mean sentiment"><table className="w-full text-sm"><tbody>{d.top_hashtags.slice(0, 8).map((h: any) => <tr key={h.hashtag} className="border-t border-line"><td className="py-1.5 font-medium">{h.hashtag}</td><td>{h.posts}</td><td>{h.likes.toLocaleString()}</td><td className={h.avg_sentiment >= 0 ? 'text-sage' : 'text-accent'}>{h.avg_sentiment.toFixed(2)}</td></tr>)}</tbody></table></ChartCard>
      <ChartCard title="Rising hashtags" sub="share in 2nd half ÷ share in 1st half of the period"><ul className="space-y-2 text-sm">{d.rising_hashtags.map((h: any) => <li key={h.hashtag} className="flex justify-between border-t border-line pt-2"><span className="font-medium">{h.hashtag}</span><span className="text-sage">×{h.growth_ratio}</span></li>)}</ul></ChartCard>
    </div>
  </div>
}

export function SocialLab() {
  const demo = useFetch(() => api<any>('/api/social/demo'), [])
  const [upload, setUpload] = useState<any>(null)
  const [upErr, setUpErr] = useState('')
  const [busy, setBusy] = useState(false)
  const onFile = async (f?: File) => {
    if (!f) return
    setBusy(true); setUpErr('')
    try { setUpload(await api('/api/social/analyse', { method: 'POST', json: { csv_text: await f.text() } })) } catch (e) { setUpErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="space-y-8">
      <section className="rounded-3xl border border-line bg-card p-6">
        <h3 className="text-xl">Analyse your own social-post export</h3>
        <p className="mt-1 text-sm text-mute">Upload a CSV with columns <code>text</code>, <code>created_at</code> and optionally <code>likes</code>, <code>platform</code> (e.g. a Reddit/X export you are licensed to use). The same hashtag, sentiment and trend pipeline runs on the backend.</p>
        <label className="btn-ghost mt-4 cursor-pointer"><Upload size={15} />{busy ? 'Analysing…' : 'Choose CSV'}<input aria-label="Upload CSV" type="file" accept=".csv,text/csv" className="hidden" onChange={e => onFile(e.target.files?.[0])} /></label>
        {upErr && <div className="mt-3"><ErrorBox message={upErr} /></div>}
      </section>
      {upload && <div><h3 className="mb-3 text-2xl">Your upload</h3><Social d={upload} /></div>}
      <div><h3 className="mb-3 text-2xl">Built-in demo</h3>{demo.error ? <ErrorBox message={demo.error} onRetry={demo.reload} /> : !demo.data ? <Spinner /> : <Social d={demo.data} />}</div>
    </div>
  )
}

export default function Trends() {
  const trends = useFetch(() => api<any>('/api/trends'), [])
  const sent = useFetch(() => api<any>('/api/sentiment'), [])

  const lines = useMemo(() => {
    if (!trends.data) return { rows: [], types: [] as string[] }
    const m: Record<number, any> = {}; const types = new Set<string>()
    trends.data.category_by_year.forEach((r: any) => { types.add(r.article_type); (m[r.year] ??= { year: r.year })[r.article_type] = r.reviews })
    return { rows: Object.values(m).sort((a: any, b: any) => a.year - b.year), types: [...types] }
  }, [trends.data])

  const sd = sent.data
  return <div>
    <PageHead eyebrow="Trends" title="What shoppers are talking about" sub="See which styles are growing and how customers feel about them." />
    {(trends.error ? <ErrorBox message={trends.error} onRetry={trends.reload} /> : !trends.data || !sd ? <Spinner /> : <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard title="Review activity by category" sub="Customer reviews per year">
          <div className="h-80"><ResponsiveContainer><LineChart data={lines.rows}><CartesianGrid stroke="#e5ddd0" vertical={false} /><XAxis dataKey="year" tick={axis} /><YAxis tick={axis} /><Tooltip /><Legend wrapperStyle={{ fontSize: 11 }} />
            {lines.types.map((t, i) => <Line key={t} dataKey={t} stroke={PALETTE[i % PALETTE.length]} dot={false} strokeWidth={2} />)}</LineChart></ResponsiveContainer></div></ChartCard>
        <ChartCard title="Emerging categories" sub={`Growth in share of reviews: ${trends.data.window.recent_years.join('–')} vs ${trends.data.window.baseline_years.join('–')}`}>
          <div className="h-80"><ResponsiveContainer><BarChart data={trends.data.emerging_categories} layout="vertical" margin={{ left: 40 }}><CartesianGrid stroke="#e5ddd0" horizontal={false} /><XAxis type="number" tick={axis} unit="%" /><YAxis type="category" dataKey="article_type" tick={axis} width={130} /><Tooltip />
            <Bar dataKey="growth_pct" fill="#b4532a" radius={[0, 6, 6, 0]} /></BarChart></ResponsiveContainer></div></ChartCard>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard title="Customer satisfaction by year" sub="Average review tone (−1 negative to +1 positive)"><div className="h-64"><ResponsiveContainer><LineChart data={sd.by_year.filter((r: any) => r.n > 500)}><CartesianGrid stroke="#e5ddd0" vertical={false} /><XAxis dataKey="year" tick={axis} /><YAxis domain={[0.3, 0.8]} tick={axis} /><Tooltip /><Line dataKey="mean" stroke="#4b6b57" strokeWidth={2.5} dot /></LineChart></ResponsiveContainer></div></ChartCard>
        <ChartCard title="Rising phrases in reviews" sub="Words and phrases showing up more in recent reviews">
          <ul className="grid grid-cols-1 gap-x-6 sm:grid-cols-2">{trends.data.emerging_terms.slice(0, 12).map((t: any) => <li key={t.term} className="flex justify-between border-t border-line py-1.5 text-sm"><span>{t.term}</span><span className="text-sage">×{t.lift}</span></li>)}</ul></ChartCard>
      </div>
    </div>)}

  </div>
}
