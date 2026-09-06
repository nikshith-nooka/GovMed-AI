import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import TopNavbar from './components/TopNavbar';
import Dashboard from './pages/Dashboard';
import RunClinicalCase from './pages/RunClinicalCase';
import ClinicalCases from './pages/ClinicalCases';
import AgentPipeline from './pages/AgentPipeline';
import ResultsComparison from './pages/ResultsComparison';
import Experiments from './pages/Experiments';
import Reports from './pages/Reports';

const PAGE_TO_PATH = {
  'dashboard': '/',
  'run-case': '/run-case',
  'cases': '/clinical-cases',
  'pipeline': '/pipeline',
  'results': '/results',
  'experiments': '/experiments',
  'reports': '/reports',
};

const PATH_TO_PAGE = {
  '/': 'dashboard',
  '/dashboard': 'dashboard',
  '/run-case': 'run-case',
  '/clinical-cases': 'cases',
  '/cases': 'cases',
  '/pipeline': 'pipeline',
  '/governance-levels': 'pipeline',
  '/results': 'results',
  '/ablation': 'results',
  '/cost-performance': 'results',
  '/experiments': 'experiments',
  '/run-experiment': 'experiments',
  '/reports': 'reports',
};

export default function App() {
  const getPageFromLocation = () => {
    if (typeof window === 'undefined') return 'dashboard';
    const path = window.location.pathname.toLowerCase().replace(/\/$/, '') || '/';
    return PATH_TO_PAGE[path] || 'dashboard';
  };

  const [currentPage, setCurrentPageState] = useState(getPageFromLocation);
  const [stats, setStats] = useState(null);
  const [cases, setCases] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Synchronized page change with browser URL
  const setCurrentPage = (pageKey) => {
    setCurrentPageState(pageKey);
    const targetPath = PAGE_TO_PATH[pageKey] || '/';
    if (window.location.pathname !== targetPath) {
      window.history.pushState({ page: pageKey }, '', targetPath);
    }
  };

  useEffect(() => {
    // Listen to browser Back / Forward buttons
    const handlePopState = () => {
      setCurrentPageState(getPageFromLocation());
    };
    window.addEventListener('popstate', handlePopState);

    // Initial URL synchronization check
    const currentPath = window.location.pathname.toLowerCase().replace(/\/$/, '') || '/';
    if (PATH_TO_PAGE[currentPath] && window.location.pathname !== (PAGE_TO_PATH[PATH_TO_PAGE[currentPath]] || '/')) {
      window.history.replaceState({ page: PATH_TO_PAGE[currentPath] }, '', PAGE_TO_PATH[PATH_TO_PAGE[currentPath]]);
    }

    // Fetch stats
    fetch('/api/stats')
      .then((res) => res.json())
      .then((data) => setStats(data))
      .catch((err) => console.warn('Using default stats:', err));

    // Fetch clinical cases
    fetch('/api/cases')
      .then((res) => res.json())
      .then((data) => setCases(data))
      .catch((err) => console.warn('Using default cases:', err));

    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const renderCurrentPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard setCurrentPage={setCurrentPage} stats={stats} />;
      case 'run-case':
        return <RunClinicalCase cases={cases} />;
      case 'cases':
        return <ClinicalCases cases={cases} setCurrentPage={setCurrentPage} />;
      case 'pipeline':
        return <AgentPipeline />;
      case 'results':
        return <ResultsComparison />;
      case 'experiments':
        return <Experiments />;
      case 'reports':
        return <Reports />;
      default:
        return <Dashboard setCurrentPage={setCurrentPage} stats={stats} />;
    }
  };

  class ErrorBoundary extends React.Component {
    constructor(props) {
      super(props);
      this.state = { hasError: false, error: null };
    }
    static getDerivedStateFromError(error) {
      return { hasError: true, error };
    }
    componentDidCatch(error, errorInfo) {
      console.error("ErrorBoundary caught:", error, errorInfo);
    }
    render() {
      if (this.state.hasError) {
        return (
          <div className="card" style={{ padding: '30px', margin: '20px', textAlign: 'center' }}>
            <h3 style={{ color: '#dc2626', marginBottom: '10px' }}>⚠️ Page Encountered an Error</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>{this.state.error?.message || 'An unexpected rendering error occurred.'}</p>
            <button className="btn btn-primary" onClick={() => window.location.href = '/'}>
              Return to Dashboard
            </button>
          </div>
        );
      }
      return this.props.children;
    }
  }

  return (
    <div className="app-layout">
      <Sidebar 
        currentPage={currentPage} 
        setCurrentPage={setCurrentPage} 
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <main className="main-content">
        <TopNavbar 
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          isSidebarOpen={sidebarOpen}
        />
        <ErrorBoundary key={currentPage}>
          {renderCurrentPage()}
        </ErrorBoundary>
      </main>
    </div>
  );
}
