// Bounded, in-memory ring of the most recent content events that passed through
// the tavern gateway. Tavern is otherwise stateless (it only fans out to Redis +
// WebSocket), so this gives the read-model (`GET /content/recent`) something real
// to serve for the dormant-safe proof panel — no fabricated data, just the last N
// events actually observed. Lost on restart, by design.

export interface ContentItem {
  content_type: string;
  content_id: string;
  text?: string;
  content?: unknown;
  metadata?: Record<string, unknown>;
  received_at: string;
}

export class ContentBuffer {
  private readonly items: ContentItem[] = [];

  constructor(private readonly max = 100) {}

  add(item: ContentItem): void {
    this.items.unshift(item); // newest first
    if (this.items.length > this.max) this.items.length = this.max;
  }

  recent(limit: number): ContentItem[] {
    return this.items.slice(0, Math.max(0, limit));
  }

  size(): number {
    return this.items.length;
  }
}
