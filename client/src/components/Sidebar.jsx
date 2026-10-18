import React from 'react';
import { 
  LayoutDashboard, 
  ClipboardList, 
  GitFork, 
  BarChart2, 
  FileSpreadsheet, 
  FileText,
  HeartPulse,
  ClipboardCheck,
  FlaskConical,
  Stethoscope,
  Database,
  AlertTriangle
} from 'lucide-react';

export default function Sidebar({ currentPage, setCurrentPage, isOpen, onClose }) {
  const navItems = [
    // Grouped by workflow; labels match the page titles.
    { id: 'dashboard', label: 'Dashboard', section: 'Research', icon: <LayoutDashboard size={16} /> },
    { id: 'results', label: 'Benchmark Results', section: 'Research', icon: <BarChart2 size={16} /> },
    { id: 'findings', label: 'Research Findings', section: 'Research', icon: <FlaskConical size={16} /> },
    { id: 'pipeline', label: 'Governance Pipeline', section: 'Research', icon: <GitFork size={16} /> },
    { id: 'cases', label: 'Case Library', section: 'Data', icon: <ClipboardList size={16} /> },
    { id: 'experiments', label: 'Experiments', section: 'Data', icon: <FileSpreadsheet size={16} /> },
    { id: 'reports', label: 'Reports & Exports', section: 'Data', icon: <FileText size={16} /> },
    { id: 'clinician', label: 'Clinician Workspace', section: 'Clinical', icon: <HeartPulse size={16} /> },
    { id: 'review', label: 'Clinician Review', section: 'Clinical', icon: <ClipboardCheck size={16} /> },
  ];

  const handleSelect = (id) => {
    setCurrentPage(id);
    if (onClose) onClose();
  };

  return (
    <>
      {isOpen && <div className="sidebar-backdrop" onClick={onClose} />}
      <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-logo-icon"><Stethoscope size={18} aria-hidden="true" /></div>
          <div className="brand-text">
            <div className="brand-title">GovBench</div>
            <div className="brand-subtitle">Clinical AI Governance</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item, i) => (
            <React.Fragment key={item.id}>
              {item.section !== navItems[i - 1]?.section && <div className="nav-section-title">{item.section}</div>}
              <button
                className={`nav-item ${currentPage === item.id ? 'active' : ''}`}
                aria-current={currentPage === item.id ? 'page' : undefined}
                onClick={() => handleSelect(item.id)}
              >
                <span className="nav-icon">{item.icon}</span>
                <span>{item.label}</span>
              </button>
            </React.Fragment>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-footer-title">Datasets Ingested</div>
          <div className="sidebar-footer-item">
            <Database size={14} aria-hidden="true" /> 150 mixed cases (MedQA, PubMedQA, MedDialog) and 300 MedQA questions with an answer key
          </div>
          <div className="sidebar-footer-item">
            <AlertTriangle size={14} aria-hidden="true" /> Decision support only, not a diagnosis
          </div>
          <div className="sidebar-quote">
            "Responsible AI for safer clinical decision-making."
          </div>
        </div>
      </aside>
    </>
  );
}
