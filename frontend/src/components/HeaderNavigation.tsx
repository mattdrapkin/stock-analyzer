import React, { useEffect } from 'react';

export interface Section {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  visible: boolean;
}

interface HeaderNavigationProps {
  sections: Section[];
  activeSection: string;
  onSectionClick: (sectionId: string) => void;
}

const HeaderNavigation: React.FC<HeaderNavigationProps> = ({ sections, activeSection, onSectionClick }) => {
  const handleScrollToSection = (sectionId: string) => {
    const element = document.getElementById(sectionId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
      onSectionClick(sectionId);
    }
  };

  // Update active section based on scroll position
  useEffect(() => {
    const visibleSections = sections.filter(s => s.visible);
    if (visibleSections.length === 0) return;

    let ticking = false;

    const handleScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          const header = document.querySelector('header');
          const headerHeight = header ? header.offsetHeight : 0;
          const scrollPosition = window.scrollY + headerHeight + 20;

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
          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [sections, onSectionClick]);

  const visibleSections = sections.filter(s => s.visible);

  if (visibleSections.length === 0) return null;

  return (
    <nav className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
      {visibleSections.map((section) => {
        const Icon = section.icon;
        const isActive = activeSection === section.id;

        return (
          <button
            key={section.id}
            onClick={() => handleScrollToSection(section.id)}
            className={`
              flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all
              ${isActive 
                ? 'bg-white text-indigo-600 shadow-sm' 
                : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
              }
            `}
            title={section.label}
          >
            <Icon className="w-4 h-4" />
            <span className="hidden sm:inline">{section.label}</span>
          </button>
        );
      })}
    </nav>
  );
};

export default HeaderNavigation;
