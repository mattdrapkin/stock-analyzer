import React, { useState, useRef } from 'react';
import ReactDatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import {
  Search,
  TrendingUp,
  TrendingDown,
  Calendar,
  Info,
  ExternalLink,
  ChevronDown,
  Loader2,
  AlertCircle,
  X,
  Layers,
  Newspaper,
  Download,
  BarChart3
} from 'lucide-react';
import { stockApi } from './api';
import type { TickerAnalysis, StockMovement, NewsCard, BasketAnalysisResponse, BasketTickerResult, PriceHistoryResponse } from './api';
import { format } from 'date-fns';
import HeaderNavigation, { type Section } from './components/HeaderNavigation';
import LoadingScreen from './components/LoadingScreen';
import StockChart from './components/StockChart';
import AILoadingBar from './components/AILoadingBar';
import BasketAnalytics from './components/BasketAnalytics';
import { DEFAULT_BASKETS } from './constants/defaultBaskets';

// Collapsible Section Component
interface CollapsibleSectionProps {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
  badge?: string;
  className?: string;
}

const CollapsibleSection: React.FC<CollapsibleSectionProps> = ({ 
  title, 
  icon: Icon, 
  expanded, 
  onToggle, 
  children, 
  badge,
  className = ''
}) => {
  return (
    <div className={`bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden ${className}`}>
      <button
        onClick={onToggle}
        className="w-full py-3 px-4 md:py-3 md:px-6 flex items-center justify-between gap-4 hover:bg-slate-50 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <Icon className="text-indigo-600 w-5 h-5" />
          <h3 className="text-lg font-bold">{title}</h3>
          {badge && (
            <span className="text-xs font-normal text-slate-400 bg-slate-100 px-2.5 py-1 rounded-full">
              {badge}
            </span>
          )}
        </div>
        <div className={`p-2 rounded-full transition-transform ${expanded ? 'rotate-180 bg-slate-100' : 'text-slate-400'}`}>
          <ChevronDown className="w-5 h-5" />
        </div>
      </button>
      {expanded && (
        <div className="px-4 pb-6 md:px-6 md:pb-8 border-t border-slate-50 pt-6">
          {children}
        </div>
      )}
    </div>
  );
};

const categoryConfig = {
  company: { bg: 'bg-indigo-50 text-indigo-700 border-indigo-100', label: 'Company' },
  competitor: { bg: 'bg-amber-50 text-amber-700 border-amber-100', label: 'Competitor' },
  macro: { bg: 'bg-emerald-50 text-emerald-700 border-emerald-100', label: 'Macro' },
} as const;

