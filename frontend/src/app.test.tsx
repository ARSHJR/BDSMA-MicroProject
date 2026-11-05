import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { UserProvider } from './UserContext'
import { ProductCard } from './components/ProductCard'
import { SafeImage } from './components/ui'
import ForYou from './pages/ForYou'
import type { Card, RecResponse } from './types'

const card = (pid: number, over: Partial<Card> = {}): Card => ({
  pid, title: `Test Dress ${pid}`, brand: 'Acme', article_type: 'Dresses', category_group: 'Clothing', gender: 'Women', colour: 'red',
  price: null, avg_rating: 4.5, n_ratings: 120, image: 'http://x/img.jpg', image_thumb: 'http://x/t.jpg', sustainability_score: 72, sus_confidence: 0.9, ...over,
})

let calls: { url: string; method: string; body?: string }[] = []
beforeEach(() => {
  calls = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, method: init?.method ?? 'GET', body: init?.body as string })
    const ok = (j: unknown) => ({ ok: true, status: 200, json: async () => j })
    if (url.startsWith('/api/reactions')) return ok({ reactions: {}, wishlist: [] })
    if (url.startsWith('/api/preferences')) return ok({ types: [], genders: [], colours: [], max_price: null, sustain: 0.3 })
    if (url.startsWith('/api/recommendations')) {
      const r: RecResponse = { mode: 'cold_start', sustain: 0.3, n_signals: 0, latency_ms: 4, items: [
        { ...card(1), score: 1, relevance: 1, parts: { content: 0, cf: 0, pref: 0, pop: 1 }, reasons: [{ type: 'popular', text: 'Popular pick: rated 4.5★ by 120 shoppers' }] }] }
      return ok(r)
    }
    return ok({ ok: true })
  }))
})
afterEach(cleanup)

describe('SafeImage', () => {
  it('shows a graceful fallback when the image URL is broken', () => {
    render(<SafeImage src="http://broken/x.jpg" alt="Broken dress" />)
    const img = screen.getByAltText('Broken dress')
    img.dispatchEvent(new Event('error'))
    return waitFor(() => expect(screen.getByText(/image unavailable/i)).toBeInTheDocument())
  })
  it('handles a missing src', () => {
    render(<SafeImage alt="none" />)
    expect(screen.getByText(/image unavailable/i)).toBeInTheDocument()
  })
})

describe('ProductCard', () => {
  it('renders price fallback and sends like + wishlist events to the API', async () => {
    render(<MemoryRouter><UserProvider><ProductCard p={card(7)} /></UserProvider></MemoryRouter>)
    expect(screen.getByText('Price n/a')).toBeInTheDocument()
    expect(screen.getByText('Test Dress 7')).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('Like'))
    await waitFor(() => expect(calls.some(c => c.url === '/api/interactions' && c.method === 'POST' && JSON.parse(c.body!).event === 'like')).toBe(true))
    expect(screen.getByLabelText('Like')).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByLabelText('Save to wishlist'))
    await waitFor(() => expect(calls.some(c => c.url === '/api/wishlist' && c.method === 'POST')).toBe(true))
    expect(screen.getByLabelText('Remove from wishlist')).toBeInTheDocument()
  })
})

describe('ForYou page', () => {
  it('shows cold-start mode, an explanation, and refetches when the sustainability slider moves', async () => {
    render(<MemoryRouter><UserProvider><ForYou /></UserProvider></MemoryRouter>)
    expect(await screen.findByText('Cold start')).toBeInTheDocument()
    expect(await screen.findByText(/Popular pick/)).toBeInTheDocument()
    const before = calls.filter(c => c.url.startsWith('/api/recommendations')).length
    const slider = screen.getByLabelText('Sustainability weight') as HTMLInputElement
    const { fireEvent } = await import('@testing-library/react')
    fireEvent.change(slider, { target: { value: '0.9' } })
    await waitFor(() => expect(calls.filter(c => c.url.startsWith('/api/recommendations')).length).toBeGreaterThan(before))
    expect(calls.at(-1)!.url).toContain('sustain=0.9')
  })
})
