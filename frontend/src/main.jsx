import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ArrowRight,
  BadgeCheck,
  BarChart3,
  Bot,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Clock3,
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
  TrendingUp,
  UserPlus,
  UserRound,
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

function currency(value) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value || 0);
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(1)}%`;
}

function App() {
  const [user, setUser] = useState(null);
  const [view, setView] = useState('landing');
  const [authRole, setAuthRole] = useState('user');
  const [history, setHistory] = useState({ loans: [], stats: { total: 0, approved: 0, risky: 0, rejected: 0 } });
  const [latestResult, setLatestResult] = useState(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    api('/api/me')
      .then((data) => {
        if (data.user) {
          setUser(data.user);
          setView(data.user.role === 'admin' ? 'admin' : 'dashboard');
        }
      })
      .catch(() => {});
  }, []);

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
    setView('landing');
  }

  const navItems = user
    ? [
        ['dashboard', user.role === 'user' ? 'Dashboard' : null],
        ['apply', user.role === 'user' ? 'Apply' : null],
        ['profile', 'Profile'],
        ['admin', user.role === 'admin' ? 'Admin' : null],
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
        {view === 'dashboard' && user?.role === 'user' && <Dashboard user={user} history={history} onApply={() => setView('apply')} />}
        {view === 'apply' && user?.role === 'user' && <LoanForm onResult={(result) => { setLatestResult(result); refreshHistory(); setView('result'); }} />}
        {view === 'result' && user?.role === 'user' && <Result result={latestResult || history.loans[0]} onApply={() => setView('apply')} />}
        {view === 'profile' && user && <Profile user={user} onLogout={logout} />}
        {view === 'admin' && user?.role === 'admin' && <Admin />}
        {user && ((['dashboard', 'apply', 'result'].includes(view) && user.role !== 'user') || (view === 'admin' && user.role !== 'admin')) && <AccessDenied user={user} />}
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
        <h1>Smart AI Loan Approval System</h1>
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
  const doughnutData = useMemo(() => ({
    labels: ['Approved', 'Risky', 'Rejected'],
    datasets: [{ data: [history.stats.approved, history.stats.risky, history.stats.rejected], backgroundColor: ['#16a34a', '#f59e0b', '#ef4444'], borderWidth: 0 }],
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
      <div className="stat-grid">
        <Stat icon={CircleDollarSign} label="Applications" value={history.stats.total} />
        <Stat icon={CheckCircle2} label="Approved" value={history.stats.approved} tone="green" />
        <Stat icon={ShieldAlert} label="Risky" value={history.stats.risky} tone="amber" />
        <Stat icon={XCircle} label="Rejected" value={history.stats.rejected} tone="red" />
        <Stat icon={ShieldCheck} label="Avg Confidence" value={formatPercent(history.stats.avg_confidence)} />
      </div>
      <div className="analytics-grid">
        <div className="panel"><h3>Approval mix</h3><Doughnut data={doughnutData} options={{ cutout: '72%', plugins: { legend: { position: 'bottom' } } }} /></div>
        <div className="panel"><h3>Risk trend</h3><Bar data={barData} options={{ responsive: true, scales: { y: { min: 0, max: 100 } } }} /></div>
      </div>
      <div className="panel">
        <h3>Previous loan applications</h3>
        <HistoryTable loans={history.loans} />
      </div>
    </section>
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
      <div className="admin-row user-history header"><span>Date</span><span>Amount</span><span>Status</span><span>Risk score</span></div>
      {loans.map((loan) => (
        <div className="admin-row user-history" key={loan.id}>
          <span>{new Date(loan.created_at).toLocaleDateString()}</span>
          <span>{currency(loan.loan_amount)}</span>
          <span className={`status ${loan.status.toLowerCase()}`}>{loan.status}</span>
          <span>{loan.risk_score}/100</span>
        </div>
      ))}
    </div>
  );
}

function LoanForm({ onResult }) {
  const presetTenureYears = ['1', '2', '3', '5', '10'];
  const [form, setForm] = useState({
    income: '',
    credit_score: '',
    employment_status: 'salaried',
    loan_amount: '',
    existing_loans: '',
    loan_type: 'Personal Loan',
    previous_loan: 'No',
    previous_loan_amount: '',
    loan_tenure: '24',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [scenario, setScenario] = useState(null);
  const [scenarioError, setScenarioError] = useState('');
  const [simulating, setSimulating] = useState(false);
  const [tenureMode, setTenureMode] = useState('list');
  const [customTenureYears, setCustomTenureYears] = useState('');
  const [selectedTenureYears, setSelectedTenureYears] = useState('2');

  function update(key, value) {
    setForm((current) => {
      const newForm = { ...current, [key]: value };

      if (key === 'previous_loan' && value === 'No') {
        newForm.previous_loan_amount = '';
      }

      return newForm;
    });
  }

  function selectTenure(value) {
    if (value === 'other') {
      setTenureMode('custom');
      setError('');
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
    const required = ['income', 'credit_score', 'loan_amount', 'loan_type', 'employment_status', 'previous_loan'];
    if (required.some((field) => !String(form[field] ?? '').trim())) return null;

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
      onResult(data);
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
        <Field label="Monthly income (₹)" value={form.income} onChange={(value) => update('income', value)} placeholder="65000" />
        <Field label="Credit score" value={form.credit_score} onChange={(value) => update('credit_score', value)} placeholder="720" />
        <label>Employment status</label>
        <select value={form.employment_status} onChange={(event) => update('employment_status', event.target.value)}>
          <option value="salaried">Salaried</option>
          <option value="self-employed">Self-employed</option>
          <option value="business">Business</option>
          <option value="student">Student</option>
          <option value="unemployed">Unemployed</option>
        </select>
        <Field label="Loan amount (₹)" value={form.loan_amount} onChange={(value) => update('loan_amount', value)} placeholder="350000" />
        <Field label="Existing EMIs / loans outstanding (₹)" value={form.existing_loans} onChange={(value) => update('existing_loans', value)} placeholder="15000" />
        
        <label>Loan type</label>
        <select value={form.loan_type} onChange={(event) => update('loan_type', event.target.value)}>
          <option value="Personal Loan">Personal Loan</option>
          <option value="Home Loan">Home Loan</option>
          <option value="Vehicle Loan">Vehicle Loan</option>
          <option value="Education Loan">Education Loan</option>
        </select>
        
        <label>Do you have any previous loan?</label>
        <select value={form.previous_loan} onChange={(event) => update('previous_loan', event.target.value)}>
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
              >
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
        <button className="primary-btn full" disabled={loading}>{loading ? <span className="spinner" /> : 'Get AI Decision'}</button>
      </form>
    </section>
  );
}

function Field({ label, value, onChange, placeholder }) {
  return (
    <>
      <label>{label}</label>
      <input type="number" min="0" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} required />
    </>
  );
}

function Metric({ label, value }) {
  return <div className="metric-card"><span>{label}</span><strong>{value}</strong></div>;
}

function RiskMeter({ score }) {
  const degrees = Math.max(18, Math.min(342, Number(score || 0) * 3.2));
  return <div className="score-orb dynamic" style={{ background: `conic-gradient(#2563eb 0 ${degrees}deg, #dbeafe ${degrees}deg 360deg)` }}>{Math.round(score || 0)}</div>;
}