const NewsCardItem: React.FC<{ card: NewsCard }> = ({ card }) => {
  const cfg = categoryConfig[card.category] ?? { bg: 'bg-slate-50 text-slate-600 border-slate-100', label: card.category };

  // Parse markdown-style links in summary
  const renderSummaryWithLinks = (text: string) => {
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
    let match;

    while ((match = linkRegex.exec(text)) !== null) {
      // Add text before the link
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index));
      }
      // Add the link
      parts.push(
        <a
          key={match.index}
          href={match[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-indigo-600 hover:text-indigo-800 underline"
        >
          {match[1]}
        </a>
      );
      lastIndex = match.index + match[0].length;
    }
    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex));
    }
    return parts.length > 0 ? parts : text;
  };

  const inner = (
    <div className={`group h-full bg-white border border-slate-200 rounded-xl p-4 transition-all hover:shadow-md hover:border-indigo-200 flex flex-col gap-2 ${
      card.url ? 'cursor-pointer' : ''
    }`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${cfg.bg}`}>
            {cfg.label}
          </span>
          {card.source_name && (
            <span className="text-xs text-slate-400 font-medium">{card.source_name}</span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {card.swing_pct !== undefined && card.swing_pct !== null && (
            <span className={`text-xs font-bold px-2 py-0.5 rounded ${
              card.swing_pct > 0
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : card.swing_pct < 0
                ? 'bg-rose-50 text-rose-700 border border-rose-200'
                : 'bg-slate-50 text-slate-600 border border-slate-200'
            }`}>
              {card.swing_pct > 0 ? '+' : ''}{card.swing_pct.toFixed(1)}%
            </span>
          )}
          {card.date && (
            <span className="text-xs text-slate-400 whitespace-nowrap flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              {card.date}
            </span>
          )}
        </div>
      </div>

      <h4 className={`font-semibold text-slate-900 leading-snug ${
        card.url ? 'group-hover:text-indigo-600 transition-colors' : ''
      }`}>
        {card.title}
        {card.url && (
          <ExternalLink className="w-3 h-3 inline ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
        )}
      </h4>

      <p className="text-sm text-slate-600 leading-relaxed flex-1">{renderSummaryWithLinks(card.summary)}</p>

      {card.relevance && (
        <p className="text-xs text-slate-400 italic border-t border-slate-100 pt-2 mt-auto">
          {card.relevance}
        </p>
      )}
    </div>
  );

  if (card.url) {
    return (
      <a href={card.url} target="_blank" rel="noopener noreferrer" className="block h-full">
        {inner}
      </a>
    );
  }
  return inner;
};

const MovementCard: React.FC<{ move: StockMovement; batchNewsCards?: NewsCard[] }> = ({ move, batchNewsCards }) => {
  const [expanded, setExpanded] = useState(false);
  const isUp = move.direction === 'up';

  // Filter news cards for this specific date (use local timezone to match backend)
  const moveDateStr = new Date(move.date).toLocaleDateString('en-CA');
  const cardsForDay = batchNewsCards?.filter(card => card.date === moveDateStr) || [];

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden transition-all hover:shadow-md">
      <div 
        className="p-4 md:p-6 cursor-pointer flex items-center justify-between gap-4"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-4">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 ${
            isUp ? 'bg-emerald-50 text-emerald-600' : 'bg-rose-50 text-rose-600'
          }`}>
            {isUp ? <TrendingUp className="w-6 h-6" /> : <TrendingDown className="w-6 h-6" />}
          </div>
          <div>
            <div className="text-sm text-slate-500 font-medium">
              {format(new Date(move.date), 'EEEE, MMMM d, yyyy')}
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-xl font-bold ${isUp ? 'text-emerald-600' : 'text-rose-600'}`}>
                {isUp ? '+' : ''}{Number(move.change_pct).toFixed(1)}%
              </span>
              <span className="text-slate-400 text-sm font-medium">
                ${Number(move.open).toFixed(2)} → ${Number(move.close).toFixed(2)}
              </span>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="hidden md:flex flex-col items-end">
            <span className="text-xs text-slate-400 uppercase font-bold tracking-wider">Volume</span>
            <span className="text-sm font-bold text-slate-700">{(move.volume / 1000000).toFixed(1)}M</span>
          </div>
          <div className={`p-2 rounded-full transition-transform ${expanded ? 'rotate-180 bg-slate-100' : 'text-slate-400'}`}>
            <ChevronDown className="w-5 h-5" />
          </div>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-6 md:px-6 md:pb-8 border-t border-slate-50 pt-6">
          <h4 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-4">Related News</h4>
          <div className="space-y-3">
            {cardsForDay.length > 0 ? (
              cardsForDay.map((card, j) => (
                <NewsCardItem key={j} card={card} />
              ))
            ) : (
              <div className="bg-slate-50 p-4 rounded-xl text-center border border-dashed border-slate-200">
                <p className="text-sm text-slate-400">No specific news articles found for this date.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const BasketResultCard: React.FC<{ result: BasketTickerResult; rank: number }> = ({ result, rank }) => {
  const isUp = result.direction === 'up';
  const [expanded, setExpanded] = useState(false);
  const hasNews = result.news_cards && result.news_cards.length > 0;
  
  return (
    <div className="bg-slate-50 rounded-xl overflow-hidden hover:bg-slate-100 transition-colors">
      <div 
        className="p-4 flex items-center gap-4 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 font-bold text-sm ${
          rank <= 3 ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-600'
        }`}>
          {rank}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-bold text-slate-900">{result.ticker}</span>
            {result.company_name && (
              <span className="text-sm text-slate-500 truncate">{result.company_name}</span>
            )}
            {hasNews && (
              <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full font-medium">
                {result.news_cards.length} news
              </span>
            )}
          </div>
          {(result.sector || result.industry) && (
            <div className="text-xs text-slate-400 mb-1">
              {result.sector && <span>{result.sector}</span>}
              {result.sector && result.industry && <span> • </span>}
              {result.industry && <span>{result.industry}</span>}
            </div>
          )}
          <div className="flex items-center gap-3 text-sm">
            <span className="text-slate-500">
              {result.start_price !== null ? `$${result.start_price.toFixed(2)}` : 'N/A'} → {result.end_price !== null ? `$${result.end_price.toFixed(2)}` : 'N/A'}
            </span>
          </div>
        </div>
        <div className={`text-right shrink-0`}>
          <div className={`text-xl font-bold ${isUp ? 'text-emerald-600' : 'text-rose-600'}`}>
            {result.total_change_pct !== null ? `${isUp ? '+' : ''}${result.total_change_pct.toFixed(1)}%` : 'N/A'}
          </div>
          <div className={`text-xs font-bold uppercase ${isUp ? 'text-emerald-500' : 'text-rose-500'}`}>
            {result.direction}
          </div>
        </div>
        <div className={`p-2 rounded-full transition-transform ${expanded ? 'rotate-180 bg-slate-200' : 'text-slate-400'}`}>
          <ChevronDown className="w-5 h-5" />
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-200 pt-4">
          <h4 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-3">Related News</h4>
          <div className="grid grid-cols-1 gap-3">
            {hasNews ? (
              result.news_cards.map((card, j) => (
                <NewsCardItem key={j} card={card} />
              ))
            ) : (
              <div className="bg-slate-50 p-4 rounded-xl text-center border border-dashed border-slate-200">
                <p className="text-sm text-slate-400">Loading news...</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// Helper function to format basket summary with bold tickers and color-coded percentages
const formatBasketSummary = (text: string, validTickers: string[]): React.ReactNode => {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;

  // Match ticker symbols with various formats:
  // - Simple: AAPL, MSFT (2-5 uppercase letters)
  // - With suffix: 2899.HK, RIO.L (letters/numbers + dot + letters)
  // Followed by optional percentage (requires % sign)
  const tickerRegex = /\b([A-Z]{2,5}(?:\.[A-Z]{1,3})?|[A-Z0-9]+\.[A-Z]{1,3})\b(?:\s*\(?([+-]?\d+\.?\d*)%\)?\s*)?/g;
  let match;

  while ((match = tickerRegex.exec(text)) !== null) {
    // Add text before the match
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    const ticker = match[1];
    const percentage = match[2];
    const matchedText = match[0];

    // Only highlight if it's a valid ticker in the basket
    if (validTickers.includes(ticker)) {
      // Render ticker as bold
      if (percentage) {
        const pctValue = parseFloat(percentage);
        // Handle NaN case
        if (!isNaN(pctValue)) {
          const colorClass = pctValue >= 0 ? 'text-emerald-600 font-bold' : 'text-rose-600 font-bold';
          // Check if there's trailing whitespace in the matched text
          const trailingSpace = matchedText.match(/\s+$/);
          parts.push(
            <span key={match.index}>
              <span className="font-bold">{ticker}</span>
              <span className={colorClass}> ({percentage}%)</span>
              {trailingSpace && <span>{trailingSpace[0]}</span>}
            </span>
          );
        } else {
          parts.push(<span key={match.index} className="font-bold">{ticker}</span>);
        }
      } else {
        parts.push(<span key={match.index} className="font-bold">{ticker}</span>);
      }
    } else {
      // Not a valid ticker, just add the matched text as-is
      parts.push(matchedText);
    }

    lastIndex = match.index + matchedText.length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  // Second pass: highlight standalone percentages (not attached to tickers)
  // This catches percentages like "+80.5%", "(+70.8%)", "(down 67.5%)"
  const processedParts: React.ReactNode[] = [];
  let partIndex = 0;

  for (const part of parts) {
    if (typeof part === 'string') {
      // Process string parts for standalone percentages
      const subParts: React.ReactNode[] = [];
      let subLastIndex = 0;
      // Match percentages with optional parentheses and "down" keyword
      // Matches: +80.5%, (70.8%), (-5.2%), (down 67.5%), etc.
      const pctRegex = /\(?\s*(?:down\s+)?([+-]?\d+\.?\d*)\s*%\s*\)?/g;
      let pctMatch;

      while ((pctMatch = pctRegex.exec(part)) !== null) {
        // Add text before the percentage
        if (pctMatch.index > subLastIndex) {
          subParts.push(part.slice(subLastIndex, pctMatch.index));
        }

        const pctValue = parseFloat(pctMatch[1]);
        const matchedPct = pctMatch[0];
        if (!isNaN(pctValue)) {
          const colorClass = pctValue >= 0 ? 'text-emerald-600 font-bold' : 'text-rose-600 font-bold';
          // Check if there's trailing whitespace in the matched text
          const trailingSpace = matchedPct.match(/\s+$/);
          subParts.push(
            <span key={`pct-${partIndex}-${pctMatch.index}`} className={colorClass}>
              {matchedPct.replace(/\s+$/, '')}
              {trailingSpace && <span>{trailingSpace[0]}</span>}
            </span>
          );
        } else {
          subParts.push(matchedPct);
        }

        subLastIndex = pctMatch.index + matchedPct.length;
      }

      // Add remaining text
      if (subLastIndex < part.length) {
        subParts.push(part.slice(subLastIndex));
      }

      processedParts.push(...subParts);
    } else {
      // Already a React element, keep as-is
      processedParts.push(part);
    }
    partIndex++;
  }

  return processedParts.length > 0 ? processedParts : text;
};

// Helper function to parse basket summary into broad theme and detailed analysis
const parseBasketSummary = (text: string, validTickers: string[]): { broadTheme: React.ReactNode; detailedAnalysis: React.ReactNode } => {
  const paragraphs = text.split('\n\n').filter(p => p.trim());
  
  if (paragraphs.length === 0) {
    return { broadTheme: null, detailedAnalysis: null };
  }
  
  if (paragraphs.length === 1) {
    return {
      broadTheme: formatBasketSummary(paragraphs[0], validTickers),
      detailedAnalysis: null
    };
  }
  
  // First paragraph is broad theme, rest is detailed analysis
  return {
    broadTheme: formatBasketSummary(paragraphs[0], validTickers),
    detailedAnalysis: formatBasketSummary(paragraphs.slice(1).join('\n\n'), validTickers)
  };
};

const App: React.FC = () => {
  const [ticker, setTicker] = useState('AAPL');
  const [startDate, setStartDate] = useState<Date | null>(null);
  const [endDate, setEndDate] = useState<Date | null>(null);
  const [analysis, setAnalysis] = useState<TickerAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Basket analysis state
  const [viewMode, setViewMode] = useState<'single' | 'basket'>('single');
  const [basketTickers, setBasketTickers] = useState('AAPL,MSFT,GOOGL,TSLA,AMZN');
  const [basketStartDate, setBasketStartDate] = useState<Date | null>(null);
  const [basketEndDate, setBasketEndDate] = useState<Date | null>(null);
  const [basketAnalysis, setBasketAnalysis] = useState<BasketAnalysisResponse | null>(null);
  const [basketLoading, setBasketLoading] = useState(false);
  const [basketError, setBasketError] = useState<string | null>(null);
  const [basketHolisticSummaryExpanded, setBasketHolisticSummaryExpanded] = useState(true);
  const [basketFilterNewsOnly, setBasketFilterNewsOnly] = useState(false);
  const [basketSortOption, setBasketSortOption] = useState<'biggest_winners' | 'biggest_losers' | 'alphabetical'>('biggest_winners');
  const [basketSectorFilter, setBasketSectorFilter] = useState<string>('all');
  const [basketIndustryFilter, setBasketIndustryFilter] = useState<string>('all');
  const [selectedBasket, setSelectedBasket] = useState<string | null>(null);
  const [basketDropdownOpen, setBasketDropdownOpen] = useState(false);

  // Collapsible sections state
  const [holisticSummaryExpanded, setHolisticSummaryExpanded] = useState(true);
  const [newsHighlightsExpanded, setNewsHighlightsExpanded] = useState(true);
  const [tickerInfoExpanded, setTickerInfoExpanded] = useState(true);
  const [analyticsExpanded, setAnalyticsExpanded] = useState(true);
  const [holisticSummary, setHolisticSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [newsLoading, setNewsLoading] = useState(false);
  const [basketAiLoading, setBasketAiLoading] = useState(false);

  // Price history data for charts
  const [priceHistory, setPriceHistory] = useState<PriceHistoryResponse | null>(null);
  const [priceHistoryLoading, setPriceHistoryLoading] = useState(false);

  // Threshold state
  const [minMovementThreshold, setMinMovementThreshold] = useState(2.0);

  // Sort state
  const [movementSort, setMovementSort] = useState<'date' | 'biggest_winners' | 'biggest_losers'>('date');
  const [filterNewsOnly, setFilterNewsOnly] = useState(false);

  // Header navigation state
  const [activeSection, setActiveSection] = useState<string>('');

  // PDF download state
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  // Ref to track current ticker being fetched to prevent race conditions
  const currentTickerRef = useRef<string | null>(null);

  // Memoize section click handler to avoid unnecessary re-renders
  const handleSectionClick = React.useCallback((sectionId: string) => {
    setActiveSection(sectionId);
  }, []);

  // Sort movements based on selected sort option
  const sortedMovements = React.useMemo(() => {
    if (!analysis) return [];

    let movements = [...analysis.movements];

    // Filter by news if checkbox is checked
    if (filterNewsOnly && analysis.batch_news_cards) {
      const newsDates = new Set(analysis.batch_news_cards.filter(card => card.date).map(card => card.date));
      movements = movements.filter(move => {
        const moveDateStr = new Date(move.date).toLocaleDateString('en-CA');
        return newsDates.has(moveDateStr);
      });
    }

    switch (movementSort) {
      case 'date':
        // Default: already sorted by date (newest first from API)
        return movements;
      case 'biggest_winners':
        // Sort by change percentage descending (biggest positive to smallest positive)
        return movements.sort((a, b) => b.change_pct - a.change_pct);
      case 'biggest_losers':
        // Sort by change percentage ascending (biggest negative to smallest negative)
        return movements.sort((a, b) => a.change_pct - b.change_pct);
      default:
        return movements;
    }
  }, [analysis, movementSort, filterNewsOnly]);

  // Define navigation sections based on view mode and data
  const navSections: Section[] = [
    {
      id: 'holistic-summary',
      label: 'Holistic Summary',
      icon: Info,
      visible: viewMode === 'single' && (!!holisticSummary || summaryLoading)
    },
    {
      id: 'analytics',
      label: 'Analytics & Graphs',
      icon: BarChart3,
      visible: viewMode === 'single' && !!analysis
    },
    {
      id: 'movements',
      label: 'Significant Movements',
      icon: TrendingUp,
      visible: viewMode === 'single' && !!analysis
    },
    {
      id: 'news-highlights',
      label: 'News Highlights',
      icon: Newspaper,
      visible: viewMode === 'single' && (analysis?.batch_news_cards?.length ?? 0) > 0
    },
    {
      id: 'basket-holistic-summary',
      label: 'Basket Summary',
      icon: Info,
      visible: viewMode === 'basket' && !!basketAnalysis?.holistic_summary
    },
    {
      id: 'basket-analytics',
      label: 'Analytics & Graphs',
      icon: BarChart3,
      visible: viewMode === 'basket' && !!basketAnalysis
    },
    {
      id: 'basket-performance',
      label: 'Basket Performance',
      icon: Layers,
      visible: viewMode === 'basket' && !!basketAnalysis
    }
  ];

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker) return;

    const params: { start_date?: string; end_date?: string } = {};
    if (startDate) params.start_date = format(startDate, 'yyyy-MM-dd');
    if (endDate) params.end_date = format(endDate, 'yyyy-MM-dd');

    // Track current ticker to prevent race conditions
    const currentTicker = ticker.toUpperCase();
    currentTickerRef.current = currentTicker;

    // Reset all state
    setLoading(true);
    setError(null);
    setAnalysis(null);
    setHolisticSummary(null);
    setPriceHistory(null);
    setNewsLoading(false);

    // ── Phase 1: Fast price & movement data (no AI) ─────────────────────────
    let phaseOneData;
    try {
      phaseOneData = await stockApi.getAnalysis(currentTicker, {
        ...params,
        min_movement_pct: minMovementThreshold,
        include_news: false,
      });
    } catch (err: unknown) {
      setLoading(false);
      console.error('Analysis error:', err);
      if (err && typeof err === 'object' && 'rateLimitInfo' in err) {
        const rateLimitErr = err as { rateLimitInfo?: { isRateLimit: boolean; message: string } };
        if (rateLimitErr.rateLimitInfo?.isRateLimit) {
          setError(rateLimitErr.rateLimitInfo.message);
          return;
        }
      }
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as { response?: { status?: number; data?: { detail?: string } } };
        const errorDetail = axiosError.response?.data?.detail;
        if (errorDetail) { setError(errorDetail); return; }
        if (axiosError.response?.status === 429) { setError('Rate limit reached. Please wait a moment before trying again.'); return; }
      }
      setError(err instanceof Error ? err.message || 'Failed to fetch analysis. Please try again.' : 'Failed to fetch analysis. Please try again.');
      return;
    }

    // Show price/movement data immediately
    setAnalysis(phaseOneData);
    setLoading(false);

    // ── Phase 2: Background AI calls (news + summary + price history) ────────
    setSummaryLoading(true);
    setPriceHistoryLoading(true);
    setNewsLoading(true);

    const [newsResult, summaryResult, priceHistoryResult] = await Promise.allSettled([
      stockApi.getAnalysisNews(currentTicker, {
        ...params,
        min_movement_pct: minMovementThreshold,
      }),
      stockApi.chat(currentTicker, {
        message: 'Provide a 1-2 sentence summary of what drove this stock\'s movements over the entire time period. Keep it simple and readable. Do not offer follow-up actions or suggest what the user can do next.',
        history: [],
      }),
      stockApi.getPriceHistory(currentTicker, params),
    ]);

    // Only update state if this is still the current ticker (prevent race condition)
    if (currentTickerRef.current === currentTicker) {
      if (newsResult.status === 'fulfilled') {
        setAnalysis(prev => prev ? { ...prev, batch_news_cards: newsResult.value.batch_news_cards } : prev);
      } else {
        console.error('Failed to fetch news:', newsResult.reason);
      }
      setNewsLoading(false);

      if (summaryResult.status === 'fulfilled') {
        setHolisticSummary(summaryResult.value.response);
      } else {
        console.error('Failed to fetch holistic summary:', summaryResult.reason);
      }
      setSummaryLoading(false);

      if (priceHistoryResult.status === 'fulfilled') {
        setPriceHistory(priceHistoryResult.value);
      } else {
        console.error('Failed to fetch price history:', priceHistoryResult.reason);
      }
      setPriceHistoryLoading(false);
    }
  };

  const clearDates = () => {
    setStartDate(null);
    setEndDate(null);
  };

  const getCytdStartDate = (): Date => {
    const now = new Date();
    return new Date(now.getFullYear(), 0, 1); // January 1st of current year
  };

  const getFytdStartDate = (): Date => {
    const now = new Date();
    const currentYear = now.getFullYear();
    const currentMonth = now.getMonth();
    
    // Fiscal year ends June 30, so if we're before July, fiscal year started previous year
    if (currentMonth < 6) {
      return new Date(currentYear - 1, 5, 30); // June 30th of previous year
    } else {
      return new Date(currentYear, 5, 30); // June 30th of current year
    }
  };

  const setCytdDates = () => {
    setStartDate(getCytdStartDate());
    setEndDate(new Date());
  };

  const setFytdDates = () => {
    setStartDate(getFytdStartDate());
    setEndDate(new Date());
  };

  const handleBasketAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();

    const tickerList = basketTickers.split(',')
      .map(t => t.trim().toUpperCase())
      .filter(t => t.length > 0);

    if (tickerList.length === 0) {
      setBasketError('Please enter at least one valid ticker');
      return;
    }

    const resolvedEnd = basketEndDate || new Date();
    const resolvedStart = basketStartDate || new Date(new Date().setMonth(resolvedEnd.getMonth() - 3));
    const startDateStr = format(resolvedStart, 'yyyy-MM-dd');
    const endDateStr = format(resolvedEnd, 'yyyy-MM-dd');
    const basketName = selectedBasket ? DEFAULT_BASKETS.find(b => b.id === selectedBasket)?.name : undefined;

    // Reset state
    setBasketLoading(true);
    setBasketError(null);
    setBasketAnalysis(null);
    setBasketAiLoading(false);

    // ── Phase 1: Fast price & performance data (no AI) ──────────────────────
    let phaseOneData;
    try {
      phaseOneData = await stockApi.analyzeBasket({
        tickers: tickerList,
        start_date: startDateStr,
        end_date: endDateStr,
        include_news: false,
        include_competitors: false,
        include_macro: false,
        basket_id: selectedBasket || undefined,
        basket_name: basketName,
      });
    } catch (err: unknown) {
      setBasketLoading(false);
      console.error('Basket analysis error:', err);
      if (err && typeof err === 'object' && 'rateLimitInfo' in err) {
        const rateLimitErr = err as { rateLimitInfo?: { isRateLimit: boolean; message: string } };
        if (rateLimitErr.rateLimitInfo?.isRateLimit) { setBasketError(rateLimitErr.rateLimitInfo.message); return; }
      }
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as { response?: { status?: number; data?: { detail?: string } } };
        const errorDetail = axiosError.response?.data?.detail;
        if (errorDetail) { setBasketError(errorDetail); return; }
        if (axiosError.response?.status === 429) { setBasketError('Rate limit reached. Please wait a moment before trying again.'); return; }
      }
      setBasketError(err instanceof Error ? err.message || 'Failed to analyze basket. Please try again.' : 'Failed to analyze basket. Please try again.');
      return;
    }

    // Show performance / analytics immediately
    setBasketAnalysis(phaseOneData);
    setBasketLoading(false);

    // ── Phase 2: Background AI enrichment (news + holistic summary) ──────────
    setBasketAiLoading(true);
    try {
      const enrichData = await stockApi.enrichBasket({
        tickers: tickerList,
        start_date: startDateStr,
        end_date: endDateStr,
        results: phaseOneData.results,
        include_competitors: false,
        include_macro: false,
        basket_name: basketName,
      });

      setBasketAnalysis(prev => {
        if (!prev) return prev;
        const updatedResults = prev.results.map(r => ({
          ...r,
          news_cards: enrichData.ticker_news[r.ticker] || r.news_cards,
        }));
        return {
          ...prev,
          results: updatedResults,
          holistic_summary: enrichData.holistic_summary,
          news_source: 'OpenAI Web Search',
        };
      });
    } catch (err) {
      console.error('Basket enrichment error (non-fatal):', err);
    } finally {
      setBasketAiLoading(false);
    }
  };

  const clearBasketDates = () => {
    setBasketStartDate(null);
    setBasketEndDate(null);
  };

  const setBasketCytdDates = () => {
    setBasketStartDate(getCytdStartDate());
    setBasketEndDate(new Date());
  };

  const setBasketFytdDates = () => {
    setBasketStartDate(getFytdStartDate());
    setBasketEndDate(new Date());
  };

  const handleSelectBasket = (basketId: string) => {
    const basket = DEFAULT_BASKETS.find(b => b.id === basketId);
    if (basket) {
      setBasketTickers(basket.tickers);
      setSelectedBasket(basketId);
      setBasketDropdownOpen(false);
    }
  };

  const handleClearBasket = () => {
    setBasketTickers('');
    setSelectedBasket(null);
  };

  const handleDownloadPdf = async () => {
    if (!analysis) return;

    setDownloadingPdf(true);
    try {
      await stockApi.downloadAnalysisPdfFromData(analysis);
    } catch (err) {
      console.error('PDF download error:', err);
      if (err && typeof err === 'object' && 'rateLimitInfo' in err) {
        const rateLimitErr = err as { rateLimitInfo?: { isRateLimit: boolean; message: string } };
        if (rateLimitErr.rateLimitInfo?.isRateLimit) {
          alert(rateLimitErr.rateLimitInfo.message);
        }
      } else {
        alert('Failed to download PDF. Please try again.');
      }
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleDownloadBasketPdf = async () => {
    if (!basketAnalysis) return;

    setDownloadingPdf(true);
    try {
      await stockApi.downloadBasketPdfFromData(basketAnalysis);
    } catch (err) {
      console.error('Basket PDF download error:', err);
      if (err && typeof err === 'object' && 'rateLimitInfo' in err) {
        const rateLimitErr = err as { rateLimitInfo?: { isRateLimit: boolean; message: string } };
        if (rateLimitErr.rateLimitInfo?.isRateLimit) {
          alert(rateLimitErr.rateLimitInfo.message);
        }
      } else {
        alert('Failed to download PDF. Please try again.');
      }
    } finally {
      setDownloadingPdf(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-4">
          {/* Logo and View Toggle */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="bg-indigo-600 p-2 rounded-lg">
                <TrendingUp className="text-white w-6 h-6" />
              </div>
              <h1 className="text-xl font-bold tracking-tight">Stock Analyzer</h1>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex bg-slate-100 rounded-lg p-1">
                <button
                  onClick={() => setViewMode('single')}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    viewMode === 'single' 
                      ? 'bg-white text-indigo-600 shadow-sm' 
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Single Ticker
                </button>
                <button
                  onClick={() => setViewMode('basket')}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${
                    viewMode === 'basket' 
                      ? 'bg-white text-indigo-600 shadow-sm' 
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <Layers className="w-4 h-4" />
                  Basket
                </button>
              </div>
              {viewMode === 'single' && analysis && (
                <button
                  onClick={handleDownloadPdf}
                  disabled={downloadingPdf}
                  className="flex items-center gap-2 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
                  title="Download PDF Report"
                >
                  {downloadingPdf ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                  <span>Download Report</span>
                </button>
              )}
              {viewMode === 'basket' && basketAnalysis && (
                <button
                  onClick={handleDownloadBasketPdf}
                  disabled={downloadingPdf}
                  className="flex items-center gap-2 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
                  title="Download PDF Report"
                >
                  {downloadingPdf ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                  <span>Download Report</span>
                </button>
              )}
            </div>
          </div>

          {/* Search Form */}
          {viewMode === 'single' ? (
            <form onSubmit={handleSearch} className="flex flex-col gap-3">
              <div className="flex flex-col md:flex-row gap-2 md:gap-3">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
                  <input
                    type="text"
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value)}
                    placeholder="Enter Ticker (e.g. TSLA)"
                    className="pl-10 pr-4 py-2 bg-slate-100 border-transparent focus:bg-white focus:ring-2 focus:ring-indigo-500 rounded-lg outline-none w-full md:w-40 transition-all"
                  />
                </div>
                <div className="flex gap-2">
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4 pointer-events-none" />
                    <ReactDatePicker
                      selected={startDate}
                      onChange={(date: Date | null) => setStartDate(date)}
                      selectsStart
                      startDate={startDate}
                      endDate={endDate}
                      placeholderText="Start (90D)"
                      className="pl-10 pr-4 py-2 bg-slate-100 border-transparent focus:bg-white focus:ring-2 focus:ring-indigo-500 rounded-lg outline-none w-full md:w-36 transition-all text-sm"
                      dateFormat="MMM d, yyyy"
                    />
                  </div>
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4 pointer-events-none" />
                    <ReactDatePicker
                      selected={endDate}
                      onChange={(date: Date | null) => setEndDate(date)}
                      selectsEnd
                      startDate={startDate}
                      endDate={endDate}
                      minDate={startDate || undefined}
                      placeholderText="End (Today)"
                      className="pl-10 pr-4 py-2 bg-slate-100 border-transparent focus:bg-white focus:ring-2 focus:ring-indigo-500 rounded-lg outline-none w-full md:w-36 transition-all text-sm"
                      dateFormat="MMM d, yyyy"
                    />
                  </div>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      onClick={setCytdDates}
                      className="px-2.5 py-2 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
                      title="Calendar Year-to-Date"
                    >
                      CYTD
                    </button>
                    <button
                      type="button"
                      onClick={setFytdDates}
                      className="px-2.5 py-2 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
                      title="Fiscal Year-to-Date"
                    >
                      FYTD
                    </button>
                  </div>
                  {(startDate || endDate) && (
                    <button
                      type="button"
                      onClick={clearDates}
                      className="px-3 py-2 text-slate-500 hover:text-slate-700 hover:bg-slate-200 rounded-lg transition-colors"
                      title="Clear dates"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
                <button
                  type="submit"
                  disabled={loading}
                  className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Analyze'}
                </button>
              </div>
              {/* Threshold Control */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm text-slate-600 font-medium">Movement Threshold:</span>
                <div className="relative group">
                  <Info className="w-4 h-4 text-slate-400 cursor-help" />
                  <div className="absolute left-0 top-6 w-64 p-3 bg-slate-800 text-white text-xs rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-20">
                    Minimum percentage change to flag as a major movement. Lower values show more movements, higher values show only the biggest swings.
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <input
                    type="number"
                    value={minMovementThreshold}
                    onChange={(e) => setMinMovementThreshold(parseFloat(e.target.value) || 2.0)}
                    step="0.1"
                    min="0.1"
                    max="50"
                    title="Minimum percentage change to flag as a major movement"
                    className="w-20 px-3 py-1.5 bg-slate-100 border-transparent focus:bg-white focus:ring-2 focus:ring-indigo-500 rounded-lg outline-none text-sm font-medium transition-all"
                  />
                  <span className="text-sm text-slate-500">%</span>
                </div>
                <div className="flex gap-1">
                  {[1, 2, 3, 5].map((value) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setMinMovementThreshold(value)}
                      className={`px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
                        minMovementThreshold === value
                          ? 'bg-indigo-600 text-white'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      {value}%
                    </button>
                  ))}
                </div>
              </div>
            </form>
          ) : (
            <form onSubmit={handleBasketAnalysis} className="flex flex-col gap-3">
              {/* Default Basket Selector */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setBasketDropdownOpen(!basketDropdownOpen)}
                  className="w-full flex items-center justify-between px-4 py-2.5 bg-gradient-to-r from-indigo-50 to-purple-50 hover:from-indigo-100 hover:to-purple-100 border border-indigo-200 rounded-lg outline-none transition-all group"
                >
                  <div className="flex items-center gap-2">
                    <Layers className="w-4 h-4 text-indigo-600" />
                    <span className="text-sm font-medium text-slate-700">
                      {selectedBasket 
                        ? DEFAULT_BASKETS.find(b => b.id === selectedBasket)?.name || 'Select a Basket'
                        : 'Select a Default Basket'
                      }
                    </span>
                  </div>
                  <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform ${basketDropdownOpen ? 'rotate-180' : ''}`} />
                </button>
                
                {basketDropdownOpen && (
                  <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-slate-200 rounded-lg shadow-lg z-20 overflow-hidden">
                    {DEFAULT_BASKETS.map((basket) => (
                      <button
                        key={basket.id}
                        type="button"
                        onClick={() => handleSelectBasket(basket.id)}
                        className="w-full px-4 py-3 text-left hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-b-0"
                      >
                        <div className="flex items-start gap-3">
                          <span className="text-xl">{basket.icon}</span>
                          <div className="flex-1">
                            <div className="font-medium text-slate-900">{basket.name}</div>
                            <div className="text-xs text-slate-500 mt-0.5">{basket.description}</div>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex flex-col md:flex-row gap-2 md:gap-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
                  <input
                    type="text"
                    value={basketTickers}
                    onChange={(e) => {
                      setBasketTickers(e.target.value);
                      setSelectedBasket(null);
                    }}
                    placeholder="Tickers (e.g. AAPL,MSFT,GOOGL)"
                    className="pl-10 pr-4 py-2 bg-slate-100 border-transparent focus:bg-white focus:ring-2 focus:ring-indigo-500 rounded-lg outline-none w-full transition-all"
                  />
                  {selectedBasket && (
                    <button
                      type="button"
                      onClick={handleClearBasket}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-200 rounded transition-colors"
                      title="Clear basket"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
                <div className="flex gap-2">
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4 pointer-events-none" />
                    <ReactDatePicker
                      selected={basketStartDate}
                      onChange={(date: Date | null) => setBasketStartDate(date)}
                      selectsStart
                      startDate={basketStartDate}
                      endDate={basketEndDate}
                      placeholderText="Start (90D)"
                      className="pl-10 pr-4 py-2 bg-slate-100 border-transparent focus:bg-white focus:ring-2 focus:ring-indigo-500 rounded-lg outline-none w-full md:w-36 transition-all text-sm"
                      dateFormat="MMM d, yyyy"
                    />
                  </div>
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4 pointer-events-none" />
                    <ReactDatePicker
                      selected={basketEndDate}
                      onChange={(date: Date | null) => setBasketEndDate(date)}
                      selectsEnd
                      startDate={basketStartDate}
                      endDate={basketEndDate}
                      minDate={basketStartDate || undefined}
                      placeholderText="End (Today)"
                      className="pl-10 pr-4 py-2 bg-slate-100 border-transparent focus:bg-white focus:ring-2 focus:ring-indigo-500 rounded-lg outline-none w-full md:w-36 transition-all text-sm"
                      dateFormat="MMM d, yyyy"
                    />
                  </div>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      onClick={setBasketCytdDates}
                      className="px-2.5 py-2 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
                      title="Calendar Year-to-Date"
                    >
                      CYTD
                    </button>
                    <button
                      type="button"
                      onClick={setBasketFytdDates}
                      className="px-2.5 py-2 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
                      title="Fiscal Year-to-Date"
                    >
                      FYTD
                    </button>
                  </div>
                  {(basketStartDate || basketEndDate) && (
                    <button
                      type="button"
                      onClick={clearBasketDates}
                      className="px-3 py-2 text-slate-500 hover:text-slate-700 hover:bg-slate-200 rounded-lg transition-colors"
                      title="Clear dates"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
                <button
                  type="submit"
                  disabled={basketLoading}
                  className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 whitespace-nowrap"
                >
                  {basketLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Analyze'}
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Section Navigation */}
        <div className="flex justify-center">
          <HeaderNavigation
            sections={navSections}
            activeSection={activeSection}
            onSectionClick={handleSectionClick}
          />
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {viewMode === 'single' ? (
          <>
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl mb-8 flex items-center gap-3">
                <AlertCircle className="w-5 h-5 shrink-0" />
                <p>{error}</p>
              </div>
            )}

            {!analysis && !loading && !error && (
              <div className="text-center py-20">
                <div className="bg-white w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm border border-slate-100">
                  <Search className="text-slate-300 w-10 h-10" />
                </div>
                <h2 className="text-2xl font-semibold mb-2">Ready to Analyze</h2>
                <p className="text-slate-500 max-w-md mx-auto">
                  Enter a stock ticker above to see major price movements and the news that caused them.
                </p>
              </div>
            )}

            {loading && (
              <div className="flex justify-center py-12">
                <LoadingScreen message="Analyzing Stock..." ticker={ticker} />
              </div>
            )}

            {analysis && (
              <div className="space-y-6">
                {/* Holistic Summary */}
                {(holisticSummary || summaryLoading) && (
                  <div id="holistic-summary">
                    <CollapsibleSection
                      title="Holistic Summary"
                      icon={Info}
                      expanded={holisticSummaryExpanded}
                      onToggle={() => setHolisticSummaryExpanded(!holisticSummaryExpanded)}
                    >
                      {summaryLoading ? (
                        <div className="flex items-center gap-2 text-slate-500">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span className="text-sm">Generating summary...</span>
                        </div>
                      ) : (
                        <div className="prose prose-slate max-w-none">
                          <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">{holisticSummary}</p>
                        </div>
                      )}
                    </CollapsibleSection>
                  </div>
                )}

                {/* Analytics & Graphs */}
                <div id="analytics">
                  <CollapsibleSection
                    title="Analytics & Graphs"
                    icon={BarChart3}
                    expanded={analyticsExpanded}
                    onToggle={() => setAnalyticsExpanded(!analyticsExpanded)}
                  >
                    {priceHistoryLoading ? (
                      <div className="flex items-center justify-center py-12">
                        <div className="flex items-center gap-2 text-slate-500">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span className="text-sm">Loading chart data...</span>
                        </div>
                      </div>
                    ) : priceHistory ? (
                      <StockChart data={priceHistory.data} newsCards={analysis.batch_news_cards} />
                    ) : (
                      <div className="flex items-center justify-center py-12 bg-slate-50 rounded-lg">
                        <p className="text-slate-500">Unable to load chart data</p>
                      </div>
                    )}
                  </CollapsibleSection>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Left Column: Ticker Info & Summary */}
                <div className="lg:col-span-1 space-y-6">
                  <div id="ticker-info">
                    <CollapsibleSection
                      title="Ticker Info"
                      icon={Info}
                      expanded={tickerInfoExpanded}
                      onToggle={() => setTickerInfoExpanded(!tickerInfoExpanded)}
                    >
                      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-3 mb-4">
                        <div>
                          <h2 className="text-3xl font-bold">{analysis.ticker}</h2>
                          <p className="text-slate-500 font-medium">{analysis.company_name}</p>
                        </div>
                        <div className="bg-slate-100 px-3 py-1 rounded-full text-xs font-bold text-slate-600 uppercase tracking-wide whitespace-nowrap">
                          {analysis.sector || 'N/A'}
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-4 mt-6">
                        <div className="bg-emerald-50 p-3 rounded-xl border border-emerald-100">
                          <p className="text-emerald-600 text-xs font-bold uppercase mb-1">Up Days</p>
                          <p className="text-2xl font-bold text-emerald-700">{analysis.up_movements}</p>
                        </div>
                        <div className="bg-rose-50 p-3 rounded-xl border border-rose-100">
                          <p className="text-rose-600 text-xs font-bold uppercase mb-1">Down Days</p>
                          <p className="text-2xl font-bold text-rose-700">{analysis.down_movements}</p>
                        </div>
                      </div>

                      <div className="mt-6 pt-6 border-t border-slate-100">
                        <div className="flex items-center justify-between text-sm text-slate-500 mb-2">
                          <span className="flex items-center gap-1.5"><Calendar className="w-4 h-4" /> Period</span>
                          <span className="font-medium text-slate-700">
                            {format(new Date(analysis.period_start), 'MMM d')} - {format(new Date(analysis.period_end), 'MMM d, yyyy')}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-sm text-slate-500">
                          <span className="flex items-center gap-1.5"><TrendingUp className="w-4 h-4" /> Threshold</span>
                          <span className="font-medium text-slate-700">±{analysis.min_movement_pct}%</span>
                        </div>
                      </div>
                    </CollapsibleSection>
                  </div>
                </div>

                {/* Right Column: Movements Timeline */}
                <div id="movements" className="lg:col-span-2 space-y-4">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-bold flex items-center gap-2">
                      Significant Movements
                      <span className="bg-slate-200 text-slate-600 text-xs px-2 py-0.5 rounded-full">
                        {analysis.total_movements}
                      </span>
                    </h3>
                    <div className="flex items-center gap-3">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={filterNewsOnly}
                          onChange={(e) => setFilterNewsOnly(e.target.checked)}
                          className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span className="text-sm text-slate-700">Has news</span>
                      </label>
                      <div className="flex items-center gap-2">
                        <label className="text-sm text-slate-600 font-medium">Sort by:</label>
                        <select
                          value={movementSort}
                          onChange={(e) => setMovementSort(e.target.value as 'date' | 'biggest_winners' | 'biggest_losers')}
                          title="Sort movements by date or magnitude"
                          className="px-3 py-1.5 bg-slate-100 border-transparent focus:bg-white focus:ring-2 focus:ring-indigo-500 rounded-lg outline-none text-sm font-medium transition-all cursor-pointer"
                        >
                          <option value="date">Date</option>
                          <option value="biggest_winners">Biggest Winners</option>
                          <option value="biggest_losers">Biggest Losers</option>
                        </select>
                      </div>
                    </div>
                  </div>

                  {sortedMovements.map((move, i) => (
                    <MovementCard key={i} move={move} batchNewsCards={analysis.batch_news_cards} />
                  ))}

                  {analysis.total_movements === 0 && (
                    <div className="bg-white p-12 rounded-2xl text-center border border-slate-200 border-dashed">
                      <Info className="w-12 h-12 text-slate-200 mx-auto mb-4" />
                      <p className="text-slate-500">No major movements detected in this period.</p>
                    </div>
                  )}
                </div>
                </div>

                {/* Batch News Cards */}
                {analysis.batch_news_cards && analysis.batch_news_cards.length > 0 && (
                  <div id="news-highlights">
                    <CollapsibleSection
                      title="News Highlights"
                      icon={Newspaper}
                      expanded={newsHighlightsExpanded}
                      onToggle={() => setNewsHighlightsExpanded(!newsHighlightsExpanded)}
                      badge={`${analysis.batch_news_cards.length} articles`}
                    >
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {analysis.batch_news_cards.map((card, i) => (
                          <NewsCardItem key={i} card={card} />
                        ))}
                      </div>
                    </CollapsibleSection>
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          <>
            {basketError && (
              <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl mb-8 flex items-center gap-3">
                <AlertCircle className="w-5 h-5 shrink-0" />
                <p>{basketError}</p>
              </div>
            )}

            {!basketAnalysis && !basketLoading && !basketError && (
              <div className="text-center py-20">
                <div className="bg-white w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm border border-slate-100">
                  <Layers className="text-slate-300 w-10 h-10" />
                </div>
                <h2 className="text-2xl font-semibold mb-2">Basket Analysis</h2>
                <p className="text-slate-500 max-w-md mx-auto">
                  Enter multiple ticker symbols above to compare their performance and find the biggest movers.
                </p>
              </div>
            )}

            {basketLoading && (
              <div className="flex justify-center py-12">
                <LoadingScreen message="Analyzing Basket..." />
              </div>
            )}

            {basketAnalysis && (
              <div className="space-y-6">
                {/* Holistic Summary */}
                {basketAnalysis.holistic_summary && (
                  <div id="basket-holistic-summary">
                    <CollapsibleSection
                      title="Basket Summary"
                      icon={Info}
                      expanded={basketHolisticSummaryExpanded}
                      onToggle={() => setBasketHolisticSummaryExpanded(!basketHolisticSummaryExpanded)}
                    >
                      <div className="prose prose-slate max-w-none">
                        {(() => {
                          const { broadTheme, detailedAnalysis } = parseBasketSummary(basketAnalysis.holistic_summary, basketAnalysis.tickers);
                          return (
                            <div className="space-y-4">
                              {broadTheme && (
                                <div className="bg-gradient-to-r from-indigo-50 to-blue-50 border-l-4 border-indigo-500 p-4 rounded-r-lg">
                                  <p className="text-slate-800 font-semibold leading-relaxed text-base">
                                    {broadTheme}
                                  </p>
                                </div>
                              )}
                              {detailedAnalysis && (
                                <div className="text-slate-700 leading-relaxed whitespace-pre-wrap">
                                  {detailedAnalysis}
                                </div>
                              )}
                              {!broadTheme && !detailedAnalysis && (
                                <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">
                                  {formatBasketSummary(basketAnalysis.holistic_summary, basketAnalysis.tickers)}
                                </p>
                              )}
                            </div>
                          );
                        })()}
                      </div>
                    </CollapsibleSection>
                  </div>
                )}

                {/* Analytics & Graphs */}
                <div id="basket-analytics">
                  <CollapsibleSection
                    title="Analytics & Graphs"
                    icon={BarChart3}
                    expanded={true}
                    onToggle={() => {}}
                  >
                    <BasketAnalytics results={basketAnalysis.results} />
                  </CollapsibleSection>
                </div>

                <div id="basket-performance" className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                  <div className="flex items-center justify-between mb-6">
                    <div>
                      <h2 className="text-2xl font-bold">Basket Performance</h2>
                      <p className="text-slate-500">
                        {format(new Date(basketAnalysis.period_start), 'MMM d')} - {format(new Date(basketAnalysis.period_end), 'MMM d, yyyy')}
                      </p>
                    </div>
                    <div className="bg-indigo-100 px-4 py-2 rounded-full text-sm font-bold text-indigo-700">
                      {basketAnalysis.total_analyzed} analyzed
                    </div>
                  </div>

                  <div className="flex items-center gap-4 mb-6 pb-4 border-b border-slate-200 flex-wrap">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={basketFilterNewsOnly}
                        onChange={(e) => setBasketFilterNewsOnly(e.target.checked)}
                        className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="text-sm text-slate-700">Show only with news</span>
                    </label>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-slate-500">Sector:</span>
                      <select
                        value={basketSectorFilter}
                        onChange={(e) => setBasketSectorFilter(e.target.value)}
                        className="text-sm border border-slate-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        aria-label="Filter by sector"
                      >
                        <option value="all">All Sectors</option>
                        {[...new Set(basketAnalysis.results.map(r => r.sector).filter(Boolean))].sort().map(sector => (
                          <option key={sector} value={sector}>{sector}</option>
                        ))}
                      </select>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-slate-500">Industry:</span>
                      <select
                        value={basketIndustryFilter}
                        onChange={(e) => setBasketIndustryFilter(e.target.value)}
                        className="text-sm border border-slate-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        aria-label="Filter by industry"
                      >
                        <option value="all">All Industries</option>
                        {[...new Set(basketAnalysis.results.map(r => r.industry).filter(Boolean))].sort().map(industry => (
                          <option key={industry} value={industry}>{industry}</option>
                        ))}
                      </select>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-slate-500">Sort by:</span>
                      <select
                        value={basketSortOption}
                        onChange={(e) => setBasketSortOption(e.target.value as 'biggest_winners' | 'biggest_losers' | 'alphabetical')}
                        className="text-sm border border-slate-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        aria-label="Sort basket results"
                      >
                        <option value="biggest_winners">Biggest winners</option>
                        <option value="biggest_losers">Biggest losers</option>
                        <option value="alphabetical">Alphabetical</option>
                      </select>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {(() => {
                      let filteredResults = [...basketAnalysis.results];

                      // Filter by news
                      if (basketFilterNewsOnly) {
                        filteredResults = filteredResults.filter(r => r.news_cards && r.news_cards.length > 0);
                      }

                      // Filter by sector
                      if (basketSectorFilter !== 'all') {
                        filteredResults = filteredResults.filter(r => r.sector === basketSectorFilter);
                      }

                      // Filter by industry
                      if (basketIndustryFilter !== 'all') {
                        filteredResults = filteredResults.filter(r => r.industry === basketIndustryFilter);
                      }

                      // Sort results
                      if (basketSortOption === 'biggest_winners') {
                        filteredResults.sort((a, b) => (b.total_change_pct || 0) - (a.total_change_pct || 0));
                      } else if (basketSortOption === 'biggest_losers') {
                        filteredResults.sort((a, b) => (a.total_change_pct || 0) - (b.total_change_pct || 0));
                      } else if (basketSortOption === 'alphabetical') {
                        filteredResults.sort((a, b) => a.ticker.localeCompare(b.ticker));
                      }

                      return filteredResults.map((result, i) => (
                        <BasketResultCard key={result.ticker} result={result} rank={i + 1} />
                      ));
                    })()}

                    {basketAnalysis.results.length === 0 && (
                      <div className="bg-slate-50 p-12 rounded-2xl text-center border border-slate-200 border-dashed">
                        <Info className="w-12 h-12 text-slate-200 mx-auto mb-4" />
                        <p className="text-slate-500">No valid results found for the provided tickers.</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </main>

      {/* AI Loading Bar at bottom */}
      <AILoadingBar
        items={[
          ...(newsLoading ? [{ key: 'news', message: 'Loading news...' }] : []),
          ...(summaryLoading ? [{ key: 'summary', message: 'Generating summary...' }] : []),
          ...(basketAiLoading ? [{ key: 'basket-news', message: 'Loading basket news...' }, { key: 'basket-summary', message: 'Generating basket summary...' }] : []),
        ]}
      />
    </div>
  );
};

export default App;
