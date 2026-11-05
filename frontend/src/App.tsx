import { BrowserRouter, Link, NavLink, Route, Routes } from 'react-router-dom'
import { useState } from 'react'
import { Heart, Menu, X } from 'lucide-react'
import { UserProvider, useUser } from './UserContext'
import Home from './pages/Home'
import Shop from './pages/Shop'
import Product from './pages/Product'
import ForYou from './pages/ForYou'
import Trends from './pages/Trends'
import Sustainability from './pages/Sustainability'
import Me from './pages/Me'
import Insights from './pages/Insights'

const LINKS = [
  ['/shop', 'Shop'], ['/for-you', 'For you'], ['/trends', 'Trends'], ['/sustainability', 'Sustainability'],
] as const

function Nav() {
  const { wishlist } = useUser()
  const [open, setOpen] = useState(false)
  const cls = ({ isActive }: { isActive: boolean }) => `text-sm transition-colors hover:text-accent ${isActive ? 'font-semibold text-ink' : 'text-mute'}`
  return <header className="sticky top-0 z-30 border-b border-line bg-paper/90 backdrop-blur">
    <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
      <Link to="/" className="font-display text-2xl tracking-tight">Thread<span className="text-accent">.</span></Link>
      <nav className="hidden items-center gap-7 md:flex" aria-label="Main">{LINKS.map(([to, l]) => <NavLink key={to} to={to} className={cls}>{l}</NavLink>)}</nav>
      <div className="flex items-center gap-3">
        <Link to="/me" className="pill hover:border-ink" aria-label="My wishlist and preferences"><Heart size={14} />My style{wishlist.length > 0 && <span className="rounded-full bg-accent px-1.5 text-[10px] text-white">{wishlist.length}</span>}</Link>
        <button className="md:hidden" aria-label="Menu" onClick={() => setOpen(o => !o)}>{open ? <X /> : <Menu />}</button>
      </div>
    </div>
    {open && <nav className="flex flex-col gap-4 border-t border-line px-5 py-4 md:hidden" onClick={() => setOpen(false)}>{LINKS.map(([to, l]) => <NavLink key={to} to={to} className={cls}>{l}</NavLink>)}</nav>}
  </header>
}

export default function App() {
  return <BrowserRouter><UserProvider>
    <Nav />
    <main className="mx-auto max-w-7xl px-5 py-10">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/shop" element={<Shop />} />
        <Route path="/product/:pid" element={<Product />} />
        <Route path="/for-you" element={<ForYou />} />
        <Route path="/trends" element={<Trends />} />
        <Route path="/sustainability" element={<Sustainability />} />
        <Route path="/me" element={<Me />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="*" element={<p className="py-20 text-center text-mute">Page not found. <Link className="underline" to="/">Go home</Link></p>} />
      </Routes>
    </main>
    <footer className="border-t border-line py-8 text-center text-xs text-mute">
      © Thread · Fashion made to last · <Link to="/insights" className="underline-offset-2 hover:underline">About our data</Link>
    </footer>
  </UserProvider></BrowserRouter>
}
