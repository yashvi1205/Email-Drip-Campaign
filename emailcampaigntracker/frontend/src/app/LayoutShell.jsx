import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  Database,
  ExternalLink,
  LogOut,
  MousePointerClick,
  Repeat,
  RefreshCw,
  Send,
  ThumbsUp,
  Users,
  Clock,
  MessageSquare,
} from 'lucide-react';

export default function LayoutShell({ children, profiles, view, loading, lastUpdated, onRefresh, onRunScraper, scraping }) {
  const navigate = useNavigate();
  return (
    <div className="app-container">
      {/* Toast Notifications are rendered by parent */}

      <aside className="sidebar">
        <div className="logo">
          <Activity size={28} />
          <span>LinkedIn Scraper</span>
        </div>

        <nav style={{ marginTop: '3rem', flex: 1, overflowY: 'auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', color: '#0a66c2', marginBottom: '1rem' }}>
            <Users size={20} />
            <span style={{ fontWeight: 600 }}>Tracked Profiles ({profiles.length})</span>
          </div>

          <div style={{ marginLeft: '2rem', marginBottom: '2rem' }}>
            {profiles.slice(0, 5).map((p) => (
              <div
                key={p.url}
                style={{
                  fontSize: '0.8rem',
                  color: '#b0b0b0',
                  marginBottom: '0.5rem',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                • {p.name}
              </div>
            ))}
          </div>

          {/* keep the same external link */}
          <div style={{ marginBottom: '2rem' }}>
            <a
              href="https://docs.google.com/spreadsheets/d/1H68sixKlA1kiqiKc1yv4kapV2UQYEPNz9Pjj5VQwguo/edit?usp=sharing"
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '1rem',
                color: '#b0b0b0',
                cursor: 'pointer',
                textDecoration: 'none',
              }}
            >
              <Database size={20} />
              <span>Open Google Sheet</span>
            </a>
          </div>

          <div
            className={`nav-item ${view === 'monitor' ? 'active' : ''}`}
            onClick={() => navigate('/monitor')}
            style={{ display: 'flex', alignItems: 'center', gap: '1rem', color: view === 'monitor' ? '#0a66c2' : '#b0b0b0', marginBottom: '1.5rem', cursor: 'pointer' }}
          >
            <Activity size={20} />
            <span>Social Monitor</span>
          </div>

          <div
            className={`nav-item ${view === 'drip' ? 'active' : ''}`}
            onClick={() => navigate('/drip')}
            style={{ display: 'flex', alignItems: 'center', gap: '1rem', color: view === 'drip' ? '#0a66c2' : '#b0b0b0', marginBottom: '1.5rem', cursor: 'pointer' }}
          >
            <Send size={20} />
            <span>Drip Dashboard</span>
          </div>
        </nav>

        <div className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'center' }}>
          <LogOut size={18} />
          <span>Sign Out</span>
        </div>
      </aside>

      <main className="main-content">
        <header className="header">
          <div>
            <h1>{view === 'monitor' ? 'Social Activity' : 'Drip Campaign'} Dashboard</h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#b0b0b0', fontSize: '0.9rem' }}>
              <Clock size={14} />
              <span>Last updated: {lastUpdated}</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <button
              className="btn"
              style={{ background: '#353535', color: 'white', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
              onClick={onRefresh}
            >
              <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>
            <button
              className="btn btn-primary"
              onClick={onRunScraper}
              disabled={scraping}
            >
              {scraping ? 'Starting...' : 'Run Scraper Now'}
            </button>
          </div>
        </header>

        {children}
      </main>
    </div>
  );
}

