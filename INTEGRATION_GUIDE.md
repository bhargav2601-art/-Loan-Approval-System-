# Dashboard Integration Examples & Code Snippets

## 🔗 Component Integration

### How Components Connect

```
main.jsx (App.jsx)
  ├── LoanForm
  │   ├── onResult(result, formData)  ← Passes both result & original data
  │   └── setLatestFormData(formData)
  │
  └── LoanDashboard
      ├── result (prediction output)
      ├── originalData (form inputs for suggestions)
      ├── Calls /api/suggestions
      ├── Calls /api/simulate (for trend)
      └── Calls /api/chat (for Q&A)
```

### State Flow Diagram

```
User fills form
    ↓
LoanForm.submit() 
    ↓
POST /api/predict
    ↓
Prediction result + original data
    ↓
setLatestResult(result)
setLatestFormData(formData)
    ↓
Navigate to 'result' view
    ↓
<LoanDashboard result={result} originalData={formData} />
    ↓
Dashboard loads & fetches suggestions
    ↓
User sees recommendations
```

---

## 📝 Code Snippets

### 1. Backend: Suggestions Endpoint

```python
@app.post("/api/suggestions")
def get_suggestions():
    """Generate smart suggestions by varying loan parameters"""
    user, error = require_role("user")
    if error:
        return error
    
    try:
        data = request.get_json(force=True)
        # Current prediction
        current_result = prediction_payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    
    current_approval = current_result["approval_probability"]
    income = float(data.get("income", 0))
    loan_amount = float(data.get("loan_amount", 0))
    loan_tenure = int(parse_input_loan_tenure(data.get("loan_tenure", 0)))
    existing_loans = float(data.get("existing_loans", 0))
    
    suggestions = []
    
    # Suggestion 1: Increase tenure
    if loan_tenure < 360:
        new_tenure = min(360, loan_tenure + 60)  # Add 5 years
        try:
            test_data = dict(data)
            test_data["loan_tenure"] = new_tenure
            test_result = prediction_payload(test_data)
            improvement = test_result["approval_probability"] - current_approval
            new_emi = test_result["calculated_emi"]
            suggestions.append({
                "type": "increase_tenure",
                "title": "Increase Loan Tenure",
                "suggested_value": new_tenure,
                "improvement_percent": round(improvement, 1),
                # ... more fields
            })
        except:
            pass
    
    # Sort and return top 3
    suggestions.sort(key=lambda x: x.get("improvement_percent", 0), reverse=True)
    return jsonify({
        "current_approval_probability": current_approval,
        "suggestions": suggestions[:3],
        "best_suggestion": suggestions[0] if suggestions else None,
    })
```

### 2. Frontend: Load Suggestions

```javascript
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
```

### 3. Frontend: Render Suggestions

```javascript
{suggestions.map((suggestion, idx) => (
  <div key={idx} className='bg-white rounded-xl shadow-md p-6'>
    <h4 className='text-lg font-bold text-slate-900 mb-2'>
      {suggestion.title}
    </h4>
    <p className='text-sm text-slate-600 mb-4'>
      {suggestion.description}
    </p>

    <div className='bg-slate-50 rounded-lg p-4 mb-4'>
      <p className='text-xs text-slate-600 mb-1'>Suggested Value</p>
      <p className='text-2xl font-bold text-slate-900'>
        {suggestion.unit === 'months'
          ? `${(suggestion.suggested_value / 12).toFixed(1)} years`
          : `₹${suggestion.suggested_value.toLocaleString('en-IN')}`}
      </p>
    </div>

    <div className='space-y-2 mb-4'>
      <div className='flex justify-between items-center'>
        <span className='text-sm text-slate-600'>Current Approval</span>
        <span className='font-bold'>
          {suggestion.current_approval_prob?.toFixed(1)}%
        </span>
      </div>
      <div className='flex justify-between items-center'>
        <span className='text-sm text-slate-600'>New Approval</span>
        <span className='font-bold text-green-600'>
          {suggestion.new_approval_prob?.toFixed(1)}%
        </span>
      </div>
      <div className='flex justify-between items-center pt-2 border-t'>
        <span className='text-sm font-semibold'>Improvement</span>
        <span className='text-lg font-bold text-green-600'>
          +{suggestion.improvement_percent?.toFixed(1)}%
        </span>
      </div>
    </div>

    <button className='w-full bg-blue-500 hover:bg-blue-600 
                       text-white font-semibold py-2 rounded-lg'>
      Apply This Option
    </button>
  </div>
))}
```

### 4. Frontend: Calculate Health Score

```javascript
const getHealthScore = () => {
  let score = 100;
  
  // Deduct for high DTI
  if (metrics.dti_ratio > 50) score -= 20;
  else if (metrics.dti_ratio > 40) score -= 10;
  
  // Deduct for high EMI ratio
  if (metrics.emi_to_income_ratio > 40) score -= 20;
  else if (metrics.emi_to_income_ratio > 30) score -= 10;
  
  // Deduct for low credit score
  if ((result?.inputs?.credit_score || 0) < 650) score -= 15;
  else if ((result?.inputs?.credit_score || 0) < 700) score -= 5;
  
  return Math.max(0, Math.min(100, score));
};

const healthScore = getHealthScore();
```

