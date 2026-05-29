import React, { useState, useEffect } from 'react';

const PRINCETON_FACTS = [
  "Princeton University was founded in 1746 as the College of New Jersey",
  "The Princeton Endowment is one of the largest university endowments in the world",
  "Princeton has produced 5 US Presidents and 3 Supreme Court Justices",
  "The endowment supports over 1,000 undergraduate scholarships annually",
  "Princeton's campus is known for its Collegiate Gothic architecture",
  "The university was renamed Princeton in 1896",
  "Princeton's endowment has funded groundbreaking research in physics and economics",
  "Albert Einstein was a faculty member at the Institute for Advanced Study in Princeton",
  "The Princeton Endowment helped establish the Princeton Plasma Physics Laboratory",
  "Princeton's financial aid program was the first to replace loans with grants",
  "The endowment supports over 500 faculty positions across disciplines",
  "Princeton has produced 49 Nobel Prize winners",
  "The university's library system holds over 14 million holdings",
  "Princeton's endowment has supported sustainability initiatives across campus",
  "The Princeton Investment Company (PRINCO) manages the university's endowment",
  "Princeton was the fourth university established in British North America",
  "The endowment has helped Princeton maintain its need-blind admission policy",
  "Princeton's Woodrow Wilson School was renamed in 2020 to the Princeton School of Public and International Affairs",
  "The university's endowment supports innovative teaching and learning initiatives",
  "Princeton's campus spans 500 acres in central New Jersey",
  "The endowment has funded the construction of state-of-the-art research facilities",
  "Princeton has produced numerous Rhodes Scholars and Marshall Scholars",
  "The Princeton Endowment has consistently delivered strong long-term returns",
  "Princeton's art museum houses over 100,000 works of art",
  "The endowment supports interdisciplinary research centers and programs",
  "Princeton was the first university to offer a course in American history",
  "The university's endowment helps fund international study opportunities for students",
  "Princeton has produced leaders in business, government, and academia worldwide",
  "The Princeton Endowment supports the university's commitment to excellence and accessibility",
  "Princeton's faculty includes members of the National Academy of Sciences and other prestigious academies",
  "The endowment has enabled Princeton to maintain its 5:1 student-to-faculty ratio"
];

