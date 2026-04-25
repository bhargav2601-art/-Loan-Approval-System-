# SmartLoan AI - Loan Approval Decision System

A full-stack AI-powered loan approval demo with user OTP login, user/admin email login, explainable predictions, risk scoring, dashboard analytics, chatbot support, fraud checks, and an admin portfolio view.

## Folder Structure

```text
LOAN PREDICTION SYSTEM/
├── app.py                    # Flask API and static React serving
├── db_setup.py               # SQLite schema setup/migration
├── train_model.py            # Dummy dataset generation + model training
├── loan_data.csv             # Generated training dataset
├── model.pkl                 # Trained Random Forest pipeline
├── loan.db                   # SQLite database
├── requirements.txt          # Python dependencies
├── frontend/
│   ├── index.html
│   ├── package.json
│   └── src/
│       ├── main.jsx          # React app
│       └── styles.css        # Fintech UI styling
├── templates/                # Legacy Flask templates kept for reference
└── static/                   # Legacy static assets kept for reference
```

## Features

- Premium fintech React UI inspired by modern banking dashboards.
- OTP-based customer login with a local demo OTP fallback.
- Email/password authentication with separate User and Admin login.
- Role-based access control for customer and bank officer screens.
- AI loan prediction using Random Forest.
- Risk score from 0 to 100.
- Explainable decision reasons and improvement suggestions.
- User dashboard with Chart.js approval and risk analytics.
- Floating chatbot for loan explanations.
- Admin dashboard for users, approval mix, all applications, high-risk users, suspicious entries, duplicate email checks, and data insights.

## Backend APIs

The backend exposes both `/api/...` routes for the React app and direct routes matching the project brief:

- `POST /register` or `/api/register`
- `POST /login` or `/api/login`
- `POST /send_otp` or `/api/send_otp`
- `POST /verify_otp` or `/api/verify_otp`
- `POST /predict` or `/api/predict`
- `GET /user-loans` or `/api/user-loans`
- `GET /admin-data` or `/api/admin-data`
- `POST /chat` or `/api/chat`
- `GET /history` or `/api/history`
- `GET /api/admin/stats`

User-only routes return `Access Denied – Unauthorized Role` for admins. Admin-only routes return the same error for normal users.

## Run Step By Step

1. Create and activate a Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install backend dependencies:

```bash
pip install -r requirements.txt
```

3. Train or refresh the ML model:

```bash
python3 train_model.py
```

4. Initialize the database:

```bash
python3 db_setup.py
```

5. Start Flask:

```bash
python3 app.py
```

6. In a second terminal, start React:

```bash
cd frontend
npm install
npm run dev
```

7. Open:

```text
http://localhost:5173
```

## Demo Login

- Admin email: `admin@smartloan.ai`
- Admin password: `Admin@123`
- Demo user email: `customer@gmail.com`
- Demo user password: `Customer@123`
- Demo OTP phone: `9876543210`

## Auth Notes

Passwords are hashed with Werkzeug before being stored in SQLite. OTPs are stored in `otp_logs` with a five-minute expiry; local development returns `dev_otp` from `/send_otp` so the demo works without Twilio credentials. In production, connect Twilio inside the marked `/send_otp` block and stop returning `dev_otp`.
