import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { useFetch } from '../hooks'
import { ChartCard, ErrorBox, PageHead, PALETTE, Spinner, Stat } from '../components/ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
const axis = { fontSize: 11, fill: '#6f675d' }
const SENT_COL: Record<string, string> = { positive: '#4b6b57', neutral: '#b08a2e', negative: '#b4532a' }

export default function Insights() {
  const dash = useFetch(() => api<any>('/api/dashboard'), [])
  const ev = useFetch(() => api<any>('/api/evaluation'), [])
  const ds = useFetch(() => api<any>('/api/datasets'), [])
  if (dash.error || ev.error || ds.error) return <ErrorBox message={dash.error || ev.error || ds.error || ''} onRetry={() => { dash.reload(); ev.reload(); ds.reload() }} />
  if (!dash.data || !ev.data || !ds.data) return <Spinner />
  const d = dash.data, e = ev.data, q = ds.data.quality_report
  const models = Object.entries(e.models).map(([name, m]: any) => ({ name, ...m }))
  const best = Math.max(...models.map((m: any) => m['ndcg@k']))
  const sent = Object.entries(d.sentiment).map(([name, value]) => ({ name, value }))
  const cmp = models.filter((m: any) => m.name !== 'Random').map((m: any) => ({ name: m.name.split(' (')[0], 'NDCG@10': +m['ndcg@k'].toFixed(4), 'Recall@10': +m['recall@k'].toFixed(4), 'Coverage': +m.coverage.toFixed(3) }))
  return <div className="space-y-14">
    <PageHead eyebrow="Transparency" title="Model & dataset insights" sub="Every number on this page is computed by the pipeline from the processed data — nothing is hard-coded." />

    <section><h2 className="mb-4 text-3xl">Dataset</h2>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4"><Stat label="Raw products" value={d.dataset.raw_products} /><Stat label="Raw reviews" value={d.dataset.raw_reviews} />
        <Stat label="Catalogue (after cleaning + k-core)" value={d.dataset.products} /><Stat label="Interactions" value={d.dataset.interactions} hint={`${d.dataset.users.toLocaleString()} users · sparsity ${d.dataset.sparsity_pct}%`} /></div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">{ds.data.sources.map((s: any) => <div key={s.name} className="rounded-2xl border border-line bg-card p-5 text-sm"><p className="font-medium">{s.name}</p>
        {s.url && <a className="text-accent underline" href={s.url} target="_blank" rel="noreferrer">{s.url}</a>}<p className="mt-1 text-mute"><b>Why:</b> {s.why}</p><p className="mt-1 text-mute"><b>Licence:</b> {s.license}</p></div>)}</div>
      <details className="mt-4 rounded-2xl border border-line bg-card p-5 text-sm"><summary className="cursor-pointer font-medium">Data-quality report</summary>
        <pre className="mt-3 overflow-x-auto text-xs text-mute">{JSON.stringify(q, null, 2)}</pre></details>
      {ds.data.benchmark && <details className="mt-3 rounded-2xl border border-line bg-card p-5 text-sm"><summary className="cursor-pointer font-medium">Processing benchmark (pandas vs DuckDB)</summary><pre className="mt-3 overflow-x-auto text-xs text-mute">{JSON.stringify(ds.data.benchmark, null, 2)}</pre></details>}
    </section>

    <section><h2 className="mb-4 text-3xl">Analytics dashboard</h2>
      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard title="Products by category" sub="Derived from title keywords (documented rules)"><div className="h-80"><ResponsiveContainer><BarChart data={d.by_category.slice(0, 14)} layout="vertical" margin={{ left: 40 }}><CartesianGrid stroke="#e5ddd0" horizontal={false} /><XAxis type="number" tick={axis} /><YAxis type="category" dataKey="name" width={130} tick={axis} /><Tooltip /><Bar dataKey="value" fill="#1a1612" radius={[0, 6, 6, 0]} /></BarChart></ResponsiveContainer></div></ChartCard>
        <ChartCard title="Price distribution" sub={d.price_note}><div className="h-80"><ResponsiveContainer><BarChart data={d.price_distribution}><CartesianGrid stroke="#e5ddd0" vertical={false} /><XAxis dataKey="name" tick={axis} /><YAxis tick={axis} /><Tooltip /><Bar dataKey="value" fill="#b4532a" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div></ChartCard>
        <ChartCard title="Most represented brands"><div className="h-80"><ResponsiveContainer><BarChart data={d.top_brands} layout="vertical" margin={{ left: 50 }}><CartesianGrid stroke="#e5ddd0" horizontal={false} /><XAxis type="number" tick={axis} /><YAxis type="category" dataKey="name" width={140} tick={axis} /><Tooltip /><Bar dataKey="value" fill="#6f675d" radius={[0, 6, 6, 0]} /></BarChart></ResponsiveContainer></div></ChartCard>
        <ChartCard title="Review sentiment" sub="VADER over all catalogue reviews"><div className="h-80"><ResponsiveContainer><PieChart><Pie data={sent} dataKey="value" nameKey="name" innerRadius={70} outerRadius={110} paddingAngle={2} label>{sent.map(s => <Cell key={s.name} fill={SENT_COL[s.name]} />)}</Pie><Tooltip /><Legend /></PieChart></ResponsiveContainer></div></ChartCard>
        <ChartCard title="Longevity-proxy distribution" sub="Share of catalogue per score band"><div className="h-72"><ResponsiveContainer><BarChart data={d.sustainability_distribution}><CartesianGrid stroke="#e5ddd0" vertical={false} /><XAxis dataKey="name" tick={axis} /><YAxis tick={axis} /><Tooltip /><Bar dataKey="value" fill="#4b6b57" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div></ChartCard>
        <ChartCard title="Gender / audience split"><div className="h-72"><ResponsiveContainer><PieChart><Pie data={d.by_gender} dataKey="value" nameKey="name" outerRadius={100} label>{d.by_gender.map((_: any, i: number) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></div></ChartCard>
      </div>
      <p className="mt-3 text-xs text-mute">Live app usage (this install): {d.app_usage.sessions} sessions · {d.app_usage.events} view events · {d.app_usage.reactions} likes/dislikes · {d.app_usage.wishlist_items} wishlist items.</p>
    </section>

    <section><h2 className="mb-2 text-3xl">Recommender evaluation</h2>
      <p className="mb-4 max-w-3xl text-sm text-mute">{e.protocol}</p>
      <div className="grid gap-4 md:grid-cols-4"><Stat label="Evaluation users" value={e.test_info.n_eval_users} /><Stat label="Online latency (mean)" value={`${e.online_latency_ms.mean.toFixed(1)} ms`} hint={`p95 ${e.online_latency_ms.p95.toFixed(1)} ms`} />
        <Stat label="Tuned weights" value={`${e.best_weights.content}/${e.best_weights.cf}/${e.best_weights.pop}`} hint="content / CF / popularity" /><Stat label="Unseen-in-train test items" value={`${e.test_info.test_item_unseen_in_train_pct}%`} hint="cold items" /></div>
      <div className="mt-6 overflow-x-auto rounded-3xl border border-line bg-card"><table className="w-full text-sm"><thead><tr className="text-left text-xs uppercase tracking-wider text-mute">
        {['Model', 'Precision@10', 'Recall@10', 'NDCG@10', 'Coverage', 'Diversity (ILD)', 'ms/user'].map(h => <th key={h} className="px-4 py-3">{h}</th>)}</tr></thead>
        <tbody>{models.map((m: any) => <tr key={m.name} className={`border-t border-line ${m['ndcg@k'] === best ? 'bg-sage-soft/50 font-medium' : ''}`}><td className="px-4 py-3">{m.name}</td>
          <td className="px-4">{m['precision@k'].toFixed(4)}</td><td>{m['recall@k'].toFixed(4)}</td><td>{m['ndcg@k'].toFixed(4)}</td><td>{(100 * m.coverage).toFixed(1)}%</td><td>{m.diversity_ild.toFixed(3)}</td><td>{m.ms_per_user_batch}</td></tr>)}</tbody></table></div>
      <div className="mt-6"><ChartCard title="Accuracy vs. catalogue coverage" sub="Popularity is a hard-to-beat baseline on sparse review data, but it recommends the same few items to everyone (see coverage).">
        <div className="h-72"><ResponsiveContainer><BarChart data={cmp}><CartesianGrid stroke="#e5ddd0" vertical={false} /><XAxis dataKey="name" tick={axis} /><YAxis tick={axis} /><Tooltip /><Legend /><Bar dataKey="NDCG@10" fill="#1a1612" radius={[4, 4, 0, 0]} /><Bar dataKey="Recall@10" fill="#b4532a" radius={[4, 4, 0, 0]} /><Bar dataKey="Coverage" fill="#4b6b57" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></ChartCard></div>
      <ul className="mt-4 list-disc space-y-1 pl-5 text-xs text-mute">{e.caveats.map((c: string) => <li key={c}>{c}</li>)}</ul>
    </section>
    <section className="rounded-3xl border border-line bg-card p-7"><h2 className="text-2xl">How the hybrid works</h2>
      <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-mute">
        <li><b className="text-ink">Content</b>: TF-IDF (1–2-grams) on title/features/description + weighted one-hots (type, gender, colour) → cosine; top-40 neighbours per item.</li>
        <li><b className="text-ink">Collaborative</b>: item-item cosine with shrinkage on the user–item matrix built only from past interactions.</li>
        <li><b className="text-ink">Profile scoring</b>: score(j) = Σᵢ wᵢ · sim(i, j) over your liked/saved/viewed items (dislikes subtract).</li>
        <li><b className="text-ink">Cold start</b>: onboarding preferences + Bayesian popularity prior.</li>
        <li><b className="text-ink">Re-ranking</b>: (1−λ)·relevance + λ·longevity proxy, then MMR diversification, then a reason is attached from the true top contributing signal.</li></ol></section>
  </div>
}
