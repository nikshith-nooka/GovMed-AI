import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import TopNavbar from './components/TopNavbar';
import Dashboard from './pages/Dashboard';
import ClinicalCases from './pages/ClinicalCases';
import AgentPipeline from './pages/AgentPipeline';
import ResultsComparison from './pages/ResultsComparison';
import Experiments from './pages/Experiments';
import Reports from './pages/Reports';
import ClinicianWorkspace from './pages/ClinicianWorkspace';
import ClinicianReview from './pages/ClinicianReview';
import ResearchFindings from './pages/ResearchFindings';

const PAGE_TO_PATH = {
  dashboard: '/',
  clinician: '/clinician',
  review: '/review',
  findings: '/findings',
  cases: '/clinical-cases',
  pipeline: '/pipeline',
  results: '/results',
  experiments: '/experiments',
  reports: '/reports',
};

const PATH_TO_PAGE = {
  '/': 'dashboard',
  '/dashboard': 'dashboard',
  '/clinician': 'clinician',
  '/review': 'review',
  '/findings': 'findings',
  '/run-case': 'clinician',
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

function pageFromLocation() {
  if (typeof window === 'undefined') return 'dashboard';
  const path = window.location.pathname.toLowerCase().replace(/\/$/, '') || '/';
  return PATH_TO_PAGE[path] || 'dashboard';
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="card" style={{ padding: '30px', margin: '20px', textAlign: 'center' }}>
          <h3 style={{ color: '#dc2626', marginBottom: '10px' }}>This page hit an error</h3>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>{this.state.error?.message || 'An unexpected rendering error occurred.'}</p>
          <button className="btn btn-primary" onClick={() => { window.location.href = '/'; }}>Return to Dashboard</button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const [currentPage, setCurrentPageState] = useState(pageFromLocation);
  const [stats, setStats] = useState(null);
  const [cases, setCases] = useState([]);
  const [casesError, setCasesError] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [prefill, setPrefill] = useState(null);
  const [caseQuery, setCaseQuery] = useState('');

  const setCurrentPage = (pageKey) => {
    setCurrentPageState(pageKey);
    const targetPath = PAGE_TO_PATH[pageKey] || '/';
    if (window.location.pathname !== targetPath) {
      window.history.pushState({ page: pageKey }, '', targetPath);
    }
  };

  const openInWorkspace = (fields) => {
    setPrefill({ ...fields, token: Date.now() });
    setCurrentPage('clinician');
  };

  const searchCases = (query) => {
    setCaseQuery(query);
    setCurrentPage('cases');
  };

  useEffect(() => {
    const handlePopState = () => setCurrentPageState(pageFromLocation());
    window.addEventListener('popstate', handlePopState);

    fetch('/api/stats')
      .then((res) => (res.ok ? res.json() : null))
      .then(setStats)
      .catch(() => setStats(null));

    fetch('/api/cases')
      .then(async (res) => {
        if (!res.ok) throw new Error(`Could not load cases (${res.status})`);
        setCases(await res.json());
      })
      .catch((err) => setCasesError(err.message));

    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const renderCurrentPage = () => {
    switch (currentPage) {
      case 'clinician':
        return <ClinicianWorkspace cases={cases} prefill={prefill} />;
      case 'review':
        return <ClinicianReview />;
      case 'findings':
        return <ResearchFindings />;
      case 'cases':
        return <ClinicalCases cases={cases} error={casesError} initialQuery={caseQuery} openInWorkspace={openInWorkspace} />;
      case 'pipeline':
        return <AgentPipeline />;
      case 'results':
        return <ResultsComparison />;
      case 'experiments':
        return <Experiments cases={cases} />;
      case 'reports':
        return <Reports />;
      default:
        return <Dashboard setCurrentPage={setCurrentPage} stats={stats} openInWorkspace={openInWorkspace} />;
    }
  };

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
          onSearch={searchCases}
          onOpenReviews={() => setCurrentPage('review')}
        />
        <ErrorBoundary key={currentPage}>
          {renderCurrentPage()}
        </ErrorBoundary>
      </main>
    </div>
  );
}
