import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
});

export interface NewsArticle {
  title: string;
  source: string;
  url?: string;
  published_at?: string;
  summary?: string;
  category: 'company' | 'competitor' | 'macro';
}

export interface StockMovement {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
  change_pct: number;
  direction: 'up' | 'down';
  news: NewsArticle[];
}

export interface TickerAnalysis {
  ticker: string;
  company_name?: string;
  sector?: string;
  industry?: string;
  period_start: string;
  period_end: string;
  min_movement_pct: number;
  total_movements: number;
  up_movements: number;
  down_movements: number;
  movements: StockMovement[];
  news_source: string;
  news_note?: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  response: string;
  ticker: string;
  movements_analyzed: number;
  context_used: boolean;
}

export const stockApi = {
  getAnalysis: async (ticker: string, params?: {
    start_date?: string;
    end_date?: string;
    min_movement_pct?: number;
    include_competitors?: boolean;
    include_macro?: boolean;
    max_articles?: number;
    use_mock?: boolean;
  }) => {
    const response = await api.get<TickerAnalysis>(`/analysis/${ticker}`, { 
      params 
    });
    return response.data;
  },

  chat: async (ticker: string, data: {
    message: string;
    history?: ChatMessage[];
    context_days?: number;
    min_movement_pct?: number;
    include_competitors?: boolean;
    include_macro?: boolean;
  }) => {
    const response = await api.post<ChatResponse>(`/chat/${ticker}`, data);
    return response.data;
  },

  checkHealth: async () => {
    const response = await api.get('/health');
    return response.data;
  }
};
