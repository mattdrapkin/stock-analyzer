import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
});

export interface RateLimitErrorInfo {
  isRateLimit: boolean;
  limitType?: string;
  waitTime?: number;
  message: string;
}

export interface RateLimitError extends Error {
  rateLimitInfo?: RateLimitErrorInfo;
}

/**
 * Parse rate limit error details from an error message.
 * Extracts limit type and wait time if available.
 */
function parseRateLimitError(message: string): RateLimitErrorInfo {
  const lowerMessage = message.toLowerCase();
  
  // Check if it's a rate limit error
  const isRateLimit = lowerMessage.includes('rate limit') || 
                      lowerMessage.includes('rate_limit_exceeded') ||
                      lowerMessage.includes('quota exceeded') ||
                      lowerMessage.includes('too many requests');
  
  if (!isRateLimit) {
    return { isRateLimit: false, message };
  }
  
  // Extract limit type
  let limitType: string | undefined;
  if (lowerMessage.includes('rpm') || lowerMessage.includes('requests per minute')) {
    limitType = 'rpm';
  } else if (lowerMessage.includes('rpd') || lowerMessage.includes('requests per day')) {
    limitType = 'rpd';
  } else if (lowerMessage.includes('tpm') || lowerMessage.includes('tokens per minute')) {
    limitType = 'tpm';
  } else if (lowerMessage.includes('token') && lowerMessage.includes('limit')) {
    limitType = 'token';
  } else if (lowerMessage.includes('quota')) {
    limitType = 'quota';
  }
  
  // Extract wait time (in seconds)
  let waitTime: number | undefined;
  const secondsMatch = message.match(/(\d+\.?\d*)\s*seconds?/i);
  if (secondsMatch) {
    waitTime = parseFloat(secondsMatch[1]);
  } else {
    const minutesMatch = message.match(/(\d+\.?\d*)\s*minutes?/i);
    if (minutesMatch) {
      waitTime = parseFloat(minutesMatch[1]) * 60;
    } else {
      const hoursMatch = message.match(/(\d+\.?\d*)\s*hours?/i);
      if (hoursMatch) {
        waitTime = parseFloat(hoursMatch[1]) * 3600;
      }
    }
  }
  
  return {
    isRateLimit: true,
    limitType,
    waitTime,
    message
  };
}

export interface NewsArticle {
  title: string;
  source: string;
  url?: string;
  published_at?: string;
  summary?: string;
  category: 'company' | 'competitor' | 'macro';
}

export interface NewsSearchSummary {
  category: 'company' | 'competitor' | 'macro';
  ai_summary: string;
  sources: string[];
  search_queries: string[];
}

