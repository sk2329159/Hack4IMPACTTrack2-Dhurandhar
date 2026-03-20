# SENTINEL-AI

#Hack4IMPACTTrack2-Dhurandhar

Hack4Impact 2025 — Track 2  
Domain: **Cybersecurity & Ethical AI Systems**

## Team
**Team Name:** Dhurandhar
  
**Members:**  
- Swarnim Kumar
- Rakshit Raj  
- Swayam Mansingh
- Swastik Suman Nayak

## Approved Problem Statement
**Mitigating National Security Risks Posed by Large Language Models (LLMs) in AI-Driven Malign Information Operations**

## Overview
SENTINEL-AI is an AI-native threat intelligence platform that detects AI-generated malicious narratives, attributes likely LLM families (GPT/Claude/Gemini/Unknown), and supports campaign-level analysis for identifying coordinated information operations. The platform is designed with a security-first and privacy-preserving approach, providing a SOC-style dashboard for real-time monitoring, analytics, and investigation support.

## Key Capabilities (MVP)
- **AI-Generated Content Detection:** probability scoring with confidence
- **Model Attribution (MVP):** GPT-family / Claude-family / Gemini-family / Unknown
- **Risk Classification:** LOW / MEDIUM / HIGH / CRITICAL
- **Campaign-Level Intelligence:** cluster grouping + propagation graph (nodes/links)
- **Dashboard Overview:** KPIs, recent detections, trend chart, campaign graph
- **Security & Governance:** JWT + RBAC, data minimization, audit-safe logging

## Architecture (High Level)
**React Dashboard** → **FastAPI Backend (JWT + RBAC)** → **Detection Module (local Python)** → **PostgreSQL (Docker)**  
All dashboard visuals are powered by a single overview endpoint for stability and demo readiness.

## Tech Stack
**ML / NLP**
- Python
- HuggingFace Transformers (detector model)
- Stylometric features (preprocessing + heuristics)

**Backend**
- FastAPI + Uvicorn
- PostgreSQL 15
- SQLAlchemy + psycopg2
- Docker + Docker Compose
- JWT Authentication + Role-Based Access Control (RBAC)

**Frontend**
- React (Vite)
- Recharts (trend charts)
- D3 / Force graph (campaign propagation visualization)
- Tailwind CSS (UI styling)

## API (Locked MVP Contract)
This MVP intentionally uses **only 3 endpoints** for reliability:

1) `POST /api/v1/auth/login` (public)  
2) `POST /api/v1/detect` (JWT required: analyst/admin)  
3) `GET /api/v1/dashboard/overview` (JWT required: viewer/analyst/admin)

Full schema is documented in: `docs/INTEGRATION_CONTRACT.md`

## Database (What is Stored)
To reduce leakage risk, the system follows **data minimization**:
- Stores `content_hash` and `text_preview` (first 200–300 chars) by default
- Stores AI probability, confidence, risk level, attribution label, timestamps
- Does **not** store IP addresses
- Avoids logging raw content

MVP tables:
- `content`
- `detection_result`
- `actor`
- `network_edge`

## Security & Ethical Safeguards
- **JWT + RBAC:** viewer / analyst / admin roles
- **No mass surveillance:** analyzes only submitted content (or authorized datasets)
- **No auto-censorship:** flags and scores content; high-stakes actions require human review
- **CORS allowlist:** only approved frontend origins
- **Safe logging:** no raw content in logs; audit by hash + metadata
- **DB isolation:** PostgreSQL runs in Docker; restrict exposure in deployment

## Getting Started (Local, Docker)
### Prerequisites
- Docker + Docker Compose
- Node.js (for dashboard dev)
- Python (optional for local ML tests; backend runs in Docker)

### 1) Start Backend + Postgres
From repo root:
```bash
docker compose up --build
```
Backend:

API: http://localhost:8000
Swagger (if enabled): http://localhost:8000/docs
### 2) Run Frontend (Dashboard)
```Bash

cd dashboard
npm install
npm run dev
```
Dashboard:

http://localhost:5173

### 3) Quick API Test Flow (Manual)
1. Login → get JWT
2. Call /detect with Authorization header
3. Call /dashboard/overview to populate KPIs/graph/trends

Demo Flow (Judging)

1. Login (analyst role)
2. Paste suspicious narrative into “Analyze Content”
3. View AI probability, attribution, risk level, explanation
4. Dashboard updates: KPIs + recent detections + trends + campaign graph
5. Repeat with multiple samples to show cluster/campaign behavior

### Credits / Attributions
This project may use open-source libraries, pre-trained models, and public datasets. All sources and dependencies will be credited in documentation and final submission notes.

License
MIT 






