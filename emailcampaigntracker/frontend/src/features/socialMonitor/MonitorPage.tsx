import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ExternalLink,
  Repeat,
  ThumbsUp,
  MessageSquare,
  Users,
} from 'lucide-react';
import { Profile } from '@types/index';

interface MonitorPageProps {
  profiles: Profile[];
}

interface ProfileWithActivity extends Profile {
  is_repost?: boolean;
  reposter_name?: string;
  photo_url?: string;
  original_author_name?: string;
  reposter_photo?: string;
  url?: string;
  company?: string;
  recent_activity?: string[];
  stats?: {
    likes: number;
    comments: number;
    reposts: number;
  };
}

export default function MonitorPage({ profiles }: MonitorPageProps) {
  return (
    <>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.8rem',
          marginBottom: '1.5rem',
        }}
      >
        <Users size={24} color="#0a66c2" />
        <h2>Monitored Profiles</h2>
      </div>

      <div className="grid" style={{ marginBottom: '4rem' }}>
        <AnimatePresence>
          {(profiles as ProfileWithActivity[]).map((profile, index) => (
            <motion.div
              key={profile.profileUrl || profile.name || index}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className="card"
            >
              {profile.is_repost && (
                <div className="repost-indicator">
                  <Repeat size={14} color="#0a66c2" />
                  <span className="repost-badge">Repost</span>
                  <span>
                    by <strong>{profile.reposter_name || profile.name}</strong>
                  </span>
                </div>
              )}

              <div className="card-header">
                <div className="avatar-stack">
                  {profile.imageUrl ? (
                    <img
                      src={profile.imageUrl}
                      alt={profile.name}
                      className="profile-photo"
                    />
                  ) : (
                    <div className="avatar">
                      {(profile.original_author_name || profile.name).charAt(
                        0
                      )}
                    </div>
                  )}
                  {profile.is_repost && profile.reposter_photo && (
                    <img
                      src={profile.reposter_photo}
                      alt="Reposter"
                      className="secondary-avatar"
                    />
                  )}
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <h3
                    style={{
                      fontSize: '1.1rem',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {profile.original_author_name || profile.name}
                  </h3>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.8rem',
                      flexWrap: 'wrap',
                    }}
                  >
                    {profile.profileUrl && (
                      <a
                        href={profile.profileUrl}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          fontSize: '0.8rem',
                          color: '#0a66c2',
                          textDecoration: 'none',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.2rem',
                        }}
                      >
                        View Profile <ExternalLink size={12} />
                      </a>
                    )}
                    {profile.company && (
                      <span style={{ fontSize: '0.8rem', color: '#b0b0b0' }}>
                        at <strong>{profile.company}</strong>
                      </span>
                    )}
                  </div>
                </div>

                <span
                  className={`status-badge ${
                    profile.is_repost
                      ? 'status-repost'
                      : 'status-synced'
                  }`}
                >
                  {profile.is_repost ? 'Repost' : 'Active'}
                </span>
              </div>

              <div className="post-content">
                {profile.recent_activity &&
                profile.recent_activity.length > 0 ? (
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.4rem',
                    }}
                  >
                    <span style={{ color: '#0a66c2', fontWeight: 600 }}>
                      Recent Activity:
                    </span>
                    {profile.recent_activity.map((act, i) => (
                      <div
                        key={i}
                        style={{
                          borderLeft: '2px solid #0a66c2',
                          paddingLeft: '0.5rem',
                          color: '#e0e0e0',
                        }}
                      >
                        {act}
                      </div>
                    ))}
                  </div>
                ) : (
                  'No recent activity tracked'
                )}
              </div>

              <div className="stats">
                <div className="stat-item">
                  <ThumbsUp size={14} /> {profile.stats?.likes || 0}
                </div>
                <div className="stat-item">
                  <MessageSquare size={14} /> {profile.stats?.comments || 0}
                </div>
                <div className="stat-item">
                  <Repeat size={14} /> {profile.stats?.reposts || 0}
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </>
  );
}
