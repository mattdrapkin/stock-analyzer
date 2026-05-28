import React, { useState, useEffect } from 'react';
import { 
  Info, 
  Newspaper, 
  MessageSquare, 
  TrendingUp,
  Layers,
  Menu,
  X
} from 'lucide-react';

export interface Section {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  visible: boolean;
}

interface SidebarProps {
  sections: Section[];
  activeSection: string;
  onSectionClick: (sectionId: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ sections, activeSection, onSectionClick }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  const handleScrollToSection = (sectionId: string) => {
    const element = document.getElementById(sectionId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
      onSectionClick(sectionId);
      setIsMobileOpen(false);
    }
  };

  // Update active section based on scroll position
  useEffect(() => {
    const handleScroll = () => {
      const visibleSections = sections.filter(s => s.visible);
      if (visibleSections.length === 0) return;

      const scrollPosition = window.scrollY + 100;
      
      for (let i = visibleSections.length - 1; i >= 0; i--) {
        const section = visibleSections[i];
        const element = document.getElementById(section.id);
        if (element) {
          const offsetTop = element.offsetTop;
          if (scrollPosition >= offsetTop) {
            onSectionClick(section.id);
            break;
          }
        }
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [sections, onSectionClick]);

  const visibleSections = sections.filter(s => s.visible);

  return (
    <>
      {/* Mobile Toggle Button */}
      <button
        onClick={() => setIsMobileOpen(!isMobileOpen)}
        className="lg:hidden fixed bottom-6 left-6 bg-indigo-600 text-white p-4 rounded-full shadow-lg z-30"
        title="Toggle navigation"
      >
        {isMobileOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
      </button>

      {/* Mobile Overlay */}
      {isMobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-20"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed left-0 top-20 bottom-0 z-20
          bg-white border-r border-slate-200 shadow-sm
          transition-all duration-300 ease-in-out
          ${isCollapsed ? 'w-16' : 'w-64'}
          ${isMobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        {/* Collapse Toggle (Desktop) */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="hidden lg:flex absolute right-0 top-4 -mr-3 bg-white border border-slate-200 rounded-full p-1.5 shadow-sm hover:shadow-md transition-shadow"
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <ChevronIcon isCollapsed={isCollapsed} />
        </button>

        {/* Navigation */}
        <nav className="p-4 h-full overflow-y-auto">
          <ul className="space-y-1">
            {visibleSections.map((section) => {
              const Icon = section.icon;
              const isActive = activeSection === section.id;

              return (
                <li key={section.id}>
                  <button
                    onClick={() => handleScrollToSection(section.id)}
                    className={`
                      w-full flex items-center gap-3 px-3 py-2.5 rounded-lg
                      transition-all duration-200
                      ${isActive 
                        ? 'bg-indigo-50 text-indigo-700 font-medium' 
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                      }
                      ${isCollapsed ? 'justify-center' : ''}
                    `}
                    title={isCollapsed ? section.label : ''}
                  >
                    <Icon className={`w-5 h-5 shrink-0 ${isActive ? 'text-indigo-600' : ''}`} />
                    {!isCollapsed && (
                      <span className="truncate">{section.label}</span>
                    )}
                    {isActive && !isCollapsed && (
                      <div className="ml-auto w-1.5 h-1.5 bg-indigo-600 rounded-full" />
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      </aside>
    </>
  );
};

const ChevronIcon: React.FC<{ isCollapsed: boolean }> = ({ isCollapsed }) => (
  <svg
    className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isCollapsed ? 'rotate-180' : ''}`}
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d={isCollapsed ? 'M9 5l7 7-7 7' : 'M15 19l-7-7 7-7'}
    />
  </svg>
);

export default Sidebar;
