import { 
  LayoutDashboard, 
  ClipboardList, 
  GitFork, 
  BarChart2, 
  FileSpreadsheet, 
  FileText,
  HeartPulse,
  ClipboardCheck,
  FlaskConical
} from 'lucide-react';

export default function Sidebar({ currentPage, setCurrentPage, isOpen, onClose }) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={16} /> },
    { id: 'clinician', label: 'Clinician Workspace', icon: <HeartPulse size={16} /> },
    { id: 'review', label: 'Clinician Review', icon: <ClipboardCheck size={16} /> },
    { id: 'findings', label: 'Research Findings', icon: <FlaskConical size={16} /> },
    { id: 'cases', label: 'Clinical Cases Dataset', icon: <ClipboardList size={16} /> },
    { id: 'pipeline', label: 'Agent Pipeline & Governance', icon: <GitFork size={16} /> },
    { id: 'results', label: 'Benchmark Analytics', icon: <BarChart2 size={16} /> },
    { id: 'experiments', label: 'Experiments', icon: <FileSpreadsheet size={16} /> },
    { id: 'reports', label: 'Reports & LaTeX Export', icon: <FileText size={16} /> },
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
          <div className="brand-logo-icon">🩺</div>
          <div className="brand-text">
            <div className="brand-title">GovBench</div>
            <div className="brand-subtitle">Clinical AI Governance</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${currentPage === item.id ? 'active' : ''}`}
              onClick={() => handleSelect(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-footer-title">Datasets Ingested</div>
          <div className="sidebar-footer-item">
            <span>📦</span> 150 cases: MedQA, PubMedQA, MedDialog (50 each)
          </div>
          <div className="sidebar-footer-item">
            <span>⚠️</span> Decision support only, not a diagnosis
          </div>
          <div className="sidebar-quote">
            "Responsible AI for safer clinical decision-making."
          </div>
        </div>
      </aside>
    </>
  );
}
