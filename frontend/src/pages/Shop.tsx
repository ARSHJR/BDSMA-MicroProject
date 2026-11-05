import { useSearchParams } from 'react-router-dom'
import { Search, SlidersHorizontal } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, qs } from '../api'
import { useFetch } from '../hooks'
import type { Card, Facets } from '../types'
import { ProductCard } from '../components/ProductCard'
import { Empty, ErrorBox, Loading, PageHead } from '../components/ui'

interface Listing { total: number; page: number; page_size: number; items: Card[] }
const SORTS = [['popular', 'Most reviewed'], ['rating', 'Top rated'], ['sustainability', 'Built to last'], ['price_asc', 'Price: low → high'], ['price_desc', 'Price: high → low'], ['newest', 'Newest']]

export default function Shop() {
  const [sp, setSp] = useSearchParams()
  const get = (k: string) => sp.get(k) ?? ''
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); if (v) n.set(k, v); else n.delete(k); if (k !== 'page') n.delete('page'); setSp(n) }
  const [q, setQ] = useState(get('q'))
  useEffect(() => { const t = setTimeout(() => q !== get('q') && set('q', q), 350); return () => clearTimeout(t) }, [q]) // eslint-disable-line
  const [openF, setOpenF] = useState(false)
  const facets = useFetch(() => api<Facets>('/api/facets'), [])
  const page = Number(get('page') || 1)
  const params = { q: get('q'), category_group: get('category_group'), article_type: get('article_type'), gender: get('gender'), colour: get('colour'),
    brand: get('brand'), max_price: get('max_price'), priced_only: get('priced_only') === '1', min_sustainability: get('min_sustainability'), sort: get('sort') || 'popular', page, page_size: 24 }
  const list = useFetch(() => api<Listing>('/api/products' + qs(params)), [sp.toString()])
  const pages = list.data ? Math.ceil(list.data.total / list.data.page_size) : 0
  const f = facets.data

  const Select = ({ k, label, opts }: { k: string; label: string; opts?: { value: string; count?: number }[] }) =>
    <label className="block text-xs font-medium uppercase tracking-wider text-mute">{label}
      <select aria-label={label} className="input mt-1 !rounded-xl normal-case tracking-normal" value={get(k)} onChange={e => set(k, e.target.value)}>
        <option value="">All</option>{opts?.map(o => <option key={o.value} value={o.value}>{o.value}{o.count ? ` (${o.count.toLocaleString()})` : ''}</option>)}</select></label>

  return <div>
    <PageHead eyebrow="Catalogue" title="Shop the edit" sub={list.data ? `${list.data.total.toLocaleString()} pieces` : 'Real products from the Amazon Fashion dataset'} />
    <div className="mb-6 flex flex-wrap gap-3">
      <div className="relative min-w-[240px] flex-1"><Search size={16} className="absolute left-4 top-3 text-mute" />
        <input className="input !pl-10" placeholder="Search dresses, leather, Levi’s…" aria-label="Search products" value={q} onChange={e => setQ(e.target.value)} /></div>
      <select aria-label="Sort" className="input !w-auto" value={get('sort') || 'popular'} onChange={e => set('sort', e.target.value)}>{SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
      <button className="btn-ghost lg:hidden" onClick={() => setOpenF(o => !o)}><SlidersHorizontal size={15} />Filters</button>
    </div>
    <div className="grid gap-8 lg:grid-cols-[230px_1fr]">
      <aside className={`${openF ? 'block' : 'hidden'} space-y-4 lg:block`} aria-label="Filters">
        <Select k="category_group" label="Group" opts={f?.category_group} />
        <Select k="article_type" label="Type" opts={f?.article_type} />
        <Select k="gender" label="For" opts={f?.gender} />
        <Select k="colour" label="Colour" opts={f?.colour} />
        <Select k="brand" label="Brand" opts={f?.brand} />
        <label className="block text-xs font-medium uppercase tracking-wider text-mute">Max price ($)
          <input className="input mt-1 !rounded-xl" type="number" min={0} placeholder="any" value={get('max_price')} onChange={e => set('max_price', e.target.value)} /></label>
        <label className="block text-xs font-medium uppercase tracking-wider text-mute">Min. durability rating: {get('min_sustainability') || 0}
          <input type="range" min={0} max={90} step={5} className="mt-2 w-full accent-[#4b6b57]" value={get('min_sustainability') || 0} onChange={e => set('min_sustainability', e.target.value === '0' ? '' : e.target.value)} /></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={get('priced_only') === '1'} onChange={e => set('priced_only', e.target.checked ? '1' : '')} />Only items with a listed price</label>
        {f && <p className="text-xs text-mute">Only {f.priced_products.toLocaleString()} of {f.total_products.toLocaleString()} products have a price in the source data.</p>}
        <button className="btn-ghost w-full" onClick={() => { setSp({}); setQ('') }}>Reset filters</button>
      </aside>
      <section>
        {list.error ? <ErrorBox message={list.error} onRetry={list.reload} /> : list.loading && !list.data ? <Loading rows={12} /> :
          list.data!.items.length === 0 ? <Empty title="Nothing matches" hint="Try removing a filter or searching a broader term." action={<button className="btn" onClick={() => { setSp({}); setQ('') }}>Clear filters</button>} /> :
            <>
              <div className={`grid grid-cols-2 gap-5 transition-opacity md:grid-cols-3 xl:grid-cols-4 ${list.loading ? 'opacity-50' : ''}`}>{list.data!.items.map(p => <ProductCard key={p.pid} p={p} />)}</div>
              <nav className="mt-10 flex items-center justify-center gap-4" aria-label="Pagination">
                <button className="btn-ghost" disabled={page <= 1} onClick={() => { set('page', String(page - 1)); window.scrollTo(0, 0) }}>← Prev</button>
                <span className="text-sm text-mute">Page {page} of {pages.toLocaleString()}</span>
                <button className="btn-ghost" disabled={page >= pages} onClick={() => { set('page', String(page + 1)); window.scrollTo(0, 0) }}>Next →</button></nav>
            </>}
      </section>
    </div>
  </div>
}
