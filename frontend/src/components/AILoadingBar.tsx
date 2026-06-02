import React from 'react';

interface LoadingItem {
  key: string;
  message: string;
}

interface AILoadingBarProps {
  items: LoadingItem[];
}

const RunningTiger: React.FC = () => (
  <div className="relative w-16 h-10 flex items-center justify-center overflow-hidden scale-75 select-none pointer-events-none">
    {/* Dust particles behind */}
    <div className="absolute left-1 bottom-1 flex gap-1">
      <div className="w-1 h-1 bg-amber-200 rounded-full animate-[dust_0.6s_infinite]" />
      <div className="w-1.5 h-1.5 bg-amber-300 rounded-full animate-[dust_0.6s_infinite_0.2s]" />
      <div className="w-1 h-1 bg-orange-200 rounded-full animate-[dust_0.6s_infinite_0.4s]" />
    </div>

    {/* Tiger structure wrapper */}
    <div className="relative w-12 h-8 animate-[tigerBob_0.6s_infinite]">
      {/* Tail */}
      <div className="absolute right-0 top-2 w-5 h-1.5 bg-amber-500 rounded-full origin-left animate-[tailWag_0.6s_infinite] transform rotate-12">
        {/* Tail stripes */}
        <div className="absolute right-1 top-0 w-1 h-full bg-slate-800 rounded-sm" />
        <div className="absolute right-3 top-0 w-1 h-full bg-slate-800 rounded-sm" />
      </div>

      {/* Back Leg (Left) */}
      <div className="absolute left-2.5 bottom-0 w-2 h-4 bg-amber-600 rounded-b-full origin-top animate-[legRunBack_0.6s_infinite]" />

      {/* Back Leg (Right) */}
      <div className="absolute left-3 bottom-0 w-2 h-4 bg-amber-500 rounded-b-full origin-top animate-[legRunFront_0.6s_infinite]" />

      {/* Body */}
      <div className="absolute left-3.5 top-1.5 w-7 h-5 bg-amber-500 rounded-full flex items-center justify-around overflow-hidden shadow-inner">
        {/* Body stripes */}
        <div className="w-0.5 h-3 bg-slate-800 rounded-full transform -rotate-12" />
        <div className="w-0.5 h-4 bg-slate-800 rounded-full transform -rotate-12" />
        <div className="w-0.5 h-3 bg-slate-800 rounded-full transform -rotate-12" />
      </div>

      {/* Front Leg (Left) */}
      <div className="absolute left-7.5 bottom-0 w-2 h-4 bg-amber-600 rounded-b-full origin-top animate-[legRunFront_0.6s_infinite]" />

      {/* Front Leg (Right) */}
      <div className="absolute left-8 bottom-0 w-2 h-4 bg-amber-500 rounded-b-full origin-top animate-[legRunBack_0.6s_infinite]" />

      {/* Head */}
      <div className="absolute left-7 top-0 w-5 h-5 bg-amber-400 rounded-full flex items-center justify-center">
        {/* Ears */}
        <div className="absolute -top-1.5 left-0.5 w-2.5 h-2.5 bg-amber-500 rounded-full flex items-center justify-center">
          <div className="w-1 h-1 bg-pink-200 rounded-full" />
        </div>
        <div className="absolute -top-1.5 right-0.5 w-2.5 h-2.5 bg-amber-500 rounded-full flex items-center justify-center">
          <div className="w-1 h-1 bg-pink-200 rounded-full" />
        </div>

        {/* Stripes on head */}
        <div className="absolute top-0.5 left-2 w-1 h-0.5 bg-slate-800 rounded-full" />
        <div className="absolute top-1 left-1.5 w-2 h-0.5 bg-slate-800 rounded-full" />

        {/* Eyes */}
        <div className="absolute top-2 left-1.5 w-1 h-1 bg-slate-900 rounded-full" />
        <div className="absolute top-2 right-1.5 w-1 h-1 bg-slate-900 rounded-full" />

        {/* Snout/Mouth */}
        <div className="absolute bottom-1 left-1.5 w-2 h-1 bg-amber-100 rounded-full" />
        <div className="absolute bottom-1 w-0.5 h-0.5 bg-amber-800 rounded-full" />
      </div>
    </div>
  </div>
);

const AILoadingBar: React.FC<AILoadingBarProps> = ({ items }) => {
  if (items.length === 0) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-r from-amber-50 via-orange-50 to-amber-50 border-t border-amber-200 shadow-lg z-50">
      <div className="max-w-6xl mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-amber-800 uppercase tracking-wider">AI Loading</span>
            <div className="flex gap-1">
              <div className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-[bounce_1s_infinite_0s]"></div>
              <div className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-[bounce_1s_infinite_0.2s]"></div>
              <div className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-[bounce_1s_infinite_0.4s]"></div>
            </div>
          </div>
          <div className="flex flex-wrap gap-4">
            {items.map((item) => (
              <div key={item.key} className="flex items-center gap-1 bg-white/80 pl-1 pr-3 py-1 rounded-full border border-amber-200 shadow-sm">
                <RunningTiger />
                <span className="text-xs font-bold text-slate-700">{item.message}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      <style>{`
        @keyframes tigerBob {
          0%, 100% { transform: translateY(0) scaleY(1); }
          50% { transform: translateY(-2px) scaleY(0.95); }
        }
        @keyframes legRunFront {
          0%, 100% { transform: rotate(-35deg); }
          50% { transform: rotate(35deg); }
        }
        @keyframes legRunBack {
          0%, 100% { transform: rotate(35deg); }
          50% { transform: rotate(-35deg); }
        }
        @keyframes tailWag {
          0%, 100% { transform: rotate(15deg); }
          50% { transform: rotate(-15deg); }
        }
        @keyframes dust {
          0% { transform: translate(0, 0) scale(1); opacity: 0.8; }
          100% { transform: translate(-10px, -5px) scale(0.2); opacity: 0; }
        }
      `}</style>
    </div>
  );
};

export default AILoadingBar;