const LoadingScreen: React.FC<{ message?: string }> = ({ message = 'Analyzing...' }) => {
  const [currentFactIndex, setCurrentFactIndex] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [shuffledFacts] = useState(() => [...PRINCETON_FACTS].sort(() => Math.random() - 0.5));

  useEffect(() => {
    // Rotate facts every 4 seconds
    const interval = setInterval(() => {
      setIsTransitioning(true);
      setTimeout(() => {
        setCurrentFactIndex((prev) => (prev + 1) % shuffledFacts.length);
        setIsTransitioning(false);
      }, 500); // Wait for fade out
    }, 4000);

    return () => clearInterval(interval);
  }, [shuffledFacts]);

  const currentFact = shuffledFacts[currentFactIndex] || PRINCETON_FACTS[0];
  return (
    <div className="bg-gradient-to-br from-indigo-50 via-white to-amber-50 rounded-2xl p-8 text-center">
      <div className="text-center">
        {/* Tiger Face Animation */}
        <div className="relative w-32 h-32 mx-auto mb-6">
          {/* Face */}
          <div className="absolute inset-0 bg-amber-400 rounded-full animate-[bounce_2s_infinite]">
            {/* Ears */}
            <div className="absolute -top-4 left-4 w-8 h-8 bg-amber-500 rounded-full transform -rotate-12">
              <div className="absolute inset-1.5 bg-amber-300 rounded-full"></div>
            </div>
            <div className="absolute -top-4 right-4 w-8 h-8 bg-amber-500 rounded-full transform rotate-12">
              <div className="absolute inset-1.5 bg-amber-300 rounded-full"></div>
            </div>

            {/* Stripes */}
            <div className="absolute top-6 left-3 w-6 h-1.5 bg-amber-600 rounded transform -rotate-12"></div>
            <div className="absolute top-9 left-2 w-8 h-1.5 bg-amber-600 rounded transform -rotate-6"></div>
            <div className="absolute top-12 left-1 w-10 h-1.5 bg-amber-600 rounded"></div>
            <div className="absolute top-6 right-3 w-6 h-1.5 bg-amber-600 rounded transform rotate-12"></div>
            <div className="absolute top-9 right-2 w-8 h-1.5 bg-amber-600 rounded transform rotate-6"></div>
            <div className="absolute top-12 right-1 w-10 h-1.5 bg-amber-600 rounded"></div>

            {/* Eyes */}
            <div className="absolute top-9 left-7 w-6 h-6 bg-white rounded-full flex items-center justify-center shadow-inner">
              <div className="w-3 h-3 bg-amber-800 rounded-full animate-pulse"></div>
            </div>
            <div className="absolute top-9 right-7 w-6 h-6 bg-white rounded-full flex items-center justify-center shadow-inner">
              <div className="w-3 h-3 bg-amber-800 rounded-full animate-pulse"></div>
            </div>

            {/* Nose */}
            <div className="absolute top-15 left-1/2 transform -translate-x-1/2 w-5 h-3 bg-amber-700 rounded-full"></div>

            {/* Mouth */}
            <div className="absolute top-18 left-1/2 transform -translate-x-1/2 w-6 h-3 border-b-4 border-amber-700 rounded-b-full"></div>

            {/* Whiskers */}
            <div className="absolute top-15 left-1 w-6 h-0.5 bg-amber-600 transform -rotate-12"></div>
            <div className="absolute top-17 left-0 w-8 h-0.5 bg-amber-600 transform -rotate-6"></div>
            <div className="absolute top-19 left-0 w-8 h-0.5 bg-amber-600"></div>
            <div className="absolute top-15 right-1 w-6 h-0.5 bg-amber-600 transform rotate-12"></div>
            <div className="absolute top-17 right-0 w-8 h-0.5 bg-amber-600 transform rotate-6"></div>
            <div className="absolute top-19 right-0 w-8 h-0.5 bg-amber-600"></div>
          </div>
          
          {/* Paw prints animation */}
          <div className="absolute -bottom-3 left-6 animate-[bounce_1.5s_infinite_0.2s]">
            <div className="w-3 h-3 bg-amber-400 rounded-full"></div>
            <div className="absolute -top-1.5 -left-1 w-1.5 h-1.5 bg-amber-400 rounded-full"></div>
            <div className="absolute -top-1.5 right-0 w-1.5 h-1.5 bg-amber-400 rounded-full"></div>
          </div>
          <div className="absolute -bottom-3 right-6 animate-[bounce_1.5s_infinite_0.4s]">
            <div className="w-3 h-3 bg-amber-400 rounded-full"></div>
            <div className="absolute -top-1.5 -left-1 w-1.5 h-1.5 bg-amber-400 rounded-full"></div>
            <div className="absolute -top-1.5 right-0 w-1.5 h-1.5 bg-amber-400 rounded-full"></div>
          </div>
        </div>
        
        {/* Loading text */}
        <div className="space-y-2">
          <h2 className="text-lg font-bold text-slate-800">{message}</h2>
          <div className="flex items-center justify-center gap-2">
            <div className="w-2 h-2 bg-indigo-500 rounded-full animate-[bounce_1s_infinite_0s]"></div>
            <div className="w-2 h-2 bg-indigo-500 rounded-full animate-[bounce_1s_infinite_0.2s]"></div>
            <div className="w-2 h-2 bg-indigo-500 rounded-full animate-[bounce_1s_infinite_0.4s]"></div>
          </div>
          <p className="text-slate-400 text-xs font-medium uppercase tracking-wider mb-1">Did you know?</p>
          <p className={`text-slate-600 text-xs max-w-xs mx-auto transition-opacity duration-500 ${isTransitioning ? 'opacity-0' : 'opacity-100'}`}>
            {currentFact}
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoadingScreen;
