import React, { useState } from 'react';
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
  Download
} from 'lucide-react';
import { stockApi } from './api';
import type { TickerAnalysis, StockMovement, NewsCard, BasketAnalysisResponse, BasketTickerResult } from './api';
import { format } from 'date-fns';
import HeaderNavigation, { type Section } from './components/HeaderNavigation';
import LoadingScreen from './components/LoadingScreen';

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

    // Only highlight if it's a valid ticker in the basket
    if (validTickers.includes(ticker)) {
      // Render ticker as bold
      if (percentage) {
        const pctValue = parseFloat(percentage);
        // Handle NaN case
        if (!isNaN(pctValue)) {
          const colorClass = pctValue >= 0 ? 'text-emerald-600 font-bold' : 'text-rose-600 font-bold';
          parts.push(
            <span key={match.index}>
              <span className="font-bold">{ticker}</span>
              <span className={colorClass}> ({percentage}%)</span>
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
      parts.push(match[0]);
    }

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : text;
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

  // Collapsible sections state
  const [holisticSummaryExpanded, setHolisticSummaryExpanded] = useState(true);
  const [newsHighlightsExpanded, setNewsHighlightsExpanded] = useState(true);
  const [tickerInfoExpanded, setTickerInfoExpanded] = useState(true);
  const [holisticSummary, setHolisticSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  // Threshold state
  const [minMovementThreshold, setMinMovementThreshold] = useState(2.0);

  // Sort state
  const [movementSort, setMovementSort] = useState<'date' | 'biggest_winners' | 'biggest_losers'>('date');

  // Header navigation state
  const [activeSection, setActiveSection] = useState<string>('');

  // PDF download state
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  // Memoize section click handler to avoid unnecessary re-renders
  const handleSectionClick = React.useCallback((sectionId: string) => {
    setActiveSection(sectionId);
  }, []);

  // Sort movements based on selected sort option
  const sortedMovements = React.useMemo(() => {
    if (!analysis) return [];
    
    const movements = [...analysis.movements];
    
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
  }, [analysis, movementSort]);

  // Define navigation sections based on view mode and data
  const navSections: Section[] = [
    {
      id: 'holistic-summary',
      label: 'Holistic Summary',
      icon: Info,
      visible: viewMode === 'single' && (!!holisticSummary || summaryLoading)
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
      visible: viewMode === 'single' && analysis?.batch_news_cards && analysis.batch_news_cards.length > 0
    },
    {
      id: 'basket-holistic-summary',
      label: 'Basket Summary',
      icon: Info,
      visible: viewMode === 'basket' && !!basketAnalysis?.holistic_summary
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
    
    setLoading(true);
    setError(null);
    try {
      const params: {
        start_date?: string;
        end_date?: string;
      } = {};
      if (startDate) {
        params.start_date = format(startDate, 'yyyy-MM-dd');
      }
      if (endDate) {
        params.end_date = format(endDate, 'yyyy-MM-dd');
      }
      const data = await stockApi.getAnalysis(ticker.toUpperCase(), {
        ...params,
        min_movement_pct: minMovementThreshold
      });
      setAnalysis(data);
      setHolisticSummary(null); // Clear previous summary
      setSummaryLoading(true); // Start loading summary
      
      // Auto-fetch holistic summary
      try {
        const summaryResponse = await stockApi.chat(ticker, {
          message: 'Provide a 1-2 sentence summary of what drove this stock\'s movements over the entire time period. Keep it simple and readable. Do not offer follow-up actions or suggest what the user can do next.',
          history: []
        });
        setHolisticSummary(summaryResponse.response);
      } catch (err) {
        // Log error and fail gracefully if summary fetch fails
        console.error('Failed to fetch holistic summary:', err);
        setHolisticSummary(null);
      } finally {
        setSummaryLoading(false); // Stop loading summary
      }
    } catch (err: unknown) {
      console.error('Analysis error:', err);
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as { response?: { status?: number; data?: { detail?: string } } };
        const errorDetail = axiosError.response?.data?.detail;
        if (errorDetail) {
          setError(errorDetail);
        } else if (axiosError.response?.status === 429) {
          setError('Rate limit reached. Please wait a moment before trying again.');
        } else {
          setError('Failed to fetch analysis. Please try again.');
        }
      } else if (err instanceof Error) {
        setError(err.message || 'Failed to fetch analysis. Please try again.');
      } else {
        setError('Failed to fetch analysis. Please try again.');
      }
      setAnalysis(null);
    } finally {
      setLoading(false);
    }
  };

  const clearDates = () => {
    setStartDate(null);
    setEndDate(null);
  };

  const handleBasketAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Parse tickers from comma-separated string
    const tickerList = basketTickers.split(',')
      .map(t => t.trim().toUpperCase())
      .filter(t => t.length > 0);
    
    if (tickerList.length === 0) {
      setBasketError('Please enter at least one valid ticker');
      return;
    }
    
    const resolvedEnd = basketEndDate || new Date();
    const resolvedStart = basketStartDate || new Date(new Date().setMonth(resolvedEnd.getMonth() - 3));
    
    setBasketLoading(true);
    setBasketError(null);
    try {
      const data = await stockApi.analyzeBasket({
        tickers: tickerList,
        start_date: format(resolvedStart, 'yyyy-MM-dd'),
        end_date: format(resolvedEnd, 'yyyy-MM-dd'),
        include_news: true,
        include_competitors: false,
        include_macro: false,
      });
      setBasketAnalysis(data);
    } catch (err: unknown) {
      console.error('Basket analysis error:', err);
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as { response?: { status?: number; data?: { detail?: string } } };
        const errorDetail = axiosError.response?.data?.detail;
        if (errorDetail) {
          setBasketError(errorDetail);
        } else if (axiosError.response?.status === 429) {
          setBasketError('Rate limit reached. Please wait a moment before trying again.');
        } else {
          setBasketError('Failed to analyze basket. Please try again.');
        }
      } else if (err instanceof Error) {
        setBasketError(err.message || 'Failed to analyze basket. Please try again.');
      } else {
        setBasketError('Failed to analyze basket. Please try again.');
      }
      setBasketAnalysis(null);
    } finally {
      setBasketLoading(false);
    }
  };

  const clearBasketDates = () => {
    setBasketStartDate(null);
    setBasketEndDate(null);
  };

  const handleDownloadPdf = async () => {
    if (!analysis) return;
    
    setDownloadingPdf(true);
    try {
      const params: {
        start_date?: string;
        end_date?: string;
        min_movement_pct?: number;
      } = {
        min_movement_pct: minMovementThreshold
      };
      
      if (startDate) {
        params.start_date = format(startDate, 'yyyy-MM-dd');
      }
      if (endDate) {
        params.end_date = format(endDate, 'yyyy-MM-dd');
      }
      
      await stockApi.downloadAnalysisPdf(analysis.ticker, params);
    } catch (err) {
      console.error('PDF download error:', err);
      alert('Failed to download PDF. Please try again.');
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleDownloadBasketPdf = async () => {
    if (!basketAnalysis) return;
    
    setDownloadingPdf(true);
    try {
      const resolvedEnd = basketEndDate || new Date();
      const resolvedStart = basketStartDate || new Date(new Date().setMonth(resolvedEnd.getMonth() - 3));
      
      await stockApi.downloadBasketPdf({
        tickers: basketAnalysis.tickers,
        start_date: format(resolvedStart, 'yyyy-MM-dd'),
        end_date: format(resolvedEnd, 'yyyy-MM-dd'),
        include_news: true,
        include_competitors: false,
        include_macro: false,
      });
    } catch (err) {
      console.error('Basket PDF download error:', err);
      alert('Failed to download PDF. Please try again.');
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
                      onChange={(date) => setStartDate(date)}
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
                      onChange={(date) => setEndDate(date)}
                      selectsEnd
                      startDate={startDate}
                      endDate={endDate}
                      minDate={startDate}
                      placeholderText="End (Today)"
                      className="pl-10 pr-4 py-2 bg-slate-100 border-transparent focus:bg-white focus:ring-2 focus:ring-indigo-500 rounded-lg outline-none w-full md:w-36 transition-all text-sm"
                      dateFormat="MMM d, yyyy"
                    />
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
            <form onSubmit={handleBasketAnalysis} className="flex flex-col md:flex-row gap-2 md:gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
                <input
                  type="text"
                  value={basketTickers}
                  onChange={(e) => setBasketTickers(e.target.value)}
                  placeholder="Tickers (e.g. AAPL,MSFT,GOOGL)"
                  className="pl-10 pr-4 py-2 bg-slate-100 border-transparent focus:bg-white focus:ring-2 focus:ring-indigo-500 rounded-lg outline-none w-full transition-all"
                />
              </div>
              <div className="flex gap-2">
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4 pointer-events-none" />
                  <ReactDatePicker
                    selected={basketStartDate}
                    onChange={(date) => setBasketStartDate(date)}
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
                    onChange={(date) => setBasketEndDate(date)}
                    selectsEnd
                    startDate={basketStartDate}
                    endDate={basketEndDate}
                    minDate={basketStartDate}
                    placeholderText="End (Today)"
                    className="pl-10 pr-4 py-2 bg-slate-100 border-transparent focus:bg-white focus:ring-2 focus:ring-indigo-500 rounded-lg outline-none w-full md:w-36 transition-all text-sm"
                    dateFormat="MMM d, yyyy"
                  />
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
                      <span className="text-sm text-slate-500">Filter by:</span>
                      <select
                        value={basketSectorFilter}
                        onChange={(e) => setBasketSectorFilter(e.target.value)}
                        className="text-sm border border-slate-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        aria-label="Filter by sector or industry"
                      >
                        <option value="all">All Sectors/Industries</option>
                        {(() => {
                          const uniqueSectors = [...new Set(basketAnalysis.results.map(r => r.sector).filter(Boolean))];
                          const uniqueIndustries = [...new Set(basketAnalysis.results.map(r => r.industry).filter(Boolean))];
                          return [...uniqueSectors, ...uniqueIndustries].sort().map(item => (
                            <option key={item} value={item}>{item}</option>
                          ));
                        })()}
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

                      // Filter by sector/industry
                      if (basketSectorFilter !== 'all') {
                        filteredResults = filteredResults.filter(r => 
                          r.sector === basketSectorFilter || r.industry === basketSectorFilter
                        );
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
    </div>
  );
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
                <p className="text-sm text-slate-400">No news articles found for this stock.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default App;

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

