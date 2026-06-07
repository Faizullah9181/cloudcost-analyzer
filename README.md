# Shimo - Multi-Cloud Cost Analysis Agent

**Shimo** is an AI-powered cloud cost analytics platform with a custom agent framework supporting AWS, Azure, GCP, and DigitalOcean. Analyze your multi-cloud spending with natural language queries via **CLI** or **Web Chat**, with persistent session management and LLM-powered insights.

![Stack](https://img.shields.io/badge/Python-3.12-blue) ![Stack](https://img.shields.io/badge/React-19-blue) ![Stack](https://img.shields.io/badge/FastAPI-0.115-green) ![Stack](https://img.shields.io/badge/Strands_Agents-1.36-purple) ![Stack](https://img.shields.io/badge/Multi_Cloud-AWS_Azure_GCP_DO-orange) ![Stack](https://img.shields.io/badge/TUI_CLI-Typer_Rich-cyan)

## 🎯 Features

### Cloud Providers
- ✅ **AWS** — Cost Explorer, EC2, RDS, Lambda, S3, Organizations
- ✅ **Azure** — Cost Management API, resource inventory, subscriptions
- ✅ **GCP** — Cloud Billing API, BigQuery export integration
- ✅ **DigitalOcean** — Billing API, droplets, volumes, databases

### Interfaces
- ✅ **CLI with TUI** — Interactive terminal chat with `/help`, `/sessions`, `/compress`, `/export`
- ✅ **Web Chat** — React 19 + TypeScript web interface
- ✅ **Session Management** — Persistent sessions, resume, export, compress context
- ✅ **API** — RESTful endpoints for programmatic access (`/api/sessions/*`)

### AI & Analysis
- ✅ **Natural Language Queries** — "Show me my GCP costs by service" → structured analysis
- ✅ **Multi-LLM Support** — Bedrock, OpenAI, Anthropic, Gemini, Ollama, Unsloth
- ✅ **Interactive Charts** — Bar, line, pie, area charts (Recharts)
- ✅ **Cost Trends** — Daily/monthly breakdowns, forecasting
- ✅ **Context Compression** — `/compress` command for long-running sessions
- ✅ **Session Memory** — Cross-session LLM summarization (clawsweeper pattern)

### Enterprise Features
- ✅ **Multi-Account** — AWS Organizations, Azure subscriptions, GCP projects
- ✅ **Custom Credentials** — Per-session cloud provider configuration
- ✅ **A2UI Messages** — Agent-to-UI protocol for structured outputs
- ✅ **Session Export** — JSON export for audits, archival, analysis

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│                  User Interfaces                  │
├──────────────────┬──────────────────────────────┤
│  Shimo CLI (TUI) │  React Web Chat              │
│  (Typer + Rich)  │  (http://localhost:5035)    │
└──────────┬───────┴──────────────────────────────┘
           │
    ┌──────▼──────────────────────────────────────┐
    │      Shimo Agent (FastAPI Backend)          │
    │   - Session persistence (SQLite)            │
    │   - Multi-cloud tool orchestration          │
    │   - Strands Agent integration               │
    └──────┬────────────────────────────────────┬─┘
           │                                    │
    ┌──────▼──────────────┐  ┌──────────────┐  │
    │  Multi-Cloud Tools  │  │  Multi-LLM   │  │
    │  ┌─ AWS (boto3)     │  │  ┌─ Bedrock  │  │
    │  ├─ Azure (SDK)     │  │  ├─ OpenAI   │  │
    │  ├─ GCP (SDK)       │  │  ├─ Gemini   │  │
    │  └─ DigitalOcean    │  │  └─ Others   │  │
    │    (REST API)       │  │              │  │
    └────────────────────┘  └──────────────┘  │
                                               │
    ┌──────────────────────────────────────────┘
    │
    └─ SQLite Session Store
       (messages, analysis, context)
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose (or Python 3.10+)
- At least one cloud provider account (AWS/Azure/GCP/DO)
- API credentials for selected providers
- LLM API key (Bedrock/OpenAI/Anthropic/etc.)

### 1. Clone & Configure

```bash
git clone https://github.com/Faizullah9181/Cloud-Analytics.git
cd Cloud-Analytics
cp .env.example .env
```

**Edit `.env` with your credentials:**

```env
# AWS
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_DEFAULT_REGION=us-east-1

# Azure (optional)
AZURE_TENANT_ID=xxx
AZURE_CLIENT_ID=xxx
AZURE_CLIENT_SECRET=xxx
AZURE_SUBSCRIPTION_ID=xxx

# GCP (optional)
GCP_PROJECT_ID=xxx
GCP_SERVICE_ACCOUNT_JSON=/path/to/sa.json

# DigitalOcean (optional)
DIGITALOCEAN_API_TOKEN=xxx

# LLM Provider
LLM_PROVIDER=bedrock  # or openai, gemini, anthropic, ollama, unsloth
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
BEDROCK_REGION=us-west-2
```

### 2. Run with Docker Compose

```bash
docker compose up --build
```

- **Web Chat**: [http://localhost:5035](http://localhost:5035)
- **API Docs**: [http://localhost:8001/docs](http://localhost:8001/docs)
- **Backend**: http://localhost:8001

### 3. Use Shimo CLI

**Inside Docker:**

```bash
docker compose exec backend shimo chat
```

**Local development:**

```bash
cd backend
pip install -r requirements.txt
python shimo_cli.py chat
```

## 📖 Usage

### Web Chat

1. Open [http://localhost:5035](http://localhost:5035)
2. Type natural language queries:
   - "What's my AWS spend this month?"
   - "Show GCP costs by service for the last 7 days"
   - "Compare Azure and DigitalOcean spending"
3. View interactive charts, service breakdowns, and recommendations
4. Sessions auto-save with full message history

### CLI (Shimo Agent)

```bash
$ shimo chat                          # Start new session
  Session name: Production Analysis
  Select cloud providers: AWS, Azure, GCP
  [Session ID: abc123...]

Shimo> What are my top AWS services by cost?
[Analyzing...]
  EC2: $1,234.56 (45%)
  RDS: $567.89 (21%)
  S3: $234.56 (9%)
  ...

Shimo> /sessions                      # List sessions
  - Production Analysis (15 messages)
  - Dev Costs (8 messages)

Shimo> /compress                      # Compress context for long sessions
✓ Context compressed (20 → 5 messages)

Shimo> /export                        # Export session to JSON
{session data...}

Shimo> /help                          # Show commands
```

**CLI Commands:**

| Command | Description |
|---------|-------------|
| `shimo chat [--session ID]` | Start/resume chat |
| `shimo new` | Create new session |
| `shimo sessions` | List active sessions |
| `shimo config` | Show configuration |
| `shimo export SESSION_ID` | Export session to JSON |
| `shimo delete SESSION_ID` | Archive session |

**In-Chat Commands:**

| Command | Description |
|---------|-------------|
| `/help` | Show command help |
| `/sessions` | List recent sessions |
| `/compress` | Compress long context |
| `/export` | Export current session |
| `/config` | Show session config |
| `/clouds` | Show enabled providers |
| `/exit` | Exit Shimo |

### API Endpoints

```bash
# Session Management
POST   /api/sessions                    # Create session
GET    /api/sessions                    # List sessions
GET    /api/sessions/{id}              # Get session
DELETE /api/sessions/{id}              # Archive session

# Messages
POST   /api/sessions/{id}/messages     # Add message
GET    /api/sessions/{id}/messages     # Get messages

# Analysis
POST   /api/sessions/{id}/analysis     # Update analysis
GET    /api/sessions/{id}/analysis     # Get last analysis
POST   /api/sessions/{id}/export       # Export session

# Legacy (AWS-only)
POST   /api/analyze                    # Analyze query
GET    /api/suggestions               # Get suggestions
```

## 📁 Project Structure

```
Cloud-Analytics/
├── backend/
│   ├── agents/
│   │   ├── cost_analyzer.py          # Strands Agent with multi-LLM
│   │   ├── shimo_agent.py            # Shimo Agent core
│   │   └── tools/
│   │       ├── aws_cost_tools.py     # 8 AWS tools
│   │       ├── azure_cost_tools.py   # 3 Azure tools
│   │       ├── gcp_billing_tools.py  # 3 GCP tools
│   │       └── digitalocean_tools.py # 3 DigitalOcean tools
│   ├── api/
│   │   ├── routes.py                 # Legacy AWS endpoints
│   │   └── sessions.py               # Session management API
│   ├── models/
│   │   └── session.py                # SQLAlchemy models (Session, Message, Credential)
│   ├── database.py                   # SQLite + SQLAlchemy setup
│   ├── config.py                     # Settings (all providers)
│   ├── main.py                       # FastAPI app
│   ├── shimo_cli.py                  # CLI entry point (Typer)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .pylintrc
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/               # React components
│   │   ├── api/                      # API client
│   │   ├── types/                    # TypeScript types
│   │   └── App.tsx
│   ├── Dockerfile
│   ├── vite.config.ts
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

## 🔧 Development

### Local Setup

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# Frontend (in another terminal)
cd frontend
npm install
npm run dev
```

- Backend: [http://localhost:8001](http://localhost:8001)
- Frontend: [http://localhost:5173](http://localhost:5173)

### Testing

```bash
# Lint backend
pylint backend/**/*.py

# Lint frontend
npm run lint
```

### Adding New Cloud Providers

1. Create `backend/agents/tools/{provider}_tools.py`:

```python
from strands_agents import tool

@tool(description="Get provider costs by service")
def provider_cost_by_service(project_id: str, start_date: str, end_date: str) -> dict:
    """Implement your provider API calls here."""
    return {"provider": "name", "services": {...}}
```

2. Update `backend/config.py` with credentials
3. Add tools to `cost_analyzer.py` agent definition
4. Test via CLI: `shimo chat`

## 📊 Multi-Cloud Cost Examples

### AWS to Azure Cost Parity

```
Shimo> Compare my AWS and Azure spending by service

Results:
AWS:                           Azure:
├─ Compute: $2,500 (42%)      ├─ Virtual Machines: $1,800 (35%)
├─ Storage: $800 (13%)        ├─ Storage: $900 (18%)
├─ Database: $1,200 (20%)     └─ SQL Database: $2,500 (49%)
└─ Networking: $950 (16%)
```

### GCP Budget Alert

```
Shimo> Alert me if GCP spending exceeds $5,000 this month

✓ Analysis configured
  Current: $3,200 (64% of budget)
  Projected: $4,100 by month-end
  Status: On track
```

### DigitalOcean Cost Optimization

```
Shimo> Find ways to save on DigitalOcean

Recommendations:
1. Downsize 3 idle droplets → Save $150/month
2. Enable automated snapshots → Save $50/month
3. Consolidate to 1 load balancer → Save $20/month
Total potential savings: $220/month
```

## 🔐 Security

- **Credentials**: Stored encrypted in SQLite (at-rest encryption via SQLAlchemy)
- **Sessions**: Per-session credential isolation
- **API**: All endpoints require valid session ID
- **CORS**: Restricted to configured origins
- **CLI**: Local-only by default (no cloud credential storage in files)

## 📝 License

MIT — See LICENSE file

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m "Add amazing feature"`)
4. Push to branch (`git push origin feature/amazing`)
5. Open Pull Request

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/Faizullah9181/Cloud-Analytics/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Faizullah9181/Cloud-Analytics/discussions)

---

**Built with ❤️ using Strands Agents, FastAPI, React, and cloud wisdom**
