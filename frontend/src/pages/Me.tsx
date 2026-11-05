import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Check } from 'lucide-react'
import { api } from '../api'
import { useFetch } from '../hooks'
import { useUser } from '../UserContext'
import type { Card, Facets, Prefs } from '../types'
import { ProductCard } from '../components/ProductCard'
import { Empty, ErrorBox, PageHead } from '../components/ui'

const TYPES = ['Dresses', 'Tops & T-Shirts', 'Jeans', 'Pants & Leggings', 'Jackets & Coats', 'Hoodies & Sweaters', 'Shorts & Skirts', 'Sneakers', 'Boots', 'Sandals', 'Jewellery', 'Watches', 'Bags & Wallets', 'Sunglasses & Eyewear', 'Scarves & Gloves', 'Hats & Caps']
const GENDERS = ['Women', 'Men', 'Girls', 'Boys', 'Unisex']
const COLOURS = ['black', 'white', 'grey', 'navy', 'blue', 'red', 'pink', 'green', 'brown', 'beige', 'gold', 'silver']

function Chips({ options, value, onChange, label }: { options: string[]; value: string[]; onChange: (v: string[]) => void; label: string }) {
  return <fieldset><legend className="mb-2 text-sm font-medium">{label}</legend><div className="flex flex-wrap gap-2">
    {options.map(o => { const on = value.includes(o); return <button type="button" key={o} aria-pressed={on} onClick={() => onChange(on ? value.filter(x => x !== o) : [...value, o])}
      className={`pill !px-3.5 !py-1.5 !text-sm ${on ? '!border-ink !bg-ink !text-paper' : 'hover:border-ink'}`}>{on && <Check size={13} />}{o}</button> })}</div></fieldset>
}

export default function Me() {
  const { prefs, savePrefs, wishlist, version } = useUser()
  const [form, setForm] = useState<Prefs>({ types: [], genders: [], colours: [], max_price: null, sustain: 0.3 })
  const [saved, setSaved] = useState(false)
  const [err, setErr] = useState('')
  const facets = useFetch(() => api<Facets>('/api/facets'), [])
  useEffect(() => { if (prefs) setForm(prefs) }, [prefs])
  const wl = useFetch(() => api<{ items: Card[] }>('/api/wishlist'), [wishlist.length, version])
  const submit = async () => { try { setErr(''); await savePrefs(form); setSaved(true); setTimeout(() => setSaved(false), 2500) } catch (e) { setErr((e as Error).message) } }
  return <div className="space-y-14">
    <PageHead eyebrow="My style" title="Your preferences" sub="A 30-second onboarding that solves the cold-start problem. Preferences are stored against an anonymous guest session (no account needed)." />
    <section className="space-y-7 rounded-3xl border border-line bg-card p-7">
      <Chips label="What do you like to wear?" options={TYPES} value={form.types} onChange={types => setForm({ ...form, types })} />
      <Chips label="Shopping for" options={GENDERS} value={form.genders} onChange={genders => setForm({ ...form, genders })} />
      <Chips label="Favourite colours" options={COLOURS} value={form.colours} onChange={colours => setForm({ ...form, colours })} />
      <div className="grid gap-6 md:grid-cols-2">
        <label className="block text-sm font-medium">Budget ceiling (optional, $)
          <input className="input mt-2" type="number" min={1} placeholder="no limit" value={form.max_price ?? ''} onChange={e => setForm({ ...form, max_price: e.target.value ? Number(e.target.value) : null })} />
          <span className="mt-1 block text-xs font-normal text-mute">Only {facets.data?.priced_products.toLocaleString() ?? '…'} products carry a price; others are never excluded by budget, just not boosted.</span></label>
        <label className="block text-sm font-medium">How much should longevity matter? <span className="font-display text-lg">{Math.round(form.sustain * 100)}%</span>
          <input type="range" aria-label="Sustainability preference" min={0} max={1} step={0.05} className="mt-3 w-full accent-[#4b6b57]" value={form.sustain} onChange={e => setForm({ ...form, sustain: Number(e.target.value) })} /></label>
      </div>
      {err && <ErrorBox message={err} />}
      <div className="flex items-center gap-4"><button className="btn" onClick={submit}>Save &amp; update my picks</button>
        {saved && <span className="flex items-center gap-1 text-sm text-sage" role="status"><Check size={15} />Saved — <Link to="/for-you" className="underline">see your picks</Link></span>}</div>
    </section>
    <section>
      <h2 className="text-3xl">Wishlist <span className="text-lg text-mute">({wishlist.length})</span></h2>
      <p className="mb-5 text-sm text-mute">Saved items count as strong positive signals — and the product page will tell you when a new item resembles something you already saved.</p>
      {wl.error ? <ErrorBox message={wl.error} onRetry={wl.reload} /> : !wl.data || wl.data.items.length === 0 ?
        <Empty title="Your wishlist is empty" hint="Tap the heart on any product to save it." action={<Link to="/shop" className="btn">Browse catalogue</Link>} /> :
        <div className="grid grid-cols-2 gap-5 md:grid-cols-4">{wl.data.items.map(p => <ProductCard key={p.pid} p={p} />)}</div>}
    </section>
  </div>
}
