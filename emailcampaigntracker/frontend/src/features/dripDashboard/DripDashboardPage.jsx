import React, { useMemo } from 'react';
import {
  Clock,
  MessageSquare,
  MousePointerClick,
  Repeat,
  Send,
  Users,
} from 'lucide-react';

export default function DripDashboardPage({ dripData, filter, setFilter }) {

  const filtered = useMemo(() => {
    return dripData.filter((item) => {
      if (filter === 'all') return true;
      if (filter === 'scraped') return !item.sequence;
      if (filter === 'opened') return item.sequence?.open_count > 0;
      if (filter === 'clicked') return item.sequence?.click_count > 0;
      if (filter === 'replied') return item.sequence?.replied;
      return true;
    });
  }, [dripData, filter]);

  return (
    <div className="drip-dashboard">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '1.5rem' }}>
        <Send size={24} color="#0a66c2" />
        <h2>Drip Campaign Status</h2>
      </div>

      <div className="filter-bar">
        <button className={`filter-btn ${filter === 'all' ? 'active' : ''}`} onClick={() => setFilter('all')}>
          All Leads ({dripData.length})
        </button>
        <button className={`filter-btn ${filter === 'scraped' ? 'active' : ''}`} onClick={() => setFilter('scraped')}>
          <Users size={14} />
          Scraped ({dripData.filter((d) => !d.sequence).length})
        </button>
        <button className={`filter-btn ${filter === 'opened' ? 'active' : ''}`} onClick={() => setFilter('opened')}>
          <Clock size={14} />
          Opened ({dripData.filter((d) => d.sequence?.open_count > 0).length})
        </button>
        <button className={`filter-btn ${filter === 'clicked' ? 'active' : ''}`} onClick={() => setFilter('clicked')}>
          <MousePointerClick size={14} />
          Clicked ({dripData.filter((d) => d.sequence?.click_count > 0).length})
        </button>
        <button className={`filter-btn ${filter === 'replied' ? 'active' : ''}`} onClick={() => setFilter('replied')}>
          <MessageSquare size={14} />
          Replied ({dripData.filter((d) => d.sequence?.replied).length})
        </button>
      </div>

      <div className="table-container card">
        <table className="drip-table">
          <thead>
            <tr>
              <th>Lead</th>
              <th>Role & Company</th>
              <th>Email Status</th>
              <th>Engagement</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((item) => (
              <tr key={item.lead_id}>
                <td>
                  <div style={{ fontWeight: 600 }}>{item.name}</div>
                  <div style={{ fontSize: '0.8rem', color: '#b0b0b0' }}>
                    {item.email && item.email.includes('@') && item.email.toLowerCase() !== 'contact restricted' ? (
                      item.email
                    ) : (
                      <span style={{ fontStyle: 'italic', opacity: 0.7 }}>No contact info found</span>
                    )}
                  </div>
                </td>
                <td>
                  <div style={{ fontSize: '0.9rem' }}>{item.role || 'Lead'}</div>
                  <div style={{ fontSize: '0.8rem', color: '#0a66c2' }}>{item.company}</div>
                </td>
                <td>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <span className={`badge ${item.sequence?.sent_at ? 'badge-success' : 'badge-neutral'}`}>
                      <Send size={12} /> {item.sequence?.sent_at ? `Sent (${item.sequence.sent_count || 1})` : 'Pending'}
                    </span>
                    {item.sequence?.sent_at && (
                      <span style={{ fontSize: '0.7rem', color: '#b0b0b0' }}>
                        {new Date(item.sequence.sent_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </td>
                <td>
                  <div className="engagement-track">
                    <div className={`engagement-step ${item.sequence?.opened_at ? 'completed' : ''}`}>
                      <Clock size={14} />
                      <span>Opened {item.sequence?.open_count > 1 ? `(${item.sequence.open_count})` : ''}</span>
                    </div>
                    <div className={`engagement-step ${item.sequence?.clicked ? 'completed' : ''}`}>
                      <MousePointerClick size={14} />
                      <span>Clicked {item.sequence?.click_count > 1 ? `(${item.sequence.click_count})` : ''}</span>
                    </div>
                    <div className={`engagement-step ${item.sequence?.replied ? 'completed' : ''}`}>
                      <MessageSquare size={14} />
                      <span>Replied</span>
                    </div>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

