import React, { useState, useEffect } from 'react';
import { Search, Sun, Moon, Bell, Menu, X } from 'lucide-react';

export default function TopNavbar({ onToggleSidebar, isSidebarOpen }) {
  const [darkMode, setDarkMode] = useState(() => {
    return typeof window !== 'undefined' && localStorage.getItem('govbench_theme') === 'dark';
  });

  useEffect(() => {
    if (darkMode) {
      document.documentElement.setAttribute('data-theme', 'dark');
      document.documentElement.classList.add('dark');
      localStorage.setItem('govbench_theme', 'dark');
    } else {
      document.documentElement.setAttribute('data-theme', 'light');
      document.documentElement.classList.remove('dark');
      localStorage.setItem('govbench_theme', 'light');
    }
  }, [darkMode]);

  const toggleTheme = () => {
    setDarkMode((prev) => !prev);
  };

  return (
    <header className="top-navbar">
      <div className="nav-left-group">
        <button 
          className="mobile-menu-btn" 
          onClick={onToggleSidebar}
          aria-label="Toggle Navigation Menu"
        >
          {isSidebarOpen ? <X size={20} /> : <Menu size={20} />}
        </button>

        <div className="search-bar">
          <Search size={16} className="search-icon" />
          <input 
            type="text" 
            placeholder="Search cases, experiments, or documentation..." 
          />
          <span className="cmd-k">⌘K</span>
        </div>
      </div>

      <div className="nav-right">
        <button 
          className="icon-btn theme-toggle-btn" 
          onClick={toggleTheme}
          title={darkMode ? "Switch to Light Mode" : "Switch to Dark Mode"}
          aria-label="Toggle Theme"
        >
          {darkMode ? (
            <Sun size={18} className="theme-icon sun" />
          ) : (
            <Moon size={18} className="theme-icon moon" />
          )}
        </button>
        <button className="icon-btn notification-btn" title="12 Pending Clinical Reviews">
          <Bell size={18} />
          <span className="notification-badge"></span>
        </button>
        <div className="user-profile">
          <div className="avatar-circle">N</div>
          <div className="user-info">
            <div className="user-name">Nikshith</div>
            <div className="user-role">Researcher</div>
          </div>
        </div>
      </div>
    </header>
  );
}
