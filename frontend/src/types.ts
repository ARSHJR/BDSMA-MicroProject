export interface Card {
  pid: number; title: string; brand: string; article_type: string; category_group: string; gender: string
  colour: string | null; price: number | null; avg_rating: number | null; n_ratings: number
  image: string; image_thumb: string; sustainability_score: number; sus_confidence: number
  similarity?: number; sustainability_gain?: number
}
export interface Reason { type: 'collaborative' | 'content' | 'preference' | 'sustainability' | 'popular'; text: string; source_pid?: number }
export interface RecItem extends Card { score: number; relevance: number; reasons: Reason[]; parts: Record<string, number> }
export interface RecResponse { mode: 'cold_start' | 'preferences' | 'personalised'; sustain: number; n_signals: number; latency_ms: number; items: RecItem[] }
export interface Facet { value: string; count: number }
export interface Facets { category_group: Facet[]; article_type: Facet[]; gender: Facet[]; colour: Facet[]; brand: Facet[]; price_range: [number, number]; priced_products: number; total_products: number }
export interface ProductDetail extends Card {
  asin: string; description: string; features: string; materials: string[]; natural_fibre: boolean; image_hires: string; n_text_reviews: number
  sustainability_breakdown: Record<string, number>; signals: Record<string, number>
  reviews: { sentiment: Record<string, number>; top_reviews: { rating: number; text: string; helpful_votes: number }[]; source: string }
  related: Card[]; longevity_alternatives: Card[]; already_saved_similar: Card[]
}
export interface Prefs { types: string[]; genders: string[]; colours: string[]; max_price: number | null; sustain: number }
export interface NV { name: string; value: number }