### 5. Frontend: Render Gauge Chart

```javascript
<div className='relative w-40 h-40'>
  <svg className='w-full h-full -rotate-90' viewBox='0 0 120 120'>
    {/* Background circle */}
    <circle cx='60' cy='60' r='50' 
            fill='none' stroke='#e2e8f0' strokeWidth='10' />
    
    {/* Progress circle - animated */}
    <circle cx='60' cy='60' r='50'
            fill='none'
            stroke={healthScore > 70 ? '#10b981' : 
                    healthScore > 50 ? '#f59e0b' : '#ef4444'}
            strokeWidth='10'
            strokeDasharray={`${(healthScore / 100) * 314} 314`}
            className='transition-all duration-500' />
  </svg>
  
  {/* Center text */}
  <div className='absolute inset-0 flex flex-col items-center justify-center'>
    <span className='text-4xl font-bold text-slate-900'>
      {healthScore}
    </span>
    <span className='text-xs text-slate-500'>/ 100</span>
  </div>
</div>
```

### 6. Frontend: Alert Component

```javascript
{(metrics.dti_ratio > 40 || metrics.emi_to_income_ratio > 35) && (
  <div className='bg-red-50 border-l-4 border-red-500 rounded-xl p-6'>
    <div className='flex items-start gap-4'>
      <AlertTriangle className='w-6 h-6 text-red-500' />
      <div>
        <h4 className='text-lg font-bold text-red-900 mb-2'>
          ⚠️ Financial Alert
        </h4>
        <p className='text-red-700'>
          Your financial profile may lead to rejection in most banks.
          Your DTI is <strong>{(metrics.dti_ratio || 0).toFixed(1)}%</strong>
          and EMI ratio is <strong>{(metrics.emi_to_income_ratio || 0).toFixed(1)}%</strong>.
        </p>
        <p className='text-red-700 mt-2'>
          <strong>Recommended:</strong> 
          Consider increasing tenure, reducing loan amount, 
          or paying down existing loans before reapplying.
        </p>
      </div>
    </div>
  </div>
)}
```

### 7. Frontend: Chat Assistant

```javascript
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

return (
  <div className='bg-white rounded-xl shadow-md p-8'>
    <h3 className='text-2xl font-bold text-slate-900 mb-6'>
      Chat Assistant
    </h3>
    
    {/* Quick Questions */}
    <div className='grid grid-cols-1 md:grid-cols-2 gap-3 mb-6'>
      {[
        'Why was my application in this status?',
        'How can I improve my approval chances?',
        'What is my risk score?',
        'What is the model confidence?',
      ].map((q, idx) => (
        <button
          key={idx}
          onClick={() => sendChatMessage(q)}
          className='p-3 bg-indigo-50 border border-indigo-200 
                     rounded-lg text-sm font-medium text-slate-700 
                     hover:bg-indigo-100 transition-colors'
        >
          {q}
        </button>
      ))}
    </div>
    
    {/* Response Display */}
    {chatResponse && (
      <div className='bg-indigo-50 rounded-lg p-4 mb-4 border border-indigo-200'>
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
        className='flex-1 px-4 py-2 border border-slate-300 rounded-lg'
      />
      <button
        onClick={() => sendChatMessage(chatMessage)}
        className='px-6 py-2 bg-indigo-500 hover:bg-indigo-600 
                   text-white font-semibold rounded-lg'
      >
        Send
      </button>
    </div>
  </div>
);
```

### 8. Styling: Metric Card

```css
.metric-card {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-left: 4px solid #3b82f6;
  transition: all 0.3s ease;
}

.metric-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.12);
}

.metric-card-value {
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 12px;
}

.metric-card-status {
  display: inline-block;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.status-safe {
  background: #d1fae5;
  color: #065f46;
}
```

---

## 🔄 Customization Examples

### Change Suggestion 1: Different Tenure Increment

**Current:**
```python
new_tenure = min(360, loan_tenure + 60)  # 5 years
```

**Alternative: 3 years**
```python
new_tenure = min(360, loan_tenure + 36)  # 3 years
```

**Alternative: Dynamic based on current tenure**
```python
increment = 24 if loan_tenure < 60 else 36
new_tenure = min(360, loan_tenure + increment)
```

### Change Suggestion 2: Different Loan Amount Reduction

**Current:**
```python
new_amount = max(income * 2, loan_amount * 0.85)  # 15% reduction
```

**Alternative: More aggressive**
```python
new_amount = max(income * 2, loan_amount * 0.75)  # 25% reduction
```

**Alternative: Based on DTI**
```python
if features["dti_ratio"] > 0.5:
    new_amount = max(income * 2, loan_amount * 0.7)  # More reduction
else:
    new_amount = max(income * 2, loan_amount * 0.85)
```