export interface NewsCard {
  title: string;
  summary: string;
  date?: string;
  source_name?: string;
  url?: string;
  category: 'company' | 'competitor' | 'macro';
  relevance?: string;
  swing_pct?: number;
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
  news_summaries: NewsSearchSummary[];
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
  batch_news_summaries: NewsSearchSummary[];
  batch_news_cards: NewsCard[];
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

export interface BasketTickerResult {
  ticker: string;
  company_name?: string;
  sector?: string;
  industry?: string;
  start_price: number;
  end_price: number;
  total_change_pct: number;
  direction: 'up' | 'down';
  news_cards: NewsCard[];
}

export interface BasketAnalysisResponse {
  tickers: string[];
  period_start: string;
  period_end: string;
  results: BasketTickerResult[];
  total_analyzed: number;
  holistic_summary?: string;
  news_source: string;
}

export interface FunFactsRequest {
  ticker?: string;
  basket?: string[];
}

export interface FunFactsResponse {
  facts: string[];
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
    try {
      const response = await api.get<TickerAnalysis>(`/analysis/${ticker}`, { 
        params 
      });
      return response.data;
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'response' in error) {
        const err = error as { response?: { status?: number; data?: { detail?: string } } };
        if (err.response?.status === 429) {
          const message = err.response.data?.detail || 'Rate limit reached. Please wait a moment before trying again.';
          const rateLimitInfo = parseRateLimitError(message);
          const enhancedError = new Error(message, { cause: error }) as RateLimitError;
          enhancedError.rateLimitInfo = rateLimitInfo;
          throw enhancedError;
        }
      }
      throw error;
    }
  },

  chat: async (ticker: string, data: {
    message: string;
    history?: ChatMessage[];
    context_days?: number;
    min_movement_pct?: number;
    include_competitors?: boolean;
    include_macro?: boolean;
  }) => {
    try {
      const response = await api.post<ChatResponse>(`/chat/${ticker}`, data);
      return response.data;
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'response' in error) {
        const err = error as { response?: { status?: number; data?: { detail?: string } } };
        if (err.response?.status === 429) {
          const message = err.response.data?.detail || 'Rate limit reached. Please wait a moment before trying again.';
          const rateLimitInfo = parseRateLimitError(message);
          const enhancedError = new Error(message, { cause: error }) as RateLimitError;
          enhancedError.rateLimitInfo = rateLimitInfo;
          throw enhancedError;
        }
      }
      throw error;
    }
  },

  checkHealth: async () => {
    const response = await api.get('/health');
    return response.data;
  },

  analyzeBasket: async (data: {
    tickers: string[];
    start_date: string;
    end_date: string;
    include_news?: boolean;
    include_competitors?: boolean;
    include_macro?: boolean;
  }) => {
    try {
      const { include_news, include_competitors, include_macro, ...bodyData } = data;
      const response = await api.post<BasketAnalysisResponse>('/basket', bodyData, {
        params: {
          include_news,
          include_competitors,
          include_macro,
        }
      });
      return response.data;
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'response' in error) {
        const err = error as { response?: { status?: number; data?: { detail?: string } } };
        if (err.response?.status === 429) {
          const message = err.response.data?.detail || 'Rate limit reached. Please wait a moment before trying again.';
          const rateLimitInfo = parseRateLimitError(message);
          const enhancedError = new Error(message, { cause: error }) as RateLimitError;
          enhancedError.rateLimitInfo = rateLimitInfo;
          throw enhancedError;
        }
      }
      throw error;
    }
  },

  getFunFacts: async (data: FunFactsRequest) => {
    try {
      const response = await api.post<FunFactsResponse>('/fun-facts', data);
      return response.data;
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'response' in error) {
        const err = error as { response?: { status?: number; data?: { detail?: string } } };
        if (err.response?.status === 429) {
          const message = err.response.data?.detail || 'Rate limit reached. Please wait a moment before trying again.';
          const rateLimitInfo = parseRateLimitError(message);
          const enhancedError = new Error(message, { cause: error }) as RateLimitError;
          enhancedError.rateLimitInfo = rateLimitInfo;
          throw enhancedError;
        }
      }
      throw error;
    }
  },

  downloadAnalysisPdf: async (ticker: string, params?: {
    start_date?: string;
    end_date?: string;
    min_movement_pct?: number;
    include_competitors?: boolean;
    include_macro?: boolean;
    max_articles?: number;
  }) => {
    try {
      const response = await api.get(`/analysis/${ticker}/pdf`, {
        params,
        responseType: 'blob',
      });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      
      // Extract filename from Content-Disposition header if available
      const contentDisposition = response.headers['content-disposition'];
      let filename = `${ticker}_analysis.pdf`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }
      
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'response' in error) {
        const err = error as { response?: { status?: number; data?: { detail?: string } } };
        if (err.response?.status === 429) {
          const message = err.response.data?.detail || 'Rate limit reached. Please wait a moment before trying again.';
          const rateLimitInfo = parseRateLimitError(message);
          const enhancedError = new Error(message, { cause: error }) as RateLimitError;
          enhancedError.rateLimitInfo = rateLimitInfo;
          throw enhancedError;
        }
      }
      throw error;
    }
  },

  downloadBasketPdf: async (data: {
    tickers: string[];
    start_date: string;
    end_date: string;
    include_news?: boolean;
    include_competitors?: boolean;
    include_macro?: boolean;
  }) => {
    try {
      const { include_news, include_competitors, include_macro, ...bodyData } = data;
      const response = await api.post('/basket/pdf', bodyData, {
        params: {
          include_news,
          include_competitors,
          include_macro,
        },
        responseType: 'blob',
      });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      
      // Extract filename from Content-Disposition header if available
      const contentDisposition = response.headers['content-disposition'];
      let filename = 'basket_analysis.pdf';
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }
      
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'response' in error) {
        const err = error as { response?: { status?: number; data?: { detail?: string } } };
        if (err.response?.status === 429) {
          const message = err.response.data?.detail || 'Rate limit reached. Please wait a moment before trying again.';
          const rateLimitInfo = parseRateLimitError(message);
          const enhancedError = new Error(message, { cause: error }) as RateLimitError;
          enhancedError.rateLimitInfo = rateLimitInfo;
          throw enhancedError;
        }
      }
      throw error;
    }
  }
};
