# AI Customer Support Agent

A fully functional AI-powered customer support agent for e-commerce refund processing, built with 100% free tools.

## Stack (All Free)
| Layer | Technology |
|-------|-----------|
| LLM | [Groq API](https://console.groq.com) — free tier, Llama 3.3 70B |
| Agent Loop | LangGraph (stateful agent with tool-calling) |
| Backend | FastAPI + Uvicorn |
| Frontend | Vanilla HTML/CSS/JS (zero dependencies) |
| Voice | Web Speech API (browser built-in — STT + TTS) |
| Database | JSON flat files (no DB server) |

## Features
- **Refund Agent**: LangGraph agent loop that calls tools to validate policy rules step-by-step
- **15 Customer CRM**: Mock profiles with order history, refund history, and account standing
- **Strict Policy Engine**: 6 policy rules (return window, order status, abuse detection, flagged accounts, etc.)
- **Voice Interface**: Click the 🎤 mic button to speak your request; agent replies are read aloud via TTS
- **Admin Dashboard**: Real-time view of agent reasoning logs (tool calls + results), session list, and full CRM table
- **Quick Test Buttons**: One-click scenarios for standard refund, expired window, flagged account

## Project Structure
```
SupportAgent/
├── backend/
│   ├── main.py          # FastAPI app — routes, session management
│   ├── agent.py         # LangGraph agent — tool-calling loop
│   ├── tools.py         # Business logic — CRM + policy validation
│   └── data/
│       ├── crm.json     # 15 customer profiles
│       └── policy.json  # Refund policy rules
├── frontend/
│   ├── index.html       # Customer chat UI + voice component
│   └── admin.html       # Admin dashboard with reasoning logs
├── venv/                # Python virtual environment
├── .env                 # GROQ_API_KEY goes here
├── requirements.txt
└── README.md
```

## Setup

### 1. Get a Free Groq API Key
1. Go to [console.groq.com](https://console.groq.com)
2. Sign up (free) → create an API key
3. Paste it in `.env`:
```
GROQ_API_KEY=gsk_your_key_here
```

### 2. Activate venv and run
```bash
# Windows
venv\Scripts\activate
cd backend
python -m uvicorn main:app --reload
```

### 3. Open in browser
- **Customer Chat**: http://localhost:8000
- **Admin Dashboard**: http://localhost:8000/admin

## Demo Scenarios

### Standard Refund (Approved)
> "I want to request a refund for order ORD-1001"
- Customer: Alice Johnson (C001)
- Result: ✅ Approved — delivered 25 days ago, good standing

### Expired Return Window (Denied)
> "I want a refund for order ORD-1003"
- Customer: Carol White (C003)
- Order purchased 2025-04-01 — over 30-day window
- Result: ❌ Denied — R1 rule violation

### Flagged Account (Denied)
> "My email is david.lee@email.com, I want a refund for ORD-1004"
- Customer: David Lee (C004) — flagged for abuse (3 prior refunds)
- Result: ❌ Denied — R3 + R4 rule violations

### In-Transit Order (Denied)
> "I want a refund for order ORD-1007"
- Customer: Grace Kim (C007) — order still in transit
- Result: ❌ Denied — R2 rule violation

### Policy Question
> "What is your refund policy?"
- Agent retrieves and explains full policy

## Agent Architecture

```
User Message
     │
     ▼
 LangGraph AgentState
     │
     ▼
 LLM (Llama 3.3 70B via Groq)
     │
     ├─── tool_lookup_customer    → CRM lookup
     ├─── tool_check_refund_policy → Run 6 policy rules
     ├─── tool_process_refund      → Finalize decision
     └─── tool_get_policy_summary  → Answer policy questions
     │
     ▼
 Final Response + Reasoning Logs
```

The agent loop runs until no more tool calls are needed, then returns the final answer. All intermediate tool calls and results are captured in `logs` and streamed to the admin dashboard.
