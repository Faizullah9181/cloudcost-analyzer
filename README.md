# Cloud Analytics

Natural language AWS cost analysis powered by [Strands Agents](https://github.com/strands-agents/sdk-python). Ask questions about your AWS costs in plain English and get detailed breakdowns, trends, and optimization recommendations with interactive charts.

![Stack](https://img.shields.io/badge/React-19-blue) ![Stack](https://img.shields.io/badge/FastAPI-0.115-green) ![Stack](https://img.shields.io/badge/Strands_Agents-1.36-purple) ![Stack](https://img.shields.io/badge/Docker-Compose-blue)

## Features

- **Natural Language Queries** — Ask "What's my AWS spend this month?" and get structured analysis
- **Interactive Charts** — Bar, line, pie, and area charts via Recharts
- **Service Breakdown** — Cost breakdown by AWS service with percentage and change indicators
- **Cost Trends** — Daily/monthly time series analysis
- **Multi-Account** — Support for AWS Organizations multi-account analysis
- **Cost Forecasting** — Predicted spend based on current usage patterns
- **Optimization Tips** — AI-generated cost reduction recommendations
- **A2UI Output** — Every analysis includes schema-aligned A2UI message JSON for agent-to-UI rendering
- **Multi-LLM Support** — Bedrock, OpenAI, Anthropic, Ollama, Gemini, or Unsloth Studio

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Agent | Strands Agents SDK |
| Backend | FastAPI + Python 3.12 |
| Frontend | React 19 + TypeScript + Vite |
| Charts | Recharts |
| Styling | Tailwind CSS |
| Infra | Docker + Docker Compose |
| Linting | Pylint + ESLint |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- AWS credentials with Cost Explorer access (`ce:GetCostAndUsage`, `ce:GetCostForecast`)
- An LLM provider (AWS Bedrock recommended)

### 1. Clone & configure

```bash
git clone https://github.com/Faizullah9181/Cloud-Analytics.git
cd Cloud-Analytics
cp .env.example .env
# Edit .env with your AWS credentials and LLM provider
```

### 2. Run with Docker Compose

```bash
docker compose up --build
```

- Frontend: [http://localhost:5035](http://localhost:5035)
- Backend API: [http://localhost:8001](http://localhost:8001)

### 3. Local development (without Docker)

**Backend:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on [http://localhost:5173](http://localhost:5173) with API proxy to backend.

## Project Structure

```
Cloud-Analytics/
├── backend/
│   ├── agents/
│   │   ├── cost_analyzer.py      # Strands Agent with cost analysis prompt
│   │   └── tools/
│   │       └── aws_cost_tools.py  # 8 custom @tool functions (boto3)
│   ├── api/
│   │   └── routes.py             # FastAPI endpoints
│   ├── models/
│   │   └── __init__.py           # Pydantic schemas
│   ├── config.py                 # Settings (env-based)
│   ├── main.py                   # FastAPI app entry
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .pylintrc
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AnalysisCard.tsx   # Analysis result display
│   │   │   ├── ChatInput.tsx      # Natural language input
│   │   │   ├── CostChart.tsx      # Recharts charts
│   │   │   ├── DashboardLayout.tsx
│   │   │   ├── MessageList.tsx    # Chat messages
│   │   │   └── ServiceBreakdown.tsx
│   │   ├── api/client.ts         # API client
│   │   ├── types/index.ts        # TypeScript interfaces
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── Dockerfile
│   ├── nginx.conf
│   └── eslint.config.js
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## Example Queries

- "What's my total AWS spend this month?"
- "Show me cost breakdown by service for the last 3 months"
- "What are my daily cost trends this week?"
- "Which region costs the most?"
- "Give me a cost forecast for next month"
- "How many EC2 instances, S3 buckets, and Lambda functions do I have?"
- "Show costs by tag for project X"

## Linting

```bash
# Backend
cd backend && pylint **/*.py

# Frontend
cd frontend && npm run lint
```

## License

MIT
