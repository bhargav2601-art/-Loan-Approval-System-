import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Bot,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  Gauge,
  Lightbulb,
  MessageCircle,
  PieChart,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { Line, Bar } from 'react-chartjs-2';

const API_BASE = import.meta.env.VITE_API_BASE || '';

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok && response.status !== 409) throw new Error(`API error: ${response.statusText}`);
  return response.json();
}

const LoanDashboard = ({ result, originalData }) => {
  const [suggestions, setSuggestions] = useState([]);
  const [trendData, setTrendData] = useState([]);
  const [chatMessage, setChatMessage] = useState('');
  const [chatResponse, setChatResponse] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (result) {
      loadSuggestions();
      loadTrendData();
    }
  }, [result]);

  const loadSuggestions = async () => {
    try {
      setLoading(true);
      const data = await api('/api/suggestions', {
        method: 'POST',
        body: JSON.stringify(originalData),
      });
      setSuggestions(data.suggestions || []);
    } catch (err) {
      console.error('Failed to load suggestions:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadTrendData = async () => {
    try {
      const tenures = [12, 24, 36, 60, 84, 120, 180, 240, 300, 360];
      const trends = [];
      for (const tenure of tenures) {
        try {
          const testData = { ...originalData, loan_tenure: tenure };
          const res = await api('/api/simulate', {
            method: 'POST',
            body: JSON.stringify(testData),
          });
          trends.push({
            tenure: tenure / 12,
            approval: res.approval_probability,
          });
        } catch (e) {
          console.warn(`Failed to load trend for tenure ${tenure}`, e);
        }
      }
      setTrendData(trends);
    } catch (err) {
      console.error('Failed to load trend data:', err);
    }
  };

  const sendChatMessage = async (question) => {
    if (!question.trim()) return;
    try {
      const res = await api('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ message: question }),
      });
      setChatResponse(res.reply || res.response);
      setChatMessage('');
    } catch (err) {
      setChatResponse('Sorry, I encountered an error. Please try again.');
    }
  };

  // Calculate metrics
  const approval = result?.approval_probability || 0;
  const riskScore = result?.risk_score || 0;
  const confidence = result?.confidence_score || 0;
  const status = result?.status || 'Pending';
  const metrics = result?.metrics || {};
  const emi = result?.calculated_emi || 0;
  const income = originalData?.income || 0;
  const loanAmount = originalData?.loan_amount || 0;
  const existingLoans = originalData?.existing_loans || 0;
  const interestRate = result?.interest_rate || 0;

  // Determine colors
  const statusColor =
    status === 'Approved'
      ? 'from-green-500 to-emerald-600'
      : status === 'Risky'
        ? 'from-yellow-500 to-orange-600'
        : 'from-red-500 to-rose-600';

  const getHealthScore = () => {
    let score = 100;
    if (metrics.dti_ratio > 50) score -= 20;
    else if (metrics.dti_ratio > 40) score -= 10;
    if (metrics.emi_to_income_ratio > 40) score -= 20;
    else if (metrics.emi_to_income_ratio > 30) score -= 10;
    if ((result?.inputs?.credit_score || 0) < 650) score -= 15;
    else if ((result?.inputs?.credit_score || 0) < 700) score -= 5;
    return Math.max(0, Math.min(100, score));
  };

  const healthScore = getHealthScore();

  const trendChartData = useMemo(() => {
    if (!trendData.length)
      return {
        labels: [],
        datasets: [],
      };
    return {
      labels: trendData.map(d => `${d.tenure}yr`),
      datasets: [
        {
          label: 'Approval Probability (%)',
          data: trendData.map(d => d.approval),
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
        },
      ],
    };
  }, [trendData]);

  const bestSuggestion = suggestions[0];

  return (
    <div className='min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6'>
      <div className='max-w-7xl mx-auto space-y-8'>
        {/* Header */}
        <div className='text-center'>
          <h1 className='text-4xl font-bold text-slate-900 mb-2'>Smart Loan Decision Dashboard</h1>
          <p className='text-lg text-slate-600'>Intelligent insights powered by AI</p>
        </div>

        {/* 1. AI DECISION SECTION */}
        <div className={`bg-gradient-to-br ${statusColor} rounded-2xl shadow-2xl p-8 text-white`}>
          <div className='grid grid-cols-1 md:grid-cols-2 gap-8'>
            <div>
              <p className='text-sm font-semibold uppercase tracking-wide opacity-90 mb-2'>Application Status</p>
              <h2 className='text-4xl font-bold mb-4'>{status}</h2>
              <p className='text-lg opacity-90 mb-6'>
                {status === 'Approved'
                  ? 'Eligible for loan with favorable terms'
                  : status === 'Risky'
                    ? 'Conditional Approval - Additional review needed'
                    : 'High Risk Application - Does not meet current criteria'}
              </p>
              <div className='flex items-center gap-2'>
                {status === 'Approved' ? (
                  <CheckCircle2 className='w-6 h-6' />
                ) : status === 'Risky' ? (
                  <AlertTriangle className='w-6 h-6' />
                ) : (
                  <ShieldAlert className='w-6 h-6' />
                )}
                <span className='font-semibold'>Review details below for next steps</span>
              </div>
            </div>

            {/* Circular Gauge */}
            <div className='flex flex-col items-center justify-center'>
              <div className='relative w-48 h-48'>
                {/* Gauge background */}
                <svg className='w-full h-full -rotate-90' viewBox='0 0 120 120'>
                  <circle cx='60' cy='60' r='50' fill='none' stroke='rgba(255,255,255,0.2)' strokeWidth='8' />
                  <circle
                    cx='60'
                    cy='60'
                    r='50'
                    fill='none'
                    stroke='currentColor'
                    strokeWidth='8'
                    strokeDasharray={`${(approval / 100) * 314} 314`}
                    className='text-white transition-all duration-500'
                  />
                </svg>
                <div className='absolute inset-0 flex flex-col items-center justify-center'>
                  <span className='text-4xl font-bold'>{approval.toFixed(1)}%</span>
                  <span className='text-sm opacity-90'>Approval Probability</span>
                </div>
              </div>
              <div className='mt-4 text-center'>
                <p className='text-white opacity-75 text-sm'>Model Confidence</p>
                <p className='text-2xl font-bold'>{confidence.toFixed(1)}%</p>
              </div>
            </div>
          </div>

          {/* Risk Score Below */}
          <div className='mt-8 pt-8 border-t border-white border-opacity-20'>
            <div className='grid grid-cols-3 gap-4'>
              <div className='text-center'>
                <p className='text-xs font-semibold uppercase opacity-75 mb-1'>Risk Score</p>
                <p className='text-3xl font-bold'>{riskScore.toFixed(1)}/100</p>
              </div>
              <div className='text-center'>
                <p className='text-xs font-semibold uppercase opacity-75 mb-1'>Risk Level</p>
                <p className='text-2xl font-bold'>{result?.risk_category || 'N/A'}</p>
              </div>
              <div className='text-center'>
                <p className='text-xs font-semibold uppercase opacity-75 mb-1'>Interest Rate</p>
                <p className='text-2xl font-bold'>{interestRate.toFixed(2)}%</p>
              </div>
            </div>
          </div>
        </div>

        {/* 2. FINANCIAL SUMMARY CARDS */}
        <div className='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6'>
          {/* EMI Card */}
          <div className='bg-white rounded-xl shadow-md p-6 border-l-4 border-blue-500'>
            <div className='flex items-center justify-between mb-4'>
              <p className='text-sm text-slate-600 font-semibold'>Monthly EMI</p>
              <CircleDollarSign className='w-5 h-5 text-blue-500' />
            </div>
            <p className='text-3xl font-bold text-slate-900'>₹{emi.toLocaleString('en-IN')}</p>
            <div className='mt-3 pt-3 border-t border-slate-200'>
              <p className='text-xs text-slate-500'>
                {((emi / income) * 100).toFixed(1)}% of monthly income
              </p>
              {(emi / income) * 100 < 30 ? (
                <span className='inline-block mt-2 px-2 py-1 bg-green-100 text-green-700 text-xs font-semibold rounded'>
                  ✓ Safe
                </span>
              ) : (emi / income) * 100 < 40 ? (
                <span className='inline-block mt-2 px-2 py-1 bg-yellow-100 text-yellow-700 text-xs font-semibold rounded'>
                  ⚠ Moderate
                </span>
              ) : (
                <span className='inline-block mt-2 px-2 py-1 bg-red-100 text-red-700 text-xs font-semibold rounded'>
                  ✕ High Risk
                </span>
              )}
            </div>
          </div>

          {/* DTI Ratio Card */}
          <div className='bg-white rounded-xl shadow-md p-6 border-l-4 border-purple-500'>
            <div className='flex items-center justify-between mb-4'>
              <p className='text-sm text-slate-600 font-semibold'>Debt-to-Income</p>
              <PieChart className='w-5 h-5 text-purple-500' />
            </div>
            <p className='text-3xl font-bold text-slate-900'>{(metrics.dti_ratio || 0).toFixed(1)}%</p>
            <div className='mt-3 pt-3 border-t border-slate-200'>
              <p className='text-xs text-slate-500'>Total debt obligations</p>
              {(metrics.dti_ratio || 0) < 36 ? (
                <span className='inline-block mt-2 px-2 py-1 bg-green-100 text-green-700 text-xs font-semibold rounded'>
                  ✓ Healthy
                </span>
              ) : (metrics.dti_ratio || 0) < 50 ? (
                <span className='inline-block mt-2 px-2 py-1 bg-yellow-100 text-yellow-700 text-xs font-semibold rounded'>
                  ⚠ Caution
                </span>
              ) : (
                <span className='inline-block mt-2 px-2 py-1 bg-red-100 text-red-700 text-xs font-semibold rounded'>
                  ✕ High Risk
                </span>
              )}
            </div>
          </div>

          {/* EMI to Income Ratio */}
          <div className='bg-white rounded-xl shadow-md p-6 border-l-4 border-orange-500'>
            <div className='flex items-center justify-between mb-4'>
              <p className='text-sm text-slate-600 font-semibold'>EMI Ratio</p>
              <TrendingUp className='w-5 h-5 text-orange-500' />
            </div>
            <p className='text-3xl font-bold text-slate-900'>{(metrics.emi_to_income_ratio || 0).toFixed(1)}%</p>
            <div className='mt-3 pt-3 border-t border-slate-200'>
              <p className='text-xs text-slate-500'>EMI as % of income</p>
              {(metrics.emi_to_income_ratio || 0) < 30 ? (
                <span className='inline-block mt-2 px-2 py-1 bg-green-100 text-green-700 text-xs font-semibold rounded'>
                  ✓ Safe
                </span>
              ) : (metrics.emi_to_income_ratio || 0) < 40 ? (
                <span className='inline-block mt-2 px-2 py-1 bg-yellow-100 text-yellow-700 text-xs font-semibold rounded'>
                  ⚠ Moderate
                </span>
              ) : (
                <span className='inline-block mt-2 px-2 py-1 bg-red-100 text-red-700 text-xs font-semibold rounded'>
                  ✕ High Risk
                </span>
              )}
            </div>
          </div>

          {/* Total Obligation */}
          <div className='bg-white rounded-xl shadow-md p-6 border-l-4 border-indigo-500'>
            <div className='flex items-center justify-between mb-4'>
              <p className='text-sm text-slate-600 font-semibold'>Total Obligation</p>
              <Shield className='w-5 h-5 text-indigo-500' />
            </div>
            <p className='text-3xl font-bold text-slate-900'>₹{(emi + existingLoans).toLocaleString('en-IN')}</p>
            <div className='mt-3 pt-3 border-t border-slate-200'>
              <p className='text-xs text-slate-500'>EMI + Existing EMI</p>
              <div className='mt-2 text-xs text-slate-600'>
                <p>New EMI: ₹{emi.toLocaleString('en-IN')}</p>
                <p>Existing: ₹{existingLoans.toLocaleString('en-IN')}</p>
              </div>
            </div>
          </div>
        </div>

        {/* 3. KEY RISK FACTORS */}
        <div>
          <h3 className='text-2xl font-bold text-slate-900 mb-6 flex items-center gap-2'>
            <ShieldAlert className='w-6 h-6 text-red-500' />
            Key Risk Factors
          </h3>
          <div className='grid grid-cols-1 md:grid-cols-2 gap-6'>
            {(result?.top_factors || []).slice(0, 4).map((factor, idx) => (
              <div key={idx} className='bg-white rounded-xl shadow-md p-6 border-l-4 border-slate-300'>
                <div className='flex items-start justify-between mb-3'>
                  <h4 className='font-semibold text-slate-900 capitalize'>
                    {factor.feature.replace(/_/g, ' ')}
                  </h4>
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-bold ${
                      factor.direction === 'negative'
                        ? 'bg-red-100 text-red-700'
                        : 'bg-green-100 text-green-700'
                    }`}
                  >
                    {factor.direction === 'negative' ? 'Issue' : 'Strong'}
                  </span>
                </div>
                <p className='text-sm text-slate-700 mb-3'>{factor.title}</p>
                <div className='bg-slate-100 rounded p-3'>
                  <p className='text-xs text-slate-600'>
                    <strong>Suggestion:</strong> {factor.suggestion}
                  </p>
                </div>
                <div className='mt-3 pt-3 border-t border-slate-200 text-xs text-slate-500'>
                  Signal: {(factor.signal * 100).toFixed(1)}% | Weight: {(factor.weight * 100).toFixed(1)}%
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 4. LOAN HEALTH SCORE */}
        <div className='bg-white rounded-xl shadow-md p-8'>
          <h3 className='text-2xl font-bold text-slate-900 mb-6 flex items-center gap-2'>
            <Gauge className='w-6 h-6 text-blue-500' />
            Loan Health Score
          </h3>
          <div className='flex items-center gap-8'>
            <div className='relative w-40 h-40'>
              <svg className='w-full h-full -rotate-90' viewBox='0 0 120 120'>
                <circle cx='60' cy='60' r='50' fill='none' stroke='#e2e8f0' strokeWidth='10' />
                <circle
                  cx='60'
                  cy='60'
                  r='50'
                  fill='none'
                  stroke={healthScore > 70 ? '#10b981' : healthScore > 50 ? '#f59e0b' : '#ef4444'}
                  strokeWidth='10'
                  strokeDasharray={`${(healthScore / 100) * 314} 314`}
                  className='transition-all duration-500'
                />
              </svg>
              <div className='absolute inset-0 flex flex-col items-center justify-center'>
                <span className='text-4xl font-bold text-slate-900'>{healthScore}</span>
                <span className='text-xs text-slate-500'>/ 100</span>
              </div>
            </div>
            <div className='flex-1'>
              <div className='space-y-4'>
                <div>
                  <div className='flex justify-between mb-2'>
                    <span className='text-sm font-semibold text-slate-700'>Credit Profile</span>
                    <span className='text-sm font-bold text-slate-900'>
                      {result?.inputs?.credit_score || 0}
                    </span>
                  </div>
                  <div className='w-full bg-slate-200 rounded-full h-2'>
                    <div
                      className='bg-blue-500 h-2 rounded-full transition-all'
                      style={{
                        width: `${Math.min(100, ((result?.inputs?.credit_score || 0) / 900) * 100)}%`,
                      }}
                    ></div>
                  </div>
                </div>
                <div>
                  <div className='flex justify-between mb-2'>
                    <span className='text-sm font-semibold text-slate-700'>Debt Management</span>
                    <span className='text-sm font-bold text-slate-900'>
                      {(metrics.dti_ratio || 0).toFixed(1)}%
                    </span>
                  </div>
                  <div className='w-full bg-slate-200 rounded-full h-2'>
                    <div
                      className='bg-green-500 h-2 rounded-full transition-all'
                      style={{
                        width: `${Math.max(0, 100 - (metrics.dti_ratio || 0))}%`,
                      }}
                    ></div>
                  </div>
                </div>
                <div>
                  <div className='flex justify-between mb-2'>
                    <span className='text-sm font-semibold text-slate-700'>Income Stability</span>
                    <span className='text-sm font-bold text-slate-900'>
                      {((result?.inputs?.income_stability_factor || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className='w-full bg-slate-200 rounded-full h-2'>
                    <div
                      className='bg-purple-500 h-2 rounded-full transition-all'
                      style={{
                        width: `${(result?.inputs?.income_stability_factor || 0) * 100}%`,
                      }}
                    ></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 5. APPROVAL TREND GRAPH */}
        <div className='bg-white rounded-xl shadow-md p-8'>
          <h3 className='text-2xl font-bold text-slate-900 mb-6 flex items-center gap-2'>
            <TrendingUp className='w-6 h-6 text-blue-500' />
            Approval Probability by Loan Tenure
          </h3>
          {trendData.length > 0 ? (
            <div style={{ height: '300px' }}>
              <Line
                data={trendChartData}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: { display: true },
                  },
                  scales: {
                    y: {
                      beginAtZero: true,
                      max: 100,
                      ticks: { callback: value => `${value}%` },
                    },
                  },
                }}
              />
            </div>
          ) : (
            <div className='h-64 flex items-center justify-center text-slate-400'>
              <p>Loading trend analysis...</p>
            </div>
          )}
        </div>

        {/* 6. SMART SUGGESTIONS ENGINE */}
        <div>
          <h3 className='text-2xl font-bold text-slate-900 mb-6 flex items-center gap-2'>
            <Lightbulb className='w-6 h-6 text-yellow-500' />
            Smart Suggestions
          </h3>

          {/* Best Suggestion Highlight */}
          {bestSuggestion && (
            <div className='mb-6 bg-gradient-to-r from-yellow-50 to-orange-50 rounded-xl shadow-md p-8 border-2 border-yellow-200'>
              <div className='flex items-start justify-between mb-4'>
                <div>
                  <div className='flex items-center gap-2 mb-2'>
                    <Sparkles className='w-6 h-6 text-yellow-500' />
                    <h4 className='text-xl font-bold text-slate-900'>Best Option</h4>
                  </div>
                  <p className='text-lg font-semibold text-slate-700'>{bestSuggestion.title}</p>
                  <p className='text-slate-600 mt-1'>{bestSuggestion.description}</p>
                </div>
                <div className='text-right'>
                  <p className='text-sm text-slate-600 mb-1'>Improvement</p>
                  <p className='text-3xl font-bold text-yellow-600'>
                    +{bestSuggestion.improvement_percent?.toFixed(1)}%
                  </p>
                </div>
              </div>

              <div className='grid grid-cols-3 gap-4 mt-6'>
                <div className='bg-white rounded-lg p-4'>
                  <p className='text-xs text-slate-600 mb-1'>Current Approval</p>
                  <p className='text-2xl font-bold text-slate-900'>
                    {bestSuggestion.current_approval_prob?.toFixed(1)}%
                  </p>
                </div>
                <div className='flex items-center justify-center'>
                  <ArrowRight className='w-6 h-6 text-yellow-500' />
                </div>
                <div className='bg-white rounded-lg p-4'>
                  <p className='text-xs text-slate-600 mb-1'>New Approval</p>
                  <p className='text-2xl font-bold text-green-600'>
                    {bestSuggestion.new_approval_prob?.toFixed(1)}%
                  </p>
                </div>
              </div>

              {bestSuggestion.emi_reduction > 0 && (
                <div className='mt-4 bg-green-100 rounded-lg p-3'>
                  <p className='text-sm text-green-800'>
                    💰 <strong>EMI Reduction:</strong> ₹{bestSuggestion.emi_reduction?.toLocaleString('en-IN')}
                    /month
                  </p>
                </div>
              )}
            </div>
          )}

          {/* All Suggestions */}
          <div className='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6'>
            {suggestions.map((suggestion, idx) => (
              <div key={idx} className='bg-white rounded-xl shadow-md p-6 border-t-4 border-blue-500'>
                <h4 className='text-lg font-bold text-slate-900 mb-2'>{suggestion.title}</h4>
                <p className='text-sm text-slate-600 mb-4'>{suggestion.description}</p>

                <div className='bg-slate-50 rounded-lg p-4 mb-4'>
                  <p className='text-xs text-slate-600 mb-1'>Suggested Value</p>
                  <p className='text-2xl font-bold text-slate-900'>
                    {suggestion.unit === 'months'
                      ? `${(suggestion.suggested_value / 12).toFixed(1)} years`
                      : `${suggestion.unit}${
                          typeof suggestion.suggested_value === 'number'
                            ? suggestion.suggested_value.toLocaleString('en-IN', {
                                maximumFractionDigits: 0,
                              })
                            : suggestion.suggested_value
                        }`}
                  </p>
                  <p className='text-xs text-slate-500 mt-1'>
                    Current: {suggestion.unit === 'months'
                      ? `${(suggestion.current_value / 12).toFixed(1)} years`
                      : `${suggestion.unit}${suggestion.current_value.toLocaleString('en-IN', {
                          maximumFractionDigits: 0,
                        })}`}
                  </p>
                </div>

                <div className='space-y-2 mb-4'>
                  <div className='flex justify-between items-center'>
                    <span className='text-sm text-slate-600'>Current Approval</span>
                    <span className='font-bold text-slate-900'>
                      {suggestion.current_approval_prob?.toFixed(1)}%
                    </span>
                  </div>
                  <div className='flex justify-between items-center'>
                    <span className='text-sm text-slate-600'>New Approval</span>
                    <span className='font-bold text-green-600'>
                      {suggestion.new_approval_prob?.toFixed(1)}%
                    </span>
                  </div>
                  <div className='flex justify-between items-center pt-2 border-t border-slate-200'>
                    <span className='text-sm font-semibold text-slate-700'>Improvement</span>
                    <span className='text-lg font-bold text-green-600'>
                      +{suggestion.improvement_percent?.toFixed(1)}%
                    </span>
                  </div>
                </div>

                <button className='w-full bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 rounded-lg transition-colors'>
                  Apply This Option
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* 7. ALERTS */}
        {(metrics.dti_ratio > 40 || metrics.emi_to_income_ratio > 35) && (
          <div className='bg-red-50 border-l-4 border-red-500 rounded-xl p-6'>
            <div className='flex items-start gap-4'>
              <AlertTriangle className='w-6 h-6 text-red-500 flex-shrink-0 mt-0.5' />
              <div>
                <h4 className='text-lg font-bold text-red-900 mb-2'>⚠️ Financial Alert</h4>
                <p className='text-red-700'>
                  Your financial profile may lead to rejection in most banks. Your DTI is{' '}
                  <strong>{(metrics.dti_ratio || 0).toFixed(1)}%</strong> and EMI ratio is{' '}
                  <strong>{(metrics.emi_to_income_ratio || 0).toFixed(1)}%</strong>.
                </p>
                <p className='text-red-700 mt-2'>
                  <strong>Recommended:</strong> Consider increasing tenure, reducing loan amount, or paying down existing
                  loans before reapplying.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* 8. CHAT ASSISTANT */}
        <div className='bg-white rounded-xl shadow-md p-8'>
          <h3 className='text-2xl font-bold text-slate-900 mb-6 flex items-center gap-2'>
            <Bot className='w-6 h-6 text-indigo-500' />
            Chat Assistant
          </h3>

          <div className='space-y-4'>
            {/* Quick Questions */}
            <div className='mb-6'>
              <p className='text-sm font-semibold text-slate-700 mb-3'>Quick Questions:</p>
              <div className='grid grid-cols-1 md:grid-cols-2 gap-3'>
                {[
                  'Why was my application in this status?',
                  'How can I improve my approval chances?',
                  'What is my risk score?',
                  'What is the model confidence?',
                ].map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => sendChatMessage(q)}
                    className='p-3 bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-200 rounded-lg text-left text-sm font-medium text-slate-700 hover:bg-indigo-100 transition-colors'
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>

            {/* Chat Display */}
            {chatResponse && (
              <div className='bg-gradient-to-br from-indigo-50 to-purple-50 rounded-lg p-4 mb-4 border border-indigo-200'>
                <p className='text-sm text-slate-900'>{chatResponse}</p>
              </div>
            )}

            {/* Custom Input */}
            <div className='flex gap-2'>
              <input
                type='text'
                placeholder='Ask me anything about your loan...'
                value={chatMessage}
                onChange={e => setChatMessage(e.target.value)}
                onKeyPress={e => e.key === 'Enter' && sendChatMessage(chatMessage)}
                className='flex-1 px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500'
              />
              <button
                onClick={() => sendChatMessage(chatMessage)}
                className='px-6 py-2 bg-indigo-500 hover:bg-indigo-600 text-white font-semibold rounded-lg transition-colors'
              >
                Send
              </button>
            </div>
          </div>
        </div>

        {/* Reasons and Suggestions */}
        <div className='grid grid-cols-1 md:grid-cols-2 gap-6'>
          {/* Reasons */}
          <div className='bg-white rounded-xl shadow-md p-8'>
            <h3 className='text-xl font-bold text-slate-900 mb-4'>Decision Factors</h3>
            <ul className='space-y-3'>
              {(result?.reasons || []).map((reason, idx) => (
                <li key={idx} className='flex items-start gap-3'>
                  <ChevronRight className='w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5' />
                  <span className='text-slate-700'>{reason}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Suggestions */}
          <div className='bg-white rounded-xl shadow-md p-8'>
            <h3 className='text-xl font-bold text-slate-900 mb-4'>Next Steps</h3>
            <ul className='space-y-3'>
              {(result?.suggestions || []).map((suggestion, idx) => (
                <li key={idx} className='flex items-start gap-3'>
                  <CheckCircle2 className='w-5 h-5 text-green-500 flex-shrink-0 mt-0.5' />
                  <span className='text-slate-700'>{suggestion}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoanDashboard;
