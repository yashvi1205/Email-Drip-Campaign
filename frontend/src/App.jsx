import React, { useState, useEffect } from 'react';
import {
  Users,
  Activity,
  Database,
  Send,
  Menu,
  LogOut,
  ExternalLink,
  MessageSquare,
  ThumbsUp,
  Repeat,
  RefreshCw,
  Clock
} from 'lucide-react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';

const API_BASE = 'http://192.168.1.38:8001/api';

function App() {
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(new Date().toLocaleTimeString());
  const [toasts, setToasts] = useState([]);

  const addToast = (message, type = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 5000);
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Auto-refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const timestamp = new Date().getTime();
      const profilesRes = await axios.get(`${API_BASE}/profiles/raw?t=${timestamp}`);
      
      setProfiles(profilesRes.data || []);
      setLastUpdated(new Date().toLocaleTimeString());
      setLoading(false);
    } catch (error) {
      console.error("Error fetching data:", error);
      addToast("Failed to sync with backend", "error");
      setLoading(false);
    }
  };

  const triggerScrape = async () => {
    if (scraping) return;
    setScraping(true);
    addToast("Starting LinkedIn Scraper...", "info");
    try {
      await axios.post(`${API_BASE}/scrape`);
      addToast("Scraper is now running in the background", "success");
      
      // Start polling for completion
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await axios.get(`${API_BASE}/scraper-status?t=${Date.now()}`);
          const { status, timestamp, new_posts_found, error } = statusRes.data;
          
          const now = Date.now() / 1000;
          const isStale = status === 'running' && (now - timestamp) > 45;

          if (status === 'completed' || isStale || status === 'error') {
            clearInterval(pollInterval);
            setScraping(false);
            
            if (status === 'completed') {
              if (new_posts_found === 0) {
                addToast("Scraping completed: No new posts found", "info");
              } else {
                addToast(`Scraping completed: Found ${new_posts_found} new posts!`, "success");
              }
            } else if (isStale) {
              addToast("Scraper seems to have stopped or was closed", "error");
            } else if (status === 'error') {
              addToast(`Scraper error: ${error || "Unknown error"}`, "error");
            }
            fetchData(); // Refresh UI with new data
          }
        } catch (err) {
          console.error("Polling error:", err);
        }
      }, 5000); // Poll every 5 seconds
      
    } catch (error) {
      console.error("Error triggering scraper:", error);
      addToast("Failed to start scraper", "error");
      setScraping(false);
    }
  };

  return (
    <div className="app-container">
      {/* Toast Notifications */}
      <div className="toast-container">
        <AnimatePresence>
          {toasts.map(toast => (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, x: 50 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, scale: 0.9 }}
              className={`toast toast-${toast.type}`}
            >
              {toast.type === 'success' && <Activity size={18} />}
              {toast.type === 'error' && <Database size={18} />}
              {toast.type === 'info' && <Clock size={18} />}
              <span>{toast.message}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Sidebar */}
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
            {profiles.map(p => (
              <div key={p.url} style={{ fontSize: '0.8rem', color: '#b0b0b0', marginBottom: '0.5rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                • {p.name}
              </div>
            ))}
          </div>
          <motion.a
            href="https://docs.google.com/spreadsheets/d/1H68sixKlA1kiqiKc1yv4kapV2UQYEPNz9Pjj5VQwguo/edit?usp=sharing"
            target="_blank"
            rel="noreferrer"
            whileHover={{ x: 5 }}
            style={{ display: 'flex', alignItems: 'center', gap: '1rem', color: '#b0b0b0', marginBottom: '2rem', cursor: 'pointer', textDecoration: 'none' }}
          >
            <Database size={20} />
            <span>Open Google Sheet</span>
          </motion.a>
        </nav>

        <div className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'center' }}>
          <LogOut size={18} />
          <span>Sign Out</span>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <header className="header">
          <div>
            <h1>Activity Dashboard</h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#b0b0b0', fontSize: '0.9rem' }}>
              <Clock size={14} />
              <span>Last updated: {lastUpdated}</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <span style={{ color: '#b0b0b0', fontSize: '0.8rem', fontStyle: 'italic' }}>
              Auto-saves to sheet on new posts only
            </span>
            <button
              className="btn"
              style={{ background: '#353535', color: 'white', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
              onClick={fetchData}
            >
              <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>
            <button
              className="btn btn-primary"
              onClick={triggerScrape}
              disabled={scraping}
            >
              {scraping ? 'Starting...' : 'Run Scraper Now'}
            </button>
          </div>
        </header>

        {loading && profiles.length === 0 ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
            >
              <RefreshCw size={40} color="#0a66c2" />
            </motion.div>
          </div>
        ) : (
          <>
            {/* Main Profiles Grid (The original view user liked) */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '1.5rem' }}>
              <Users size={24} color="#0a66c2" />
              <h2>Monitored Profiles</h2>
            </div>
            <div className="grid" style={{ marginBottom: '4rem' }}>
              <AnimatePresence>
                {profiles.map((profile, index) => (
                  <motion.div
                    key={profile.url}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className="card"
                  >
                    {profile.is_repost && (
                      <div className="repost-indicator">
                        <Repeat size={14} color="#0a66c2" />
                        <span className="repost-badge">Repost</span>
                        <span>by <strong>{profile.reposter_name || profile.name}</strong></span>
                      </div>
                    )}

                    <div className="card-header">
                      <div className="avatar-stack">
                        {profile.photo_url ? (
                          <img
                            src={profile.photo_url}
                            alt={profile.original_author_name || profile.username}
                            className="profile-photo"
                          />
                        ) : (
                          <div className="avatar">
                            {(profile.original_author_name || profile.name).charAt(0)}
                          </div>
                        )}
                        {profile.is_repost && profile.reposter_photo && (
                          <img 
                            src={profile.reposter_photo} 
                            alt={profile.reposter_name} 
                            className="secondary-avatar"
                            title={`Reposted by ${profile.reposter_name}`}
                          />
                        )}
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <h3 style={{ fontSize: '1.1rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {profile.original_author_name || profile.name}
                        </h3>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
                          <a href={profile.url} target="_blank" rel="noreferrer" style={{ fontSize: '0.8rem', color: '#0a66c2', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                            View {profile.is_repost ? 'Reposter' : 'Profile'} <ExternalLink size={12} />
                          </a>
                        </div>
                      </div>
                      <span className={`status-badge ${profile.is_repost ? 'status-repost' : 'status-synced'}`}>
                        {profile.is_repost ? 'Repost' : 'Active'}
                      </span>
                    </div>

                    <div className="post-content" style={{ fontSize: '0.85rem' }}>
                      {profile.recent_activity && profile.recent_activity.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                          <span style={{ color: '#0a66c2', fontWeight: 600 }}>Recent Activity:</span>
                          {profile.recent_activity.map((act, i) => (
                            <div key={i} style={{ borderLeft: '2px solid #0a66c2', paddingLeft: '0.5rem', color: '#e0e0e0' }}>
                              {act}
                            </div>
                          ))}
                        </div>
                      ) : (
                        "No recent activity tracked"
                      )}
                    </div>

                    <div className="stats" style={{ borderTop: '1px solid #353535', paddingTop: '0.8rem', marginTop: 'auto' }}>
                      <div className="stat-item"><ThumbsUp size={14} /> {profile.stats?.likes || 0}</div>
                      <div className="stat-item"><MessageSquare size={14} /> {profile.stats?.comments || 0}</div>
                      <div className="stat-item"><Repeat size={14} /> {profile.stats?.reposts || 0}</div>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>

          </>
        )}
      </main>

      <style dangerouslySetInnerHTML={{
        __html: `
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .animate-spin {
          animation: spin 1s linear infinite;
        }
      `}} />
    </div>
  );
}

export default App;
