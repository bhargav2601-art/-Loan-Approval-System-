import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Award,
  BadgeCheck,
  BarChart3,
  Bot,
  Briefcase,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  GraduationCap,
  Heart,
  Info,
  Landmark,
  LockKeyhole,
  LogOut,
  Mail,
  Menu,
  MessageCircle,
  PieChart,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Table2,
  Target,
  ThumbsUp,
  TrendingUp,
  UserPlus,
  UserRound,
  Wallet,
  X,
  XCircle,
} from 'lucide-react';
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
} from 'chart.js';
import { Bar, Doughnut } from 'react-chartjs-2';
import './styles.css';

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend);

const API_BASE = import.meta.env.VITE_API_BASE || '';

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || 'Something went wrong');
  }
  return data;
}

function resolveAssetUrl(path) {
  if (!path) return '';
  if (/^https?:\/\//.test(path)) return path;
  if (!API_BASE) return path;
  return `${API_BASE}${path}`;
}

function currency(value) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value || 0);
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(1)}%`;
}

function routeToView(pathname) {
  if (pathname === '/model-insights') return 'model-insights';
  return 'landing';
}

function viewToRoute(view) {
  if (view === 'model-insights') return '/model-insights';
  return '/';
}

function App() {
  const [user, setUser] = useState(null);
  const [view, setView] = useState(() => routeToView(window.location.pathname));
  const [authRole, setAuthRole] = useState('user');
  const [history, setHistory] = useState({ loans: [], stats: { total: 0, approved: 0, risky: 0, rejected: 0 } });
  const [latestResult, setLatestResult] = useState(null);
  const [latestFormData, setLatestFormData] = useState(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [formResetToken, setFormResetToken] = useState(0);

  useEffect(() => {
    api('/api/me')
      .then((data) => {
        if (data.user) {
          setUser(data.user);
          if (window.location.pathname === '/model-insights' && data.user.role === 'admin') {
            setView('model-insights');
          } else {
            setView(data.user.role === 'admin' ? 'admin' : 'dashboard');
          }
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const onPopState = () => setView(routeToView(window.location.pathname));
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  useEffect(() => {
    const nextPath = viewToRoute(view);
    if (window.location.pathname !== nextPath) {
      window.history.replaceState({}, '', nextPath);
    }
  }, [view]);

  async function refreshHistory() {
    if (!user) return;
    const data = await api('/api/history');
    setHistory(data);
  }

  useEffect(() => {
    refreshHistory().catch(() => {});
  }, [user]);

  async function logout() {
    await api('/api/logout', { method: 'POST', body: '{}' });
    setUser(null);
    setHistory({ loans: [], stats: { total: 0, approved: 0, risky: 0, rejected: 0 } });
    setLatestResult(null);
    setLatestFormData(null);
    setView('landing');
  }

  function startNewApplication() {
    setLatestResult(null);
    setLatestFormData(null);
    window.localStorage.clear();
    window.sessionStorage.clear();
    setFormResetToken((current) => current + 1);
    setView('apply');
  }

  const navItems = user
    ? [
        ['dashboard', user.role === 'user' ? 'Dashboard' : null],
        ['apply', user.role === 'user' ? 'Apply' : null],
        ['profile', 'Profile'],
        ['admin', user.role === 'admin' ? 'Admin' : null],
        ['model-insights', user.role === 'admin' ? 'Model Insights' : null],
      ].filter((item) => item[1])
    : [];

  return (
    <div className="app-shell">
      <div className="ambient-grid" />
      <header className="topbar">
        <button className="brand" onClick={() => setView(user ? (user.role === 'admin' ? 'admin' : 'dashboard') : 'landing')}>
          <span className="brand-mark"><Landmark size={20} /></span>
          <span>SmartLoan AI</span>
        </button>
        <nav className="nav-links">
          {navItems.map(([key, label]) => (
            <button key={key} className={view === key ? 'active' : ''} onClick={() => setView(key)}>
              {label}
            </button>
          ))}
        </nav>
        <div className="top-actions">
          {user ? (
            <>
              <span className="user-pill"><UserRound size={16} /> {user.name}</span>
              <button className="icon-btn" onClick={logout} aria-label="Logout"><LogOut size={18} /></button>
            </>
          ) : (
            <>
              <button className="ghost-btn" onClick={() => { setAuthRole('user'); setView('login'); }}>User Login</button>
              <button className="primary-btn compact" onClick={() => { setAuthRole('admin'); setView('login'); }}>Admin Login</button>
            </>
          )}
          <button className="icon-btn menu-btn" onClick={() => setMobileOpen(true)} aria-label="Menu"><Menu /></button>
        </div>
      </header>

      {mobileOpen && (
        <div className="mobile-menu">
          <button className="icon-btn close-menu" onClick={() => setMobileOpen(false)}><X /></button>
          {(user ? navItems : [['landing', 'Home'], ['login', 'User Login'], ['admin-login', 'Admin Login']]).map(([key, label]) => (
            <button key={key} onClick={() => { setView(key); setMobileOpen(false); }}>{label}</button>
          ))}
        </div>
      )}

      <main>
        {view === 'landing' && <Landing onStart={() => setView('login')} />}
        {view === 'login' && <Login initialRole={authRole} onAuthed={(nextUser) => { setUser(nextUser); setView(nextUser.role === 'admin' ? 'admin' : 'dashboard'); }} />}
        {view === 'admin-login' && <Login initialRole="admin" onAuthed={(nextUser) => { setUser(nextUser); setView(nextUser.role === 'admin' ? 'admin' : 'dashboard'); }} />}
        {view === 'dashboard' && user?.role === 'user' && <Dashboard user={user} history={history} onApply={startNewApplication} />}
        {view === 'apply' && user?.role === 'user' && <LoanForm resetToken={formResetToken} onResult={(result, formData) => { setLatestResult(result); setLatestFormData(formData); refreshHistory(); setView('result'); }} />}
        {view === 'result' && user?.role === 'user' && <Result result={latestResult || history.loans[0]} onApply={startNewApplication} />}
        {view === 'profile' && user && <Profile user={user} onLogout={logout} />}
        {view === 'admin' && user?.role === 'admin' && <Admin />}
        {view === 'model-insights' && user?.role === 'admin' && <ModelInsights />}
        {user && ((['dashboard', 'apply', 'result'].includes(view) && user.role !== 'user') || (['admin', 'model-insights'].includes(view) && user.role !== 'admin')) && <AccessDenied user={user} />}
      </main>

      {user?.role === 'user' && <Chatbot />}
    </div>
  );
}

function Landing({ onStart }) {
  const features = [
    [Sparkles, 'AI prediction', 'Instant approval intelligence using a trained risk model.'],
    [ShieldCheck, 'Explainable AI', 'Clear reasons and next best actions for every decision.'],
    [TrendingUp, 'Risk score', 'A CIBIL-like score from 0 to 100 for fast review.'],
    [Bot, 'Chatbot', 'Conversational help for rejection reasons and improvement tips.'],
  ];

  return (
    <section className="landing">
      <div className="hero-copy">
        <span className="eyebrow"><BadgeCheck size={16} /> AI banking decision engine</span>
        <h1>Loan Approval Prediction System</h1>
        <p>Approve smarter, explain faster, and give customers a premium lending experience from secure email login to AI-backed decisions.</p>
        <div className="hero-actions">
          <button className="primary-btn" onClick={onStart}>Get Started <ArrowRight size={18} /></button>
          <button className="secondary-btn" onClick={onStart}>Login</button>
        </div>
      </div>
      <div className="hero-panel">
        <div className="approval-card">
          <div>
            <span className="muted">Approval probability</span>
            <strong>82%</strong>
          </div>
          <CheckCircle2 className="approved" />
        </div>
        <div className="risk-meter">
          <span>Risk score</span>
          <div className="meter-ring">18</div>
          <small>Low risk profile detected</small>
        </div>
        <div className="mini-ledger">
          {['Verified income', 'Healthy score', 'Low existing loans'].map((item) => (
            <div key={item}><CheckCircle2 size={16} /> {item}</div>
          ))}
        </div>
      </div>
      <div className="feature-grid">
        {features.map(([Icon, title, text]) => (
          <article className="feature-card" key={title}>
            <Icon />
            <h3>{title}</h3>
            <p>{text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}


function Login({ initialRole = 'user', onAuthed }) {
  const [role, setRole] = useState(initialRole);
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({
    name: '',
    email: '',
    password: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function switchRole(nextRole) {
    setRole(nextRole);
    setError('');
    setMode('login');
    setForm({ name: '', email: '', password: '' });
  }

  async function submit(event) {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      const path = mode === 'register' ? '/api/register' : '/api/login';
      const payload = mode === 'register'
        ? { name: form.name, email: form.email, password: form.password }
        : { email: form.email, password: form.password, role };
      const data = await api(path, { method: 'POST', body: JSON.stringify(payload) });
      onAuthed(data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const adminTitle = 'Admin Portal';
  const userTitle = 'Welcome Back';
  const adminDesc = 'Access the admin dashboard to manage loan applications and view analytics.';
  const userDesc = 'Sign in to apply for loans or continue as guest to explore.';

  return (
    <section className="auth-wrap">
      <div className="auth-card">
        <span className="eyebrow"><LockKeyhole size={16} /> Secure authentication</span>
        <h2>{role === 'admin' ? adminTitle : userTitle}</h2>
        <p>{role === 'admin' ? adminDesc : userDesc}</p>

        <div className="segmented">
          <button className={role === 'user' ? 'selected' : ''} onClick={() => switchRole('user')} type="button"><UserRound size={16} /> User</button>
          <button className={role === 'admin' ? 'selected' : ''} onClick={() => switchRole('admin')} type="button"><ShieldCheck size={16} /> Admin</button>
        </div>

        <form onSubmit={submit}>
          {role === 'user' && (
            <div className="mode-switch compact-switch">
              <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')} type="button">Sign In</button>
              <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')} type="button">Register</button>
            </div>
          )}
          
          {mode === 'register' && role === 'user' && (
            <>
              <label>Full name</label>
              <div className="input-icon"><UserPlus size={18} /><input value={form.name} onChange={(event) => update('name', event.target.value)} placeholder="Enter your full name" /></div>
            </>
          )}
          
          <label>Email address</label>
          <div className="input-icon"><Mail size={18} /><input type="email" value={form.email} onChange={(event) => update('email', event.target.value)} placeholder={role === 'admin' ? "Enter admin credentials" : "name@example.com"} /></div>
          
          <label>Password</label>
          <div className="input-icon"><LockKeyhole size={18} /><input type="password" value={form.password} onChange={(event) => update('password', event.target.value)} placeholder="Enter password" /></div>
          
          {error && <div className="error"><XCircle size={16} /> {error}</div>}
          <button className="primary-btn full" disabled={loading}>
            {loading ? <span className="spinner" /> : mode === 'register' ? 'Create Account' : "Sign In as " + (role === 'admin' ? 'Admin' : 'User')}
          </button>
          
          {role === 'user' && mode === 'login' && (
            <button type="button" className="ghost-btn full" onClick={() => onAuthed({ id: 0, name: 'Guest User', email: 'guest', role: 'user' })}>
              Continue as Guest
            </button>
          )}
        </form>
      </div>
    </section>
  );
}
function Dashboard({ user, history, onApply }) {
  const stats = history.stats;
  const approvalRate = stats.total > 0 ? Math.round((stats.approved / stats.total) * 100) : 0;

  const doughnutData = useMemo(() => ({
    labels: ['Approved', 'Risky', 'Rejected'],
    datasets: [{ data: [stats.approved, stats.risky, stats.rejected], backgroundColor: ['#16a34a', '#f59e0b', '#ef4444'], borderWidth: 0 }],
  }), [history]);

  const barData = useMemo(() => ({
    labels: history.loans.slice(0, 6).reverse().map((loan) => new Date(loan.created_at).toLocaleDateString()),
    datasets: [{ label: 'Risk score', data: history.loans.slice(0, 6).reverse().map((loan) => loan.risk_score), backgroundColor: '#2563eb', borderRadius: 8 }],
  }), [history]);

  return (
    <section className="dashboard">
      <div className="section-head">
        <div>
          <span className="eyebrow"><Clock3 size={16} /> Real-time decisioning</span>
          <h2>Welcome back, {user.name}</h2>
        </div>
        <button className="primary-btn" onClick={onApply}>New Application <ChevronRight size={18} /></button>
      </div>

      {/* KPI Stats */}
      <div className="stat-grid">
        <Stat icon={CircleDollarSign} label="Applications" value={stats.total} />
        <Stat icon={CheckCircle2} label="Approved" value={stats.approved} tone="green" />
        <Stat icon={ShieldAlert} label="Under Review" value={stats.risky} tone="amber" />
        <Stat icon={XCircle} label="Rejected" value={stats.rejected} tone="red" />
        <Stat icon={Target} label="Approval Rate" value={`${approvalRate}%`} tone={approvalRate >= 60 ? 'green' : approvalRate >= 30 ? 'amber' : 'red'} />
        <Stat icon={ShieldCheck} label="Avg Confidence" value={formatPercent(stats.avg_confidence)} />
      </div>

      {/* Charts */}
      <div className="analytics-grid">
        <div className="panel"><h3>Approval distribution</h3><Doughnut data={doughnutData} options={{ cutout: '72%', plugins: { legend: { position: 'bottom' } } }} /></div>
        <div className="panel"><h3>Risk score trend</h3><Bar data={barData} options={{ responsive: true, scales: { y: { min: 0, max: 100 } } }} /></div>
      </div>

      {/* Financial Health */}
      {stats.avg_risk !== undefined && (
        <div className="panel">
          <h3><Heart size={16} style={{display:'inline',marginRight:6}} />Financial Health Overview</h3>
          <div className="fin-health-grid">
            <FinHealthBar label="Avg Risk Score" value={stats.avg_risk} max={100} tone={stats.avg_risk < 35 ? 'green' : stats.avg_risk < 65 ? 'amber' : 'red'} />
            <FinHealthBar label="Avg Confidence" value={stats.avg_confidence} max={100} tone="blue" />
            <FinHealthBar label="Approval Rate" value={approvalRate} max={100} tone={approvalRate >= 50 ? 'green' : 'amber'} />
          </div>
        </div>
      )}

      {/* Recent applications */}
      <div className="panel">
        <h3>Recent applications</h3>
        <HistoryTable loans={history.loans} />
      </div>
    </section>
  );
}

function FinHealthBar({ label, value, max = 100, tone = 'blue' }) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  return (
    <div className="fin-health-bar">
      <div className="fin-health-bar-header"><span>{label}</span><strong>{Math.round(value)}</strong></div>
      <div className="fin-health-track"><div className={`fin-health-fill ${tone}`} style={{ width: `${pct}%` }} /></div>
    </div>
  );
}

function Stat({ icon: Icon, label, value, tone = 'blue' }) {
  return <div className={`stat-card ${tone}`}><Icon /><span>{label}</span><strong>{value}</strong></div>;
}

function LoanRow({ loan }) {
  return (
    <div className="loan-row">
      <div><strong>{currency(loan.loan_amount)}</strong><span>{loan.user_email || new Date(loan.created_at).toLocaleDateString()}</span></div>
      <div><span>Credit</span><strong>{loan.credit_score}</strong></div>
      <div><span>Risk</span><strong>{loan.risk_score}</strong></div>
      <span className={`status ${loan.status.toLowerCase()}`}>{loan.status}</span>
    </div>
  );
}

function HistoryTable({ loans }) {
  if (loans.length === 0) {
    return <p className="muted">No applications yet. Run your first AI decision.</p>;
  }
  return (
    <div className="admin-table">
      <div className="admin-row user-history header">
        <span>Date</span><span>Amount</span><span>Employment</span><span>Status</span><span>Risk</span><span>Confidence</span>
      </div>
      {loans.map((loan) => (
        <div className="admin-row user-history" key={loan.id}>
          <span>{new Date(loan.created_at).toLocaleDateString()}</span>
          <span>{currency(loan.loan_amount)}</span>
          <span style={{textTransform:'capitalize'}}>{loan.employment_status || '—'}</span>
          <span className={`status ${(loan.status || '').toLowerCase().replace(/\s+/g, '-')}`}>{loan.status}</span>
          <span>{loan.risk_score}/100</span>
          <span>{formatPercent(loan.confidence_score)}</span>
        </div>
      ))}
    </div>
  );
}

// Salary bands — mirrors underwriting_engine.py SALARY_BANDS exactly
const SALARY_BANDS_JS = [
  { minAge: 20, maxAge: 22, normalMin: 8000,  normalMax: 35000,  warningAbove: 35000,  reviewAbove: 40000,  rejectAbove: 60000  },
  { minAge: 23, maxAge: 25, normalMin: 15000, normalMax: 60000,  warningAbove: 60000,  reviewAbove: 70000,  rejectAbove: 90000  },
  { minAge: 26, maxAge: 30, normalMin: 20000, normalMax: 120000, warningAbove: 120000, reviewAbove: 140000, rejectAbove: 180000 },
  { minAge: 31, maxAge: 40, normalMin: 25000, normalMax: 250000, warningAbove: 250000, reviewAbove: 280000, rejectAbove: 350000 },
  { minAge: 41, maxAge: 55, normalMin: 25000, normalMax: 400000, warningAbove: 400000, reviewAbove: 450000, rejectAbove: 550000 },
];

function getSalaryValidation(age, income) {
  if (!age || !income) return null;
  const band = SALARY_BANDS_JS.find((b) => age >= b.minAge && age <= b.maxAge);
  if (!band) return null;
  const inc = Number(income);
  if (!inc) return null;
  if (inc > band.rejectAbove) {
    return { level: 'reject', icon: '\u274C', label: 'Manual Review', message: `Income \u20B9${inc.toLocaleString('en-IN')} is not realistic for age ${age}. Expected up to \u20B9${band.normalMax.toLocaleString('en-IN')}.` };
  }
  if (inc > band.reviewAbove) {
    return { level: 'review', icon: '\u274C', label: 'Manual Review', message: `Income is unusually high for age ${age} and will need verification. Expected \u20B9${band.normalMin.toLocaleString('en-IN')}\u2013\u20B9${band.normalMax.toLocaleString('en-IN')}.` };
  }
  if (inc > band.warningAbove) {
    return { level: 'warning', icon: '\u26A0\uFE0F', label: 'Warning', message: `Salary is above the typical range for age ${age}. Expected \u20B9${band.normalMin.toLocaleString('en-IN')}\u2013\u20B9${band.normalMax.toLocaleString('en-IN')}.` };
  }
  if (inc < band.normalMin) {
    return { level: 'warning', icon: '\u26A0\uFE0F', label: 'Warning', message: `Income \u20B9${inc.toLocaleString('en-IN')} is below the typical range for age ${age}. Expected \u20B9${band.normalMin.toLocaleString('en-IN')}\u2013\u20B9${band.normalMax.toLocaleString('en-IN')}.` };
  }
  return { level: 'normal', icon: '\u2714', label: 'Normal', message: `Income is within the expected range for age ${age} (\u20B9${band.normalMin.toLocaleString('en-IN')}\u2013\u20B9${band.normalMax.toLocaleString('en-IN')}).` };
}

function LoanForm({ onResult, resetToken }) {
  const presetTenureYears = ['1', '2', '3', '5', '10'];
  const defaultForm = {
    age: '',
    income: '',
    credit_score: '',
    employment_status: '',
    // student fields
    student_earning: '',
    income_source: '',
    parent_guardian_income: '',
    sponsor_available: '',
    education: '',
    graduation_year: '',
    scholarship: '',
    education_loan: '',
    financial_support: '',
    monthly_stipend: '',
    // unemployed fields
    source_of_income: '',
    savings_amount: '',
    investments_amount: '',
    rental_income: '',
    emergency_fund: '',
    co_applicant_available: '',
    // salaried fields
    company_name: '',
    work_experience: '',
    // business fields
    business_type: '',
    years_in_business: '',
    ownership_type: '',
    // loan fields
    loan_amount: '',
    existing_loans: '',
    loan_type: '',
    previous_loan: '',
    previous_loan_amount: '',
    loan_tenure: '',
  };
  const [form, setForm] = useState(defaultForm);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [scenario, setScenario] = useState(null);
  const [scenarioError, setScenarioError] = useState('');
  const [simulating, setSimulating] = useState(false);
  const [tenureMode, setTenureMode] = useState('list');
  const [customTenureYears, setCustomTenureYears] = useState('');
  const [selectedTenureYears, setSelectedTenureYears] = useState('');
  const ageValue = Number(form.age);
  const ageError = form.age && (ageValue < 20 || ageValue > 55) ? 'Eligible age must be between 20 and 55 years.' : '';
  const salaryValidation = form.employment_status === 'salaried' && form.age && form.income
    ? getSalaryValidation(ageValue, form.income)
    : null;
  const salaryBlocksSubmit = salaryValidation?.level === 'reject';
  const predictionDisabled = loading || Boolean(ageError) || salaryBlocksSubmit;

  function resetForm() {
    setForm(defaultForm);
    setError('');
    setLoading(false);
    setScenario(null);
    setScenarioError('');
    setSimulating(false);
    setTenureMode('list');
    setCustomTenureYears('');
    setSelectedTenureYears('');
  }

  useEffect(() => {
    resetForm();
  }, [resetToken]);

  function update(key, value) {
    setForm((current) => {
      const newForm = { ...current, [key]: value };

      if (key === 'previous_loan' && value === 'No') {
        newForm.previous_loan_amount = '';
      }
      if (key === 'employment_status') {
        Object.assign(newForm, {
          income: '',
          // student
          student_earning: '',
          income_source: '',
          parent_guardian_income: '',
          sponsor_available: '',
          education: '',
          graduation_year: '',
          scholarship: '',
          education_loan: '',
          financial_support: '',
          monthly_stipend: '',
          // unemployed
          source_of_income: '',
          savings_amount: '',
          investments_amount: '',
          rental_income: '',
          emergency_fund: '',
          co_applicant_available: '',
          // salaried
          company_name: '',
          work_experience: '',
          // business
          business_type: '',
          years_in_business: '',
          ownership_type: '',
        });
      }
      if (key === 'student_earning') {
        newForm.income = '';
        newForm.income_source = '';
        newForm.parent_guardian_income = '';
        newForm.sponsor_available = '';
      }

      return newForm;
    });
  }

  function selectTenure(value) {
    if (value === 'other') {
      setTenureMode('custom');
      setError('');
      setSelectedTenureYears('');
      update('loan_tenure', '');
      return;
    }

    setTenureMode('list');
    setSelectedTenureYears(value);
    setCustomTenureYears('');
    update('loan_tenure', String(Number(value) * 12));
  }

  function handleCustomTenure(value) {
    const sanitized = value.replace(/\D/g, '');
    setCustomTenureYears(sanitized);
    setError('');
    if (!sanitized) return;

    const years = Number(sanitized);
    if (years >= 1 && years <= 30) {
      update('loan_tenure', String(years * 12));
    }
  }

  function usePresetTenure() {
    setTenureMode('list');
    setCustomTenureYears('');
    setError('');
    update('loan_tenure', String(Number(selectedTenureYears) * 12));
  }

  function buildPayload(strict = false) {
    const required = ['age', 'credit_score', 'loan_amount', 'loan_type', 'employment_status', 'previous_loan'];
    if (required.some((field) => !String(form[field] ?? '').trim())) return null;
    if (ageError) {
      if (strict) setError(ageError);
      return null;
    }

    const employmentRequired = [];
    if (form.employment_status === 'student') {
      employmentRequired.push('student_earning', 'education', 'graduation_year', 'scholarship', 'education_loan');
      if (form.student_earning === 'Yes') {
        employmentRequired.push('income', 'income_source');
      }
      if (form.student_earning === 'No') {
        employmentRequired.push('parent_guardian_income', 'sponsor_available');
      }
    } else if (form.employment_status === 'unemployed') {
      employmentRequired.push('income', 'source_of_income', 'savings_amount', 'investments_amount', 'sponsor_available', 'co_applicant_available');
    } else if (form.employment_status === 'salaried') {
      employmentRequired.push('income', 'company_name', 'work_experience');
    } else if (form.employment_status === 'business') {
      employmentRequired.push('income', 'business_type', 'years_in_business', 'ownership_type');
    }

    const missingEmploymentField = employmentRequired.find((field) => !String(form[field] ?? '').trim());
    if (missingEmploymentField) {
      if (strict) {
        setError('Please complete all employment details before submitting.');
      }
      return null;
    }

    let tenureMonths = form.loan_tenure;
    if (tenureMode === 'custom') {
      if (!customTenureYears) return null;
      const years = Number(customTenureYears);
      if (!Number.isInteger(years) || years < 1 || years > 30) {
        if (strict) {
          setError('Loan tenure must be between 1 and 30 years.');
        }
        return null;
      }
      tenureMonths = String(years * 12);
    }

    if (form.previous_loan === 'Yes' && !String(form.previous_loan_amount || '').trim()) {
      if (strict) {
        setError('Please enter your previous loan amount.');
      }
      return null;
    }

    return {
      ...form,
      income: form.employment_status === 'student' && form.student_earning === 'No' ? '' : form.income,
      existing_loans: form.existing_loans || '0',
      loan_tenure: tenureMonths,
    };
  }

  useEffect(() => {
    const payload = buildPayload(false);
    if (!payload) {
      setScenario(null);
      setScenarioError('');
      return undefined;
    }

    const timeoutId = window.setTimeout(async () => {
      setSimulating(true);
      try {
        const data = await api('/api/simulate', { method: 'POST', body: JSON.stringify(payload) });
        setScenario(data);
        setScenarioError('');
      } catch (err) {
        setScenario(null);
        setScenarioError(err.message);
      } finally {
        setSimulating(false);
      }
    }, 280);

    return () => window.clearTimeout(timeoutId);
  }, [form, tenureMode, customTenureYears, selectedTenureYears]);

  async function submit(event) {
    event.preventDefault();
    setError('');
    const payload = buildPayload(true);
    if (!payload) return;

    setLoading(true);
    try {
      const data = await api('/api/predict', { method: 'POST', body: JSON.stringify(payload) });
      onResult(data, payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="form-layout">
      <div className="form-intro">
        <span className="eyebrow"><PieChart size={16} /> AI underwriting</span>
        <h2>Loan Application</h2>
        <p>Enter your details and choose a loan tenure. We'll calculate your EMI and provide an instant decision with explainable reasoning.</p>
        <div className="panel simulator-panel">
          <div className="simulator-head">
            <div>
              <span className="muted">What-if simulator</span>
              <h3>Live affordability preview</h3>
            </div>
            {simulating && <span className="muted">Refreshing...</span>}
          </div>
          {scenario ? (
            <>
              <div className="preview-score">
                <RiskMeter score={scenario.risk_score} />
                <div className="preview-copy">
                  <strong>{scenario.status}</strong>
                  <span>{formatPercent(scenario.approval_probability)} approval probability</span>
                  <span>{formatPercent(scenario.confidence_score)} confidence</span>
                </div>
              </div>
              <div className="metric-grid compact">
                <Metric label="EMI" value={currency(scenario.calculated_emi)} />
                <Metric label="Rate" value={formatPercent(scenario.interest_rate)} />
                <Metric label="DTI" value={formatPercent(scenario.metrics.dti_ratio)} />
                <Metric label="EMI / Income" value={formatPercent(scenario.metrics.emi_to_income_ratio)} />
              </div>
              <p className="muted preview-note">{scenario.top_factors[0]?.title || 'Fill in the form to preview the strongest underwriting signal.'}</p>
            </>
          ) : (
            <p className="muted preview-note">{scenarioError || 'The simulator will start once the key affordability fields are filled.'}</p>
          )}
        </div>
      </div>
      <form className="loan-form" onSubmit={submit}>
        <Field
          label="Age"
          value={form.age}
          onChange={(value) => update('age', value)}
          placeholder="28"
          min="20"
          max="55"
          invalid={Boolean(ageError)}
          describedBy="age-validation-message"
        />
        {ageError && <div id="age-validation-message" className="field-error">{ageError}</div>}
        <Field label="Credit score" value={form.credit_score} onChange={(value) => update('credit_score', value)} placeholder="720" />
        <label>Employment status</label>
        <select value={form.employment_status} onChange={(event) => update('employment_status', event.target.value)} required>
          <option value="" disabled>Select employment status</option>
          <option value="salaried">Salaried</option>
          <option value="business">Business</option>
          <option value="student">Student</option>
          <option value="unemployed">Unemployed</option>
        </select>

        {form.employment_status === 'student' && (
          <div className="conditional-fields">
            <TextField label="Course / Degree" value={form.education} onChange={(value) => update('education', value)} placeholder="B.Tech, MBA, B.Com..." />
            <Field label="Expected graduation year" value={form.graduation_year} onChange={(value) => update('graduation_year', value)} placeholder="2026" min="2020" max="2035" />
            <label>Scholarship available?</label>
            <select value={form.scholarship} onChange={(event) => update('scholarship', event.target.value)} required>
              <option value="" disabled>Select an option</option>
              <option value="Yes">Yes</option>
              <option value="No">No</option>
            </select>
            <label>Existing education loan?</label>
            <select value={form.education_loan} onChange={(event) => update('education_loan', event.target.value)} required>
              <option value="" disabled>Select an option</option>
              <option value="Yes">Yes</option>
              <option value="No">No</option>
            </select>
            <label>Are you currently earning?</label>
            <select value={form.student_earning} onChange={(event) => update('student_earning', event.target.value)} required>
              <option value="" disabled>Select an option</option>
              <option value="Yes">Yes</option>
              <option value="No">No</option>
            </select>
            {form.student_earning === 'Yes' && (
              <>
                <Field label="Monthly income / stipend (₹)" value={form.income} onChange={(value) => update('income', value)} placeholder="18000" />
                <label>Income source</label>
                <select value={form.income_source} onChange={(event) => update('income_source', event.target.value)} required>
                  <option value="" disabled>Select income source</option>
                  <option value="Internship">Internship</option>
                  <option value="Freelancing">Freelancing</option>
                  <option value="Part-time">Part-time</option>
                </select>
                <Field label="Monthly stipend (₹)" value={form.monthly_stipend} onChange={(value) => update('monthly_stipend', value)} placeholder="15000" />
              </>
            )}
            {form.student_earning === 'No' && (
              <>
                <Field label="Parent / Guardian income (₹)" value={form.parent_guardian_income} onChange={(value) => update('parent_guardian_income', value)} placeholder="65000" />
                <TextField label="Source of financial support" value={form.financial_support} onChange={(value) => update('financial_support', value)} placeholder="Parents, scholarship fund, employer..." />
                <label>Sponsor available?</label>
                <select value={form.sponsor_available} onChange={(event) => update('sponsor_available', event.target.value)} required>
                  <option value="" disabled>Select an option</option>
                  <option value="Yes">Yes</option>
                  <option value="No">No</option>
                </select>
              </>
            )}
          </div>
        )}

        {form.employment_status === 'unemployed' && (
          <div className="conditional-fields">
            <Field label="Declared monthly income (₹)" value={form.income} onChange={(value) => update('income', value)} placeholder="25000" />
            <TextField label="Source of income" value={form.source_of_income} onChange={(value) => update('source_of_income', value)} placeholder="Rent, investments, family support" />
            <Field label="Savings amount (₹)" value={form.savings_amount} onChange={(value) => update('savings_amount', value)} placeholder="150000" />
            <Field label="Investments (₹)" value={form.investments_amount} onChange={(value) => update('investments_amount', value)} placeholder="50000" />
            <Field label="Rental income / month (₹)" value={form.rental_income} onChange={(value) => update('rental_income', value)} placeholder="0" />
            <Field label="Emergency fund (₹)" value={form.emergency_fund} onChange={(value) => update('emergency_fund', value)} placeholder="0" />
            <label>Sponsor available?</label>
            <select value={form.sponsor_available} onChange={(event) => update('sponsor_available', event.target.value)} required>
              <option value="" disabled>Select an option</option>
              <option value="Yes">Yes</option>
              <option value="No">No</option>
            </select>
            <label>Co-applicant available?</label>
            <select value={form.co_applicant_available} onChange={(event) => update('co_applicant_available', event.target.value)} required>
              <option value="" disabled>Select an option</option>
              <option value="Yes">Yes</option>
              <option value="No">No</option>
            </select>
          </div>
        )}

        {form.employment_status === 'salaried' && (
          <div className="conditional-fields">
            <Field
              label="Monthly income (₹)"
              value={form.income}
              onChange={(value) => update('income', value)}
              placeholder="65000"
              invalid={salaryValidation?.level === 'reject' || salaryValidation?.level === 'review'}
            />
            {salaryValidation && (
              <div className={`salary-validation-hint salary-hint-${salaryValidation.level}`}>
                <span className="salary-hint-icon">{salaryValidation.icon}</span>
                <span className="salary-hint-label">{salaryValidation.label}</span>
                <span className="salary-hint-msg">{salaryValidation.message}</span>
              </div>
            )}
            <TextField label="Company name" value={form.company_name} onChange={(value) => update('company_name', value)} placeholder="Company name" />
            <Field label="Work experience (years)" value={form.work_experience} onChange={(value) => update('work_experience', value)} placeholder="3" />
          </div>
        )}

        {form.employment_status === 'business' && (
          <div className="conditional-fields">
            <Field label="Monthly business income (₹)" value={form.income} onChange={(value) => update('income', value)} placeholder="85000" />
            <TextField label="Business type" value={form.business_type} onChange={(value) => update('business_type', value)} placeholder="Retail, consulting, services" />
            <Field label="Years in business" value={form.years_in_business} onChange={(value) => update('years_in_business', value)} placeholder="4" />
            <label>Ownership type</label>
            <select value={form.ownership_type} onChange={(event) => update('ownership_type', event.target.value)} required>
              <option value="" disabled>Select ownership type</option>
              <option value="Startup">Startup</option>
              <option value="Partnership">Partnership</option>
              <option value="LLP">LLP</option>
              <option value="Private Limited">Private Limited</option>
              <option value="Proprietorship">Proprietorship</option>
              <option value="Inherited">Inherited</option>
            </select>
          </div>
        )}

        <Field label="Loan amount (₹)" value={form.loan_amount} onChange={(value) => update('loan_amount', value)} placeholder="350000" />
        <Field label="Existing EMIs / loans outstanding (₹)" value={form.existing_loans} onChange={(value) => update('existing_loans', value)} placeholder="15000" />
        
        <label>Loan type</label>
        <select value={form.loan_type} onChange={(event) => update('loan_type', event.target.value)} required>
          <option value="" disabled>Select loan type</option>
          <option value="Personal Loan">Personal Loan</option>
          <option value="Home Loan">Home Loan</option>
          <option value="Vehicle Loan">Vehicle Loan</option>
          <option value="Education Loan">Education Loan</option>
        </select>
        
        <label>Do you have any previous loan?</label>
        <select value={form.previous_loan} onChange={(event) => update('previous_loan', event.target.value)} required>
          <option value="" disabled>Select an option</option>
          <option value="No">No</option>
          <option value="Yes">Yes</option>
        </select>
        
        {form.previous_loan === 'Yes' && (
          <Field label="Previous loan amount (₹)" value={form.previous_loan_amount} onChange={(value) => update('previous_loan_amount', value)} placeholder="Enter previous loan amount" />
        )}

        <label>Loan tenure</label>
        <div className={`tenure-smart-field ${tenureMode === 'custom' ? 'is-custom' : ''}`}>
          <div className="tenure-field-stage">
            {tenureMode === 'list' ? (
              <select
                value={selectedTenureYears}
                onChange={(event) => selectTenure(event.target.value)}
                required
              >
                <option value="" disabled>Select tenure in years</option>
                {presetTenureYears.map((years) => (
                  <option key={years} value={years}>{years} {years === '1' ? 'year' : 'years'}</option>
                ))}
                <option value="other">Other...</option>
              </select>
            ) : (
              <div className="tenure-custom-entry">
                <input
                  type="number"
                  min="1"
                  max="30"
                  step="1"
                  inputMode="numeric"
                  value={customTenureYears}
                  onChange={(event) => handleCustomTenure(event.target.value)}
                  placeholder="Enter tenure in years"
                />
                <button type="button" className="tenure-back-btn" onClick={usePresetTenure}>
                  ← Choose from list
                </button>
              </div>
            )}
          </div>
        </div>

        {error && <div className="error"><XCircle size={16} /> {error}</div>}
        <button className="primary-btn full" disabled={predictionDisabled}>{loading ? <span className="spinner" /> : 'Get AI Decision'}</button>
      </form>
    </section>
  );
}

function Field({ label, value, onChange, placeholder, min = '0', max, invalid = false, describedBy }) {
  return (
    <>
      <label>{label}</label>
      <input
        type="number"
        min={min}
        max={max}
        className={invalid ? 'field-invalid' : ''}
        aria-invalid={invalid ? 'true' : 'false'}
        aria-describedby={describedBy}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required
      />
    </>
  );
}

function TextField({ label, value, onChange, placeholder }) {
  return (
    <>
      <label>{label}</label>
      <input type="text" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} required />
    </>
  );
}

function Metric({ label, value }) {
  return <div className="metric-card"><span>{label}</span><strong>{value}</strong></div>;
}

function RiskMeter({ score }) {
  const clamped = Math.max(0, Math.min(100, Number(score || 0)));
  const degrees = Math.round(clamped * 3.2);
  const color = clamped < 35 ? '#16a34a' : clamped < 65 ? '#f59e0b' : '#ef4444';
  return (
    <div className="score-orb dynamic" style={{ background: `conic-gradient(${color} 0 ${degrees}deg, #1e293b ${degrees}deg 360deg)` }}>
      {Math.round(clamped)}
    </div>
  );
}