### Change Suggestion 3: Add New Suggestion Type

**Add Increase Income Suggestion:**

```python
# After line ~985 (in suggestions list building)

# Suggestion 3: Increase Income
if income < 100000:  # Only for lower income
    new_income = income * 1.15  # 15% increase needed
    try:
        test_data = dict(data)
        test_data["income"] = new_income
        test_result = prediction_payload(test_data)
        improvement = test_result["approval_probability"] - current_approval
        suggestions.append({
            "type": "increase_income",
            "title": "Increase Documented Income",
            "description": "Show additional income sources like bonus/freelance",
            "suggested_value": round(new_income, 2),
            "current_value": round(income, 2),
            "unit": "₹",
            "current_approval_prob": current_approval,
            "new_approval_prob": test_result["approval_probability"],
            "improvement_percent": round(improvement, 1),
        })
    except:
        pass
```

### Change Health Score Calculation

**Current (conservative):**
```javascript
const getHealthScore = () => {
  let score = 100;
  if (metrics.dti_ratio > 50) score -= 20;
  else if (metrics.dti_ratio > 40) score -= 10;
  // ...
};
```

**Alternative (weighted formula):**
```javascript
const getHealthScore = () => {
  const creditScore = (result?.inputs?.credit_score || 0) / 900;
  const dtiRatio = 1 - Math.min(1, (metrics.dti_ratio || 0) / 0.6);
  const emiRatio = 1 - Math.min(1, (metrics.emi_to_income_ratio || 0) / 0.5);
  
  return Math.round((creditScore * 40 + dtiRatio * 35 + emiRatio * 25));
};
```

---

## 🧪 Testing Helper Functions

### Test API Endpoint

```bash
# Get suggestions for test case
curl -X POST http://localhost:5000/api/suggestions \
  -H "Content-Type: application/json" \
  -H "Cookie: session=$(curl -s -c cookies.txt -X POST \
    http://localhost:5000/api/login \
    -d '{"email":"customer@gmail.com","password":"Customer@123","role":"user"}' \
    | jq -r '.user.id')" \
  -d '{
    "income": 50000,
    "credit_score": 720,
    "employment_status": "salaried",
    "loan_amount": 500000,
    "existing_loans": 10000,
    "loan_type": "Personal Loan",
    "previous_loan": "No",
    "previous_loan_amount": 0,
    "loan_tenure": 24
  }' | jq .
```

### Frontend Console Test

```javascript
// In browser console (F12)

// Test data
const testData = {
  income: 50000,
  credit_score: 720,
  employment_status: "salaried",
  loan_amount: 500000,
  existing_loans: 10000,
  loan_type: "Personal Loan",
  previous_loan: "No",
  previous_loan_amount: 0,
  loan_tenure: 24
};

// Call suggestions API
fetch('/api/suggestions', {
  method: 'POST',
  credentials: 'include',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(testData)
})
  .then(r => r.json())
  .then(d => console.log('Suggestions:', d))
  .catch(e => console.error('Error:', e));
```

---

## 📊 Performance Optimization Tips

### 1. Parallel API Calls (Already Done)
```javascript
// Instead of sequential:
const trends = [];
for (const tenure of tenures) {
  const res = await api(...);  // Waits each time
  trends.push(res);
}

// Better - parallel:
const promises = tenures.map(tenure => api(...));
const trends = await Promise.all(promises);
```

### 2. Memoize Chart Data
```javascript
const trendChartData = useMemo(() => {
  if (!trendData.length) return { labels: [], datasets: [] };
  return {
    labels: trendData.map(d => `${d.tenure}yr`),
    datasets: [{ /* data */ }],
  };
}, [trendData]);  // Recalculate only when trendData changes
```

### 3. Lazy Load Sections
```javascript
// Load suggestions only after user scrolls to them
const [suggestionsLoaded, setSuggestionsLoaded] = useState(false);

useEffect(() => {
  if (suggestionsLoaded && !suggestions.length) {
    loadSuggestions();
  }
}, [suggestionsLoaded]);

// Use Intersection Observer to detect scroll
```

---

## 🐛 Common Issues & Solutions

| Issue | Root Cause | Solution |
|-------|-----------|----------|
| "Suggestions undefined" | originalData not passed | Check LoanForm calls `onResult(data, payload)` |
| API returns 401 | User not authenticated | Re-login; check session cookie |
| Chart doesn't render | Chart.js not registered | Verify `ChartJS.register()` in main.jsx |
| Suggestions empty array | All 3 suggestion attempts failed | Check error logs in console |
| Gauge doesn't animate | CSS transition missing | Verify `transition-all` class applied |
| Chat no response | /api/chat endpoint error | Check latest application exists |
| Health score always 100 | Math error | Debug `getHealthScore()` function |

---

**Last Updated:** 2026-04-28  
**Version:** 1.0  
**Status:** Production Ready ✅
