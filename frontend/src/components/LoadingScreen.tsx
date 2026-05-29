import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { stockApi } from '../api';
import { DEFAULT_FACTS } from '../constants/funFacts';

interface LoadingScreenProps {
  message?: string;
  ticker?: string;
  basket?: string[];
}

const LoadingScreen: React.FC<LoadingScreenProps> = ({ 
  message = 'Analyzing...', 
  ticker, 
  basket 
}) => {
  const [currentFactIndex, setCurrentFactIndex] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const shuffleFacts = (factsArray: string[]): string[] => {
    const shuffled = [...factsArray];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
  };

  const [facts, setFacts] = useState<string[]>(() => {
    // Shuffle default facts on initialization
    return shuffleFacts(DEFAULT_FACTS);
  });

  useEffect(() => {
    // Fetch fun facts if ticker or basket is provided
    const fetchFunFacts = async () => {
      if (ticker || basket) {
        try {
          const response = await stockApi.getFunFacts({ ticker, basket });
          if (response.facts && response.facts.length > 0) {
            setFacts(shuffleFacts(response.facts));
          }
        } catch (error) {
          // Keep using default facts on error
          console.error('Failed to fetch fun facts:', error);
        }
      }
    };

    fetchFunFacts();
  }, [ticker, basket, stockApi.getFunFacts]);

  useEffect(() => {
    // Rotate facts every 8 seconds
    const interval = setInterval(() => {
      setIsTransitioning(true);
      setTimeout(() => {
        setCurrentFactIndex((prev) => (prev + 1) % facts.length);
        setIsTransitioning(false);
      }, 500); // Wait for fade out
    }, 8000);

    return () => clearInterval(interval);
  }, [facts]);

  const currentFact = facts[currentFactIndex] || DEFAULT_FACTS[0];
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
          <div className={`text-slate-600 text-xs max-w-xs mx-auto transition-opacity duration-500 ${isTransitioning ? 'opacity-0' : 'opacity-100'}`}>
            <ReactMarkdown>{currentFact}</ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoadingScreen;