function ConfidenceBar({ value }) {
  const pct = Math.min(100, Math.max(0, Number(value || 0)));
  const color = pct >= 70 ? '#16a34a' : pct >= 45 ? '#f59e0b' : '#ef4444';
  return (
    <div className="confidence-bar-wrap">
      <div className="confidence-bar-header">
        <span>Model Confidence</span>
        <strong style={{ color }}>{pct.toFixed(1)}%</strong>
      </div>
      <div className="confidence-track">
        <div className="confidence-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="confidence-label">{pct >= 70 ? 'High confidence' : pct >= 45 ? 'Moderate confidence' : 'Low confidence — manual review advised'}</span>
    </div>
  );
}

function RatioBar({ label, value, good, warn, format = 'percent' }) {
  const display = format === 'percent' ? `${(value * 100).toFixed(1)}%` : value.toFixed(2);
  const tone = value <= good ? 'green' : value <= warn ? 'amber' : 'red';
  const pct = Math.min(100, Math.round(value * 100));
  return (
    <div className="ratio-row">
      <div className="ratio-row-header"><span>{label}</span><strong className={`ratio-val ${tone}`}>{display}</strong></div>
      <div className="ratio-track"><div className={`ratio-fill ${tone}`} style={{ width: `${Math.min(pct, 100)}%` }} /></div>
    </div>
  );
}