function Result({ result, onApply }) {
  if (!result) return <section className="panel empty-state"><h2>No result yet</h2><button className="primary-btn" onClick={onApply}>Create Application</button></section>;
  const approved = result.status === 'Approved';
  const risky = result.status === 'Risky';
  const toneClass = approved ? 'approved-bg' : risky ? 'risky-bg' : 'rejected-bg';
  const toneCopy = approved
    ? 'This profile clears the AI lending policy.'
    : risky
      ? 'This profile is conditionally approvable but needs additional affordability review.'
      : 'The current profile needs improvement before approval.';
  return (
    <section className="result-grid">
      <div className={`decision-panel ${toneClass}`}>
        {approved ? <CheckCircle2 size={44} /> : risky ? <ShieldAlert size={44} /> : <XCircle size={44} />}
        <span>Loan Status</span>
        <h2>{result.status}</h2>
        <p>{toneCopy}</p>
        <div className="metric-grid decision-metrics">
          <Metric label="EMI" value={currency(result.calculated_emi)} />
          <Metric label="Rate" value={formatPercent(result.interest_rate)} />
          <Metric label="Approval" value={formatPercent(result.approval_probability)} />
          <Metric label="Confidence" value={formatPercent(result.confidence_score)} />
        </div>
      </div>
      <div className="panel risk-card">
        <h3>Risk Score</h3>
        <RiskMeter score={result.risk_score} />
        <strong>{result.risk_category} risk</strong>
        <div className="metric-grid compact">
          <Metric label="DTI" value={formatPercent(result.metrics.dti_ratio)} />
          <Metric label="EMI / Income" value={formatPercent(result.metrics.emi_to_income_ratio)} />
          <Metric label="Utilization" value={formatPercent(result.metrics.credit_utilization)} />
          <Metric label="Stability" value={formatPercent(result.metrics.income_stability_factor)} />
        </div>
      </div>
      <div className="panel">
        <h3>Decision explanation</h3>
        <ul className="clean-list">{result.reasons.map((item) => <li key={item}><BarChart3 size={16} /> {item}</li>)}</ul>
      </div>
      <div className="panel">
        <h3>Suggestions</h3>
        <ul className="clean-list">{result.suggestions.map((item) => <li key={item}><Sparkles size={16} /> {item}</li>)}</ul>
        <button className="secondary-btn" onClick={onApply}>Try another scenario</button>
      </div>
      <div className="panel result-wide">
        <h3>Top contributing factors</h3>
        <div className="factor-grid">
          {result.top_factors.map((factor) => (
            <div className={`factor-card ${factor.direction}`} key={factor.feature}>
              <strong>{factor.title}</strong>
              <span>{factor.suggestion}</span>
            </div>
          ))}
        </div>
      </div>
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
  const [messages, setMessages] = useState([{ from: 'bot', text: 'Hi, I can explain your latest loan decision.' }]);
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
              {['Why rejected?', 'Improve score', 'What is risk score?'].map((item) => (
                <button key={item} onClick={() => send(item)}>{item}</button>
              ))}
            </div>
            {messages.map((item, index) => <div className={`bubble ${item.from}`} key={`${item.from}-${index}`}>{item.text}</div>)}
            {loading && <div className="bubble bot">Typing...</div>}
          </div>
          <div className="chat-input">
            <input value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && send()} placeholder="Why was my loan rejected?" />
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

createRoot(document.getElementById('root')).render(<App />);
