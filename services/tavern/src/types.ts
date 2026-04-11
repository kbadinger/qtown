export interface LeaderboardEntry {
  npcId: string;
  score: number;
  rank: number;
}

export interface TownEvent {
  type: string;
  data: Record<string, unknown>;
  timestamp: number;
  source: string;
}

export interface WebSocketMessage {
  channel: string;
  event: TownEvent;
}