const SEVERITY_META = {
  reject:   { cls: 'sev-reject',   label: 'Reject Rule' },
  review:   { cls: 'sev-review',   label: 'Review Flag' },
  warning:  { cls: 'sev-warning',  label: 'Risk Factor' },
  positive: { cls: 'sev-positive', label: 'Positive' },
};

const IMPACT_META = {
  High:   { cls: 'impact-high',   icon: AlertTriangle },
  Medium: { cls: 'impact-medium', icon: Info },
  Low:    { cls: 'impact-low',    icon: ThumbsUp },
};

const TIMELINE_STEPS = [
  { id: 'collection', label: 'Data Collection', desc: 'Application fields captured and validated' },
  { id: 'consistency', label: 'Consistency Check', desc: 'Cross-field logical validation' },
  { id: 'ml', label: 'ML Scoring', desc: 'Random Forest ensemble probability computed' },
  { id: 'financial', label: 'Financial Ratios', desc: 'DTI, EMI ratio, affordability scored' },
  { id: 'underwriting', label: 'Underwriting Rules', desc: 'Employment-specific business rules applied' },
  { id: 'decision', label: 'Final Decision', desc: 'Combined risk score determines outcome' },
];

function Result({ result, onApply }) {
  if (!result) return (
    <section className="panel empty-state">
      <h2>No result yet</h2>
      <button className="primary-btn" onClick={onApply}>Create Application</button>
    </section>
  );

  const statusKey = (result.status || '').toLowerCase().replace(/\s+/g, '-');
  const approved  = result.status === 'Approved';
  const risky     = result.status === 'Risky';
  const manual    = result.status === 'Manual Review';
  const rejected  = result.status === 'Rejected';

  const toneClass = approved ? 'approved-bg' : risky || manual ? 'risky-bg' : 'rejected-bg';
  const toneCopy  = approved
    ? 'This profile clears the AI lending policy.'
    : manual
      ? 'Application requires manual underwriter review before a final decision.'
      : risky
        ? 'Profile is conditionally approvable but needs additional review.'
        : 'The current profile needs improvement before approval.';

  const uw         = result.underwriting || {};
  const ratios     = uw.financial_ratios || {};
  const triggered  = uw.triggered_rules || [];
  const recs       = uw.recommendations || [];
  const topFactors = result.top_factors || [];

  const scoreBreakdown = [
    { label: 'Business Rules',    value: uw.penalty_points   || 0 },
    { label: 'Financial Risk',    value: uw.financial_points  || 0 },
    { label: 'Consistency Flags', value: uw.consistency_points|| 0 },
    { label: 'Stability',         value: uw.stability_points  || 0 },
  ].filter(s => s.value > 0);

  const maxBreakdown = Math.max(...scoreBreakdown.map(s => s.value), 1);

  return (
    <section className="result-grid">

      {/* ── Decision Header ── */}
      <div className={`decision-panel ${toneClass}`}>
        {approved ? <CheckCircle2 size={44} /> : manual ? <ShieldAlert size={44} /> : risky ? <ShieldAlert size={44} /> : <XCircle size={44} />}
        <span>Loan Status</span>
        <h2>{result.status}</h2>
        <p>{toneCopy}</p>
        <div className="metric-grid decision-metrics">
          <Metric label="EMI"        value={currency(result.calculated_emi)} />
          <Metric label="Rate"       value={formatPercent(result.interest_rate)} />
          <Metric label="Approval"   value={formatPercent(result.approval_probability)} />
          <Metric label="Confidence" value={formatPercent(result.confidence_score)} />
        </div>
      </div>

      {/* ── Risk Meter + Confidence ── */}
      <div className="panel risk-card">
        <h3>Risk Score</h3>
        <RiskMeter score={result.risk_score} />
        <strong>{result.risk_category}</strong>
        <ConfidenceBar value={result.confidence_score} />
      </div>

      {/* ── Financial Health ── */}
      <div className="panel">
        <h3><Activity size={15} style={{display:'inline',marginRight:5}} />Financial Health</h3>
        {ratios.affordability_score !== undefined && (
          <div className="afford-score-badge">
            <span>Affordability Score</span>
            <strong className={ratios.affordability_score >= 70 ? 'green-text' : ratios.affordability_score >= 45 ? 'amber-text' : 'red-text'}>
              {ratios.affordability_score}/100
            </strong>
          </div>
        )}
        <div className="ratio-list">
          {ratios.debt_to_income    !== undefined && <RatioBar label="Debt-to-Income"     value={ratios.debt_to_income}    good={0.35} warn={0.50} />}
          {ratios.emi_ratio         !== undefined && <RatioBar label="EMI Ratio"          value={ratios.emi_ratio}         good={0.30} warn={0.40} />}
          {ratios.existing_loan_ratio !== undefined && <RatioBar label="Existing Loan Ratio" value={ratios.existing_loan_ratio} good={0.20} warn={0.35} />}
          {ratios.savings_ratio     !== undefined && <RatioBar label="Savings Coverage"   value={ratios.savings_ratio}     good={0.20} warn={0.10} format="decimal" />}
        </div>
        <div className="metric-grid compact" style={{marginTop:12}}>
          <Metric label="DTI"         value={formatPercent(result.metrics?.dti_ratio)} />
          <Metric label="EMI/Income"  value={formatPercent(result.metrics?.emi_to_income_ratio)} />
          <Metric label="Utilization" value={formatPercent(result.metrics?.credit_utilization)} />
          <Metric label="Stability"   value={formatPercent(result.metrics?.income_stability_factor)} />
        </div>
      </div>

      {/* ── Approval Breakdown ── */}
      {scoreBreakdown.length > 0 && (
        <div className="panel">
          <h3><BarChart3 size={15} style={{display:'inline',marginRight:5}} />Score Breakdown</h3>
          <p className="muted" style={{fontSize:'0.82rem',marginBottom:8}}>Lower penalty points = lower risk</p>
          {scoreBreakdown.map(s => (
            <div className="breakdown-row" key={s.label}>
              <span>{s.label}</span>
              <div className="breakdown-track">
                <div className="breakdown-fill" style={{ width: `${Math.round(s.value / maxBreakdown * 100)}%` }} />
              </div>
              <strong>{s.value}pts</strong>
            </div>
          ))}
          <div className="breakdown-total">Total Risk Score: <strong>{result.risk_score}/100</strong></div>
        </div>
      )}

      {/* ── Triggered Rules ── */}
      {triggered.length > 0 && (
        <div className="panel">
          <h3><Target size={15} style={{display:'inline',marginRight:5}} />Triggered Rules</h3>
          <div className="triggered-list">
            {triggered.map((t, i) => {
              const meta = SEVERITY_META[t.severity] || SEVERITY_META.warning;
              return (
                <div className={`triggered-item ${meta.cls}`} key={i}>
                  <div className="triggered-item-header">
                    <span className="triggered-badge">{meta.label}</span>
                  </div>
                  <p>{t.rule}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Explanation ── */}
      <div className="panel">
        <h3>Decision Explanation</h3>
        {result.warning_message && <div className="warning-banner">{result.warning_message}</div>}
        {uw.manual_review && <div className="review-banner">Manual review required before final approval.</div>}
        {(uw.positive_reasons?.length > 0) && (
          <div className="explain-section">
            <span className="explain-label positive"><ThumbsUp size={13} /> Positive Factors</span>
            <ul className="clean-list">
              {uw.positive_reasons.map(item => <li key={item}><CheckCircle2 size={15} /> {item}</li>)}
            </ul>
          </div>
        )}
        {(uw.risk_factors?.length > 0 || result.reasons?.length > 0) && (
          <div className="explain-section">
            <span className="explain-label negative"><AlertTriangle size={13} /> Risk Factors</span>
            <ul className="clean-list">
              {[...(uw.risk_factors || []), ...(result.reasons || [])].slice(0,5).map(item => <li key={item}><BarChart3 size={15} /> {item}</li>)}
            </ul>
          </div>
        )}
      </div>

      {/* ── Processing Timeline ── */}
      <div className="panel">
        <h3><Clock3 size={15} style={{display:'inline',marginRight:5}} />Processing Timeline</h3>
        <div className="timeline">
          {TIMELINE_STEPS.map((step, i) => (
            <div className="timeline-step" key={step.id}>
              <div className="timeline-dot">{i + 1}</div>
              <div className="timeline-content">
                <strong>{step.label}</strong>
                <span>{step.desc}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Top Factors ── */}
      {topFactors.length > 0 && (
        <div className="panel result-wide">
          <h3>Top Contributing Factors</h3>
          <div className="factor-grid">
            {topFactors.map((factor) => (
              <div className={`factor-card ${factor.direction}`} key={factor.feature}>
                <strong>{factor.title}</strong>
                <span>{factor.suggestion}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Recommendation Cards ── */}
      {recs.length > 0 && (
        <div className="panel result-wide">
          <h3><Sparkles size={15} style={{display:'inline',marginRight:5}} />Recommendations</h3>
          <div className="rec-grid">
            {recs.map((rec, i) => {
              const meta = IMPACT_META[rec.impact] || IMPACT_META.Low;
              const Icon = meta.icon;
              return (
                <div className={`rec-card ${meta.cls}`} key={i}>
                  <div className="rec-card-header">
                    <Icon size={18} />
                    <strong>{rec.title}</strong>
                    <span className="rec-impact-badge">{rec.impact} Impact</span>
                  </div>
                  <p>{rec.description}</p>
                </div>
              );
            })}
          </div>
          <button className="secondary-btn" style={{marginTop:16}} onClick={onApply}>Try another scenario</button>
        </div>
      )}

      {/* ── Suggestions fallback ── */}
      {recs.length === 0 && result.suggestions?.length > 0 && (
        <div className="panel">
          <h3>Suggestions</h3>
          <ul className="clean-list">{result.suggestions.map(item => <li key={item}><Sparkles size={16} /> {item}</li>)}</ul>
          <button className="secondary-btn" onClick={onApply}>Try another scenario</button>
        </div>
      )}

    </section>
  );
}

function AccessDenied({ user }) {
  return (
    <section className="panel access-denied">
      <span className="eyebrow"><ShieldCheck size={16} /> Role protected route</span>
      <h2>Access Denied – Unauthorized Role</h2>
      <p>{user.role === 'admin' ? 'Bank officers can only access the Admin Dashboard and profile area.' : 'Customers can only access the User Dashboard, loan workflow, chatbot, and profile area.'}</p>
    </section>
  );
}

function Profile({ user, onLogout }) {
  return (
    <section className="profile-grid">
      <div className="panel">
        <span className="eyebrow"><UserRound size={16} /> Profile</span>
        <h2>{user.name}</h2>
        <div className="profile-list">
          <div><span>Email</span><strong>{user.email}</strong></div>
          <div><span>Role</span><strong>{user.role === 'admin' ? 'Bank Officer' : 'Customer'}</strong></div>
        </div>
        <button className="secondary-btn" onClick={onLogout}><LogOut size={18} /> Logout</button>
      </div>
      <div className="panel">
        <h3>Access permissions</h3>
        <ul className="clean-list">
          {user.role === 'admin' ? (
            <>
              <li><ShieldCheck size={16} /> Monitor all loan applications.</li>
              <li><Table2 size={16} /> Review high-risk and suspicious entries.</li>
              <li><BarChart3 size={16} /> Analyze approval trends and rejection factors.</li>
            </>
          ) : (
            <>
              <li><PieChart size={16} /> Apply for AI loan decisions.</li>
              <li><Clock3 size={16} /> View previous applications and status history.</li>
              <li><Bot size={16} /> Ask the chatbot for rejection reasons and improvement tips.</li>
            </>
          )}
        </ul>
      </div>
    </section>
  );
}

function Chatbot() {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState([
    {
      from: 'bot',
      text: 'Hi, I am your live loan assistant. Ask me about loans, banking, EMI, DTI, credit score, interest rates, or your latest application.',
    },
  ]);
  const [loading, setLoading] = useState(false);

  async function send(quickMessage = '') {
    const outgoing = quickMessage || message;
    if (!outgoing.trim()) return;
    setMessages((items) => [...items, { from: 'user', text: outgoing }]);
    setMessage('');
    setLoading(true);
    try {
      const data = await api('/api/chat', { method: 'POST', body: JSON.stringify({ message: outgoing }) });
      setMessages((items) => [...items, { from: 'bot', text: data.reply || data.response }]);
    } catch (err) {
      setMessages((items) => [...items, { from: 'bot', text: err.message }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chatbot">
      {open && (
        <div className="chat-window">
          <div className="chat-head"><span><Bot size={18} /> Loan Assistant</span><button onClick={() => setOpen(false)}><X size={18} /></button></div>
          <div className="chat-body">
            <div className="quick-chat">
              {['Why rejected?', 'What is EMI?', 'How to improve eligibility?', 'Home loan vs personal loan'].map((item) => (
                <button key={item} onClick={() => send(item)}>{item}</button>
              ))}
            </div>
            {messages.map((item, index) => <div className={`bubble ${item.from}`} key={`${item.from}-${index}`}>{item.text}</div>)}
            {loading && <div className="bubble bot">Typing...</div>}
          </div>
          <div className="chat-input">
            <input value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && send()} placeholder="Ask about EMI, DTI, home loans, credit score..." />
            <button onClick={send}><ArrowRight size={18} /></button>
          </div>
        </div>
      )}
      <button className="chat-fab" onClick={() => setOpen((value) => !value)} aria-label="Open chat"><MessageCircle /></button>
    </div>
  );
}

function Admin() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api('/api/admin/stats').then(setStats).catch((err) => setError(err.message));
  }, []);

  if (error) return <section className="panel empty-state"><h2>{error}</h2><p>Login with the bank officer account: admin@loanai.com</p></section>;
  if (!stats) return <section className="panel empty-state"><span className="spinner" /></section>;

  const data = { labels: ['Approved', 'Risky', 'Rejected'], datasets: [{ data: [stats.approved, stats.risky, stats.rejected], backgroundColor: ['#16a34a', '#f59e0b', '#ef4444'], borderWidth: 0 }] };
  const incomeData = {
    labels: stats.income_groups.map((item) => item.group),
    datasets: [{ label: 'Rejected applications', data: stats.income_groups.map((item) => item.rejected), backgroundColor: '#ef4444', borderRadius: 8 }],
  };
  const factorData = {
    labels: stats.factor_impact.map((item) => item.factor),
    datasets: [{ label: 'Affected applications', data: stats.factor_impact.map((item) => item.count), backgroundColor: '#2563eb', borderRadius: 8 }],
  };

  return (
    <section className="dashboard">
      <div className="section-head"><div><span className="eyebrow"><ShieldCheck size={16} /> Admin console</span><h2>Portfolio overview</h2></div></div>
      <div className="stat-grid">
        <Stat icon={UserRound} label="Users" value={stats.total_users} />
        <Stat icon={CircleDollarSign} label="Applications" value={stats.total_applications} />
        <Stat icon={ShieldAlert} label="Risky" value={stats.risky} tone="amber" />
        <Stat icon={XCircle} label="Rejected" value={stats.rejected} tone="red" />
      </div>
      <div className="analytics-grid">
        <div className="panel"><h3>Approval vs rejection</h3><Doughnut data={data} options={{ cutout: '70%' }} /></div>
        <div className="panel"><h3>Rejected income groups</h3><Bar data={incomeData} options={{ responsive: true }} /></div>
        <div className="panel"><h3>Factor impact</h3><Bar data={factorData} options={{ responsive: true, indexAxis: 'y' }} /></div>
        <div className="panel"><h3>High-risk users list</h3><div className="table-list">{stats.high_risk.length === 0 && <p className="muted">No high-risk applications yet.</p>}{stats.high_risk.map((loan) => <LoanRow key={loan.id} loan={loan} />)}</div></div>
      </div>
      <div className="panel">
        <h3>All loan applications</h3>
        <div className="admin-table">
          <div className="admin-row header"><span>User ID</span><span>Email</span><span>Income</span><span>Loan</span><span>Result</span><span>Risk</span></div>
          {stats.applications.map((loan) => (
            <div className="admin-row" key={loan.id}>
              <span>#{loan.user_id}</span>
              <span>{loan.user_email}</span>
              <span>{currency(loan.income)}</span>
              <span>{currency(loan.loan_amount)}</span>
              <span className={`status ${loan.status.toLowerCase()}`}>{loan.status}</span>
              <span>{loan.risk_score}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="analytics-grid">
        <div className="panel">
          <h3>Suspicious entries</h3>
          <div className="table-list">
            {stats.high_risk.filter((loan) => loan.fraud_flags.length).length === 0 && <p className="muted">No fraud flags detected.</p>}
            {stats.high_risk.filter((loan) => loan.fraud_flags.length).map((loan) => (
              <div className="fraud-row" key={`fraud-${loan.id}`}>
                <strong>{loan.user_email}</strong>
                <span>{loan.fraud_flags.join(', ')}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <h3>Duplicate users</h3>
          <div className="table-list">
            {stats.duplicate_users.length === 0 && <p className="muted">No duplicate email accounts detected.</p>}
            {stats.duplicate_users.map((item) => <div className="fraud-row" key={item.email}><strong>{item.email}</strong><span>{item.count} accounts</span></div>)}
          </div>
        </div>
      </div>
    </section>
  );
}

function InsightMetricCard({ icon: Icon, label, value, tone }) {
  return (
    <article className={`stat-card ${tone || ''}`}>
      <Icon size={20} />
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function ModelInsights() {
  const [insights, setInsights] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api('/api/model-insights')
      .then(setInsights)
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return (
      <section className="panel empty-state">
        <h2>Model Performance &amp; Evaluation</h2>
        <p>{error}</p>
      </section>
    );
  }

  if (!insights) {
    return <section className="panel empty-state"><span className="spinner" /></section>;
  }

  const matrix = Array.isArray(insights.confusion_matrix) ? insights.confusion_matrix : [];
  const summaryCards = [
    [BarChart3, 'Accuracy', formatPercent((insights.accuracy || 0) * 100), 'green'],
    [ShieldCheck, 'F1 Score', formatPercent((insights.f1_score || 0) * 100), 'amber'],
    [TrendingUp, 'ROC AUC', formatPercent((insights.roc_auc || 0) * 100), ''],
    [PieChart, 'Precision', formatPercent((insights.precision || 0) * 100), ''],
    [CheckCircle2, 'Recall', formatPercent((insights.recall || 0) * 100), ''],
  ];

  return (
    <section className="dashboard">
      <div className="section-head">
        <div>
          <span className="eyebrow"><BarChart3 size={16} /> Admin insights</span>
          <h2>Model Performance &amp; Evaluation</h2>
        </div>
      </div>

      <div className="stat-grid">
        {summaryCards.map(([Icon, label, value, tone]) => (
          <InsightMetricCard key={label} icon={Icon} label={label} value={value} tone={tone} />
        ))}
      </div>

      <div className="analytics-grid">
        <div className="panel insights-panel">
          <h3>Confusion Matrix</h3>
          {insights.image_url ? (
            <img className="insights-image" src={resolveAssetUrl(insights.image_url)} alt="Confusion matrix heatmap" />
          ) : (
            <p className="muted">Confusion matrix image is not available yet.</p>
          )}
        </div>

        <div className="panel insights-panel">
          <h3>Confusion Matrix Values</h3>
          {matrix.length ? (
            <div className="matrix-grid">
              {matrix.flatMap((row, rowIndex) =>
                row.map((value, columnIndex) => (
                  <div className="matrix-cell" key={`${rowIndex}-${columnIndex}`}>
                    <span>{rowIndex === 0 ? 'Actual Rejected' : 'Actual Approved'}</span>
                    <strong>{value}</strong>
                    <small>{columnIndex === 0 ? 'Predicted Rejected' : 'Predicted Approved'}</small>
                  </div>
                ))
              )}
            </div>
          ) : (
            <p className="muted">Confusion matrix values are not available yet.</p>
          )}
        </div>
      </div>
    </section>
  );
}

createRoot(document.getElementById('root')).render(<App />);
