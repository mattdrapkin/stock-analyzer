import React, { useState } from 'react';
import { 
  Search, 
  TrendingUp, 
  TrendingDown, 
  Calendar, 
  MessageSquare, 
  Info, 
  ExternalLink,
  ChevronRight,
  ChevronDown,
  Loader2,
  AlertCircle
} from 'lucide-react';
import { stockApi } from './api';
import type { TickerAnalysis, StockMovement, NewsArticle, ChatMessage } from './api';
import { format } from 'date-fns';

const App: React.FC = () => {
  const [ticker, setTicker] = useState('AAPL');
  const [analysis, setAnalysis] = useState<TickerAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Chat state
  const [chatMessage, setChatMessage] = useState('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker) return;
    
    setLoading(true);
    setError(null);
    try {
      const data = await stockApi.getAnalysis(ticker.toUpperCase());
      setAnalysis(data);
      setChatHistory([]); // Clear chat for new ticker
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as { response: { data: { detail: string } } };
        setError(axiosError.response?.data?.detail || 'Failed to fetch analysis');
      } else {
        setError('Failed to fetch analysis');
      }
      setAnalysis(null);
    } finally {
      setLoading(false);
    }
  };

  const handleChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatMessage || !analysis) return;

    const newMessage: ChatMessage = { role: 'user', content: chatMessage };
    setChatHistory(prev => [...prev, newMessage]);
    setChatMessage('');
    setChatLoading(true);

    try {
      const response = await stockApi.chat(analysis.ticker, {
        message: chatMessage,
        history: chatHistory
      });
      const assistantMessage: ChatMessage = { role: 'assistant', content: response.response };
      setChatHistory(prev => [...prev, assistantMessage]);
    } catch {
      const errorMessage: ChatMessage = { 
        role: 'assistant', 
        content: 'Sorry, I encountered an error while processing your request.' 
      };
      setChatHistory(prev => [...prev, errorMessage]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="bg-indigo-600 p-2 rounded-lg">
              <TrendingUp className="text-white w-6 h-6" />
            </div>
            <h1 className="text-xl font-bold tracking-tight">Stock Analyzer</h1>
          </div>
          
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder="Enter Ticker (e.g. TSLA)"
                className="pl-10 pr-4 py-2 bg-slate-100 border-transparent focus:bg-white focus:ring-2 focus:ring-indigo-500 rounded-lg outline-none w-full md:w-64 transition-all"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Analyze'}
            </button>
          </form>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
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

        {analysis && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left Column: Ticker Info & Summary */}
            <div className="lg:col-span-1 space-y-6">
              <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h2 className="text-3xl font-bold">{analysis.ticker}</h2>
                    <p className="text-slate-500 font-medium">{analysis.company_name}</p>
                  </div>
                  <div className="bg-slate-100 px-3 py-1 rounded-full text-xs font-bold text-slate-600 uppercase tracking-wider">
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
              </div>

              {/* Chat Interface (Desktop) */}
              <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden hidden lg:flex flex-col h-[500px]">
                <div className="bg-slate-50 p-4 border-b border-slate-200 flex items-center gap-2">
                  <MessageSquare className="w-5 h-5 text-indigo-600" />
                  <h3 className="font-bold">AI Stock Assistant</h3>
                </div>
                
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {chatHistory.length === 0 ? (
                    <div className="text-center py-8">
                      <p className="text-sm text-slate-400">Ask about {analysis.ticker}'s movements...</p>
                    </div>
                  ) : (
                    chatHistory.map((msg, i) => (
                      <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[85%] p-3 rounded-2xl text-sm ${
                          msg.role === 'user' 
                            ? 'bg-indigo-600 text-white rounded-tr-none' 
                            : 'bg-slate-100 text-slate-800 rounded-tl-none'
                        }`}>
                          {msg.content}
                        </div>
                      </div>
                    ))
                  )}
                  {chatLoading && (
                    <div className="flex justify-start">
                      <div className="bg-slate-100 p-3 rounded-2xl rounded-tl-none">
                        <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
                      </div>
                    </div>
                  )}
                </div>

                <form onSubmit={handleChat} className="p-4 bg-white border-t border-slate-100">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={chatMessage}
                      onChange={(e) => setChatMessage(e.target.value)}
                      placeholder="Ask why it moved..."
                      className="flex-1 bg-slate-50 border-none rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                    />
                    <button 
                      type="submit" 
                      disabled={chatLoading || !chatMessage}
                      className="bg-indigo-600 text-white p-2 rounded-lg disabled:opacity-50"
                      title="Send message"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </form>
              </div>
            </div>

            {/* Right Column: Movements Timeline */}
            <div className="lg:col-span-2 space-y-4">
              <h3 className="text-lg font-bold flex items-center gap-2 mb-4">
                Significant Movements
                <span className="bg-slate-200 text-slate-600 text-xs px-2 py-0.5 rounded-full">
                  {analysis.total_movements}
                </span>
              </h3>

              {analysis.movements.map((move, i) => (
                <MovementCard key={i} move={move} />
              ))}

              {analysis.total_movements === 0 && (
                <div className="bg-white p-12 rounded-2xl text-center border border-slate-200 border-dashed">
                  <Info className="w-12 h-12 text-slate-200 mx-auto mb-4" />
                  <p className="text-slate-500">No major movements detected in this period.</p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Floating Chat Button (Mobile) */}
      {analysis && (
        <button
          onClick={() => setIsChatOpen(!isChatOpen)}
          className="lg:hidden fixed bottom-6 right-6 bg-indigo-600 text-white p-4 rounded-full shadow-lg z-20"
          title="Toggle chat"
        >
          <MessageSquare className="w-6 h-6" />
        </button>
      )}
    </div>
  );
};

const MovementCard: React.FC<{ move: StockMovement }> = ({ move }) => {
  const [expanded, setExpanded] = useState(false);
  const isUp = move.direction === 'up';

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
          <div className="space-y-4">
            {move.news.length > 0 ? (
              move.news.map((article, j) => (
                <NewsItem key={j} article={article} />
              ))
            ) : (
              <div className="bg-slate-50 p-4 rounded-xl text-center">
                <p className="text-sm text-slate-500 italic">No specific news articles found for this date.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const NewsItem: React.FC<{ article: NewsArticle }> = ({ article }) => {
  return (
    <div className="group border-l-2 border-indigo-100 hover:border-indigo-500 pl-4 transition-colors">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[10px] font-bold uppercase tracking-tighter text-indigo-500 bg-indigo-50 px-1.5 py-0.5 rounded">
          {article.category}
        </span>
        <span className="text-xs font-medium text-slate-400">{article.source}</span>
      </div>
      <a 
        href={article.url || '#'} 
        target="_blank" 
        rel="noopener noreferrer"
        className="text-slate-800 font-semibold leading-snug group-hover:text-indigo-600 transition-colors flex items-start gap-1"
      >
        {article.title}
        {article.url && <ExternalLink className="w-3 h-3 mt-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />}
      </a>
      {article.summary && (
        <p className="text-sm text-slate-500 mt-1 line-clamp-2">{article.summary}</p>
      )}
    </div>
  );
};

export default App;

