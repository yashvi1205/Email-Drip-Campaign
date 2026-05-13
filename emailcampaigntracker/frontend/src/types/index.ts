export type ApiResponse<T> = {
  data: T;
  status: number;
};

export type ApiError = {
  message: string;
  status: number;
  code: string;
  requestId?: string;
};

export type User = {
  id: number;
  username: string;
  email: string;
  role: 'admin' | 'user' | 'scraper' | 'dashboard';
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login_at?: string;
};

export type AuthContext = {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  register: (username: string, email: string, password: string) => Promise<void>;
};

export type Lead = {
  id: number;
  name: string;
  email: string;
  linkedin_url: string;
  status: 'active' | 'inactive' | 'bounced';
  created_at: string;
  updated_at: string;
};

export type EmailSequence = {
  id: number;
  lead_id: number;
  tracking_id: string;
  subject_line: string;
  email_body: string;
  status: 'pending' | 'sent' | 'opened' | 'replied';
  sent_at?: string;
  opened_at?: string;
  replied_at?: string;
  created_at: string;
  updated_at: string;
};

export type Event = {
  id: number;
  lead_id: number;
  event_type: 'open' | 'click' | 'reply' | 'bounce';
  metadata?: Record<string, unknown>;
  timestamp: string;
  created_at: string;
};

export type ScraperStatus = {
  is_running: boolean;
  profiles_scraped: number;
  errors_count: number;
  last_run_at?: string;
  next_run_at?: string;
};

export type DashboardData = {
  profiles: Profile[];
  dripData: DripStats[];
  lastUpdated: string;
};

export type Profile = {
  id?: string;
  name: string;
  headline?: string;
  location?: string;
  profileUrl?: string;
  imageUrl?: string;
};

export type DripStats = {
  id: number;
  lead_id: number;
  name: string;
  email: string;
  sequences_sent: number;
  sequences_opened: number;
  sequences_replied: number;
  last_activity?: string;
};
