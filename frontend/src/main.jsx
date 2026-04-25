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
  KeyRound,
  Landmark,
  LockKeyhole,
  LogOut,
  Mail,
  Menu,
  MessageCircle,
  PieChart,
  Send,
  ShieldCheck,
  Smartphone,
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

function App() {
  const [user, setUser] = useState(null);
  const [view, setView] = useState('landing');
  const [authRole, setAuthRole] = useState('user');
  const [history, setHistory] = useState({ loans: [], stats: { total: 0, approved: 0, rejected: 0 } });
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
    setHistory({ loans: [], stats: { total: 0, approved: 0, rejected: 0 } });
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
  const [authMethod, setAuthMethod] = useState(initialRole === 'admin' ? 'email' : 'otp');
  const [otpSent, setOtpSent] = useState(false);
  const [devOtp, setDevOtp] = useState('');
  const [form, setForm] = useState({
    name: '',
    email: initialRole === 'admin' ? 'admin@smartloan.ai' : 'customer@gmail.com',
    password: initialRole === 'admin' ? 'Admin@123' : 'Customer@123',
    phone: '9876543210',
    otp: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function switchRole(nextRole) {
    setRole(nextRole);
    setError('');
    if (nextRole === 'admin') {
      setMode('login');
      setAuthMethod('email');
      setOtpSent(false);
      setForm({ name: '', email: 'admin@smartloan.ai', password: 'Admin@123', phone: '', otp: '' });
    } else {
      setAuthMethod('otp');
      setForm({ name: '', email: 'customer@gmail.com', password: 'Customer@123', phone: '9876543210', otp: '' });
    }
  }

  async function sendOtp() {
    setError('');
    setLoading(true);
    try {
      const data = await api('/api/send_otp', { method: 'POST', body: JSON.stringify({ phone: form.phone }) });
      setOtpSent(true);
      setDevOtp(data.dev_otp || '');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function submit(event) {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (role === 'user' && authMethod === 'otp') {
        const data = await api('/api/verify_otp', { method: 'POST', body: JSON.stringify({ phone: form.phone, otp: form.otp }) });
        onAuthed(data.user);
        return;
      }
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

  return (
    <section className="auth-wrap">
      <div className="auth-card">
        <span className="eyebrow"><LockKeyhole size={16} /> Role-based secure login</span>
        <h2>{role === 'admin' ? 'Bank officer access' : 'Customer access'}</h2>
        <p>{role === 'admin' ? 'Admin users can monitor applications, risk, fraud flags, and portfolio insights.' : 'Customers can register, apply for loans, view history, and chat with the AI assistant.'}</p>

        <div className="segmented">
          <button className={role === 'user' ? 'selected' : ''} onClick={() => switchRole('user')} type="button"><UserRound size={16} /> User Login</button>
          <button className={role === 'admin' ? 'selected' : ''} onClick={() => switchRole('admin')} type="button"><ShieldCheck size={16} /> Admin Login</button>
        </div>

        {role === 'user' && (
          <div className="mode-switch">
            <button className={authMethod === 'otp' ? 'active' : ''} onClick={() => { setAuthMethod('otp'); setMode('login'); setError(''); }} type="button"><Smartphone size={16} /> OTP</button>
            <button className={authMethod === 'email' ? 'active' : ''} onClick={() => { setAuthMethod('email'); setError(''); }} type="button"><Mail size={16} /> Email</button>
          </div>
        )}

        <form onSubmit={submit}>
          {role === 'user' && authMethod === 'otp' ? (
            <>
              <label>Phone number</label>
              <div className="otp-row">
                <div className="input-icon"><Smartphone size={18} /><input value={form.phone} onChange={(event) => update('phone', event.target.value)} placeholder="9876543210" /></div>
                <button className="secondary-btn" type="button" onClick={sendOtp} disabled={loading}>{loading ? <span className="spinner dark" /> : <><Send size={16} /> Send OTP</>}</button>
              </div>
              <label>Verification code</label>
              <div className="input-icon"><KeyRound size={18} /><input value={form.otp} onChange={(event) => update('otp', event.target.value)} placeholder="6-digit OTP" inputMode="numeric" /></div>
              {otpSent && <span className="demo-code">Demo OTP sent. Local code: {devOtp}</span>}
            </>
          ) : (
            <>
              {role === 'user' && (
                <div className="mode-switch compact-switch">
                  <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')} type="button">Login</button>
                  <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')} type="button">Register</button>
                </div>
              )}
              {mode === 'register' && role === 'user' && (
                <>
                  <label>Full name</label>
                  <div className="input-icon"><UserPlus size={18} /><input value={form.name} onChange={(event) => update('name', event.target.value)} placeholder="Aarav Sharma" /></div>
                </>
              )}
              <label>Email address</label>
              <div className="input-icon"><Mail size={18} /><input type="email" value={form.email} onChange={(event) => update('email', event.target.value)} placeholder="name@gmail.com" /></div>
              <label>Password</label>
              <div className="input-icon"><LockKeyhole size={18} /><input type="password" value={form.password} onChange={(event) => update('password', event.target.value)} placeholder="Enter password" /></div>
            </>
          )}
          {role === 'admin' && <span className="demo-code">Demo admin: admin@smartloan.ai / Admin@123</span>}
          {role === 'user' && authMethod === 'email' && mode === 'login' && <span className="demo-code">Demo user: customer@gmail.com / Customer@123</span>}
          {error && <div className="error"><XCircle size={16} /> {error}</div>}
          <button className="primary-btn full" disabled={loading}>
            {loading ? <span className="spinner" /> : role === 'user' && authMethod === 'otp' ? 'Verify OTP & Login' : mode === 'register' ? 'Create User Account' : `Login as ${role === 'admin' ? 'Admin' : 'User'}`}
          </button>
        </form>
      </div>
    </section>
  );
}

function Dashboard({ user, history, onApply }) {
  const doughnutData = useMemo(() => ({
    labels: ['Approved', 'Rejected'],
    datasets: [{ data: [history.stats.approved, history.stats.rejected], backgroundColor: ['#16a34a', '#ef4444'], borderWidth: 0 }],
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
        <Stat icon={XCircle} label="Rejected" value={history.stats.rejected} tone="red" />
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
  const [form, setForm] = useState({
    income: '',
    credit_score: '',
    employment_status: 'salaried',
    loan_amount: '',
    existing_loans: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await api('/api/predict', { method: 'POST', body: JSON.stringify(form) });
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
        <p>Enter the core lending signals and get an instant decision with explainable reasoning.</p>
      </div>
      <form className="loan-form" onSubmit={submit}>
        <Field label="Monthly income" value={form.income} onChange={(value) => update('income', value)} placeholder="65000" />
        <Field label="Credit score" value={form.credit_score} onChange={(value) => update('credit_score', value)} placeholder="720" />
        <label>Employment status</label>
        <select value={form.employment_status} onChange={(event) => update('employment_status', event.target.value)}>
          <option value="salaried">Salaried</option>
          <option value="self-employed">Self-employed</option>
          <option value="business">Business</option>
          <option value="student">Student</option>
          <option value="unemployed">Unemployed</option>
        </select>
        <Field label="Loan amount" value={form.loan_amount} onChange={(value) => update('loan_amount', value)} placeholder="350000" />
        <Field label="Existing loans" value={form.existing_loans} onChange={(value) => update('existing_loans', value)} placeholder="80000" />
        {error && <div className="error"><XCircle size={16} /> {error}</div>}
        <button className="primary-btn full" disabled={loading}>{loading ? <span className="spinner" /> : 'Run AI Decision'}</button>
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

function Result({ result, onApply }) {
  if (!result) return <section className="panel empty-state"><h2>No result yet</h2><button className="primary-btn" onClick={onApply}>Create Application</button></section>;
  const approved = result.status === 'Approved';
  return (
    <section className="result-grid">
      <div className={`decision-panel ${approved ? 'approved-bg' : 'rejected-bg'}`}>
        {approved ? <CheckCircle2 size={44} /> : <XCircle size={44} />}
        <span>Loan Status</span>
        <h2>{result.status}</h2>
        <p>{approved ? 'This profile clears the AI lending policy.' : 'The current profile needs improvement before approval.'}</p>
      </div>
      <div className="panel risk-card">
        <h3>Risk Score</h3>
        <div className="score-orb">{result.risk_score}</div>
        <strong>{result.risk_category} risk</strong>
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

  if (error) return <section className="panel empty-state"><h2>{error}</h2><p>Login with the seeded bank officer account: admin@smartloan.ai.</p></section>;
  if (!stats) return <section className="panel empty-state"><span className="spinner" /></section>;

  const data = { labels: ['Approved', 'Rejected'], datasets: [{ data: [stats.approved, stats.rejected], backgroundColor: ['#16a34a', '#ef4444'], borderWidth: 0 }] };
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
