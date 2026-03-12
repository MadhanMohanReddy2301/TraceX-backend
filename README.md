<p align="center">
  <h1 align="center">🔍 TraceX Backend</h1>
  <p align="center">
    <em>AI-Powered Requirements Traceability & Test Case Generation Platform</em>
  </p>
  <p align="center">
    <a href="#features">Features</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#getting-started">Getting Started</a> •
    <a href="#api-reference">API Reference</a> •
    <a href="#deployment">Deployment</a>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/Google_ADK-1.13-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Google ADK">
    <img src="https://img.shields.io/badge/Gemini-2.0_Flash-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white" alt="Gemini">
    <img src="https://img.shields.io/badge/FastAPI-0.120-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
    <img src="https://img.shields.io/badge/Cloud_Run-Deployable-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white" alt="Cloud Run">
  </p>
</p>

---

## 📖 Overview

**TraceX** is an intelligent backend platform that automates software requirements traceability using a multi-agent AI system. Built on [Google's Agent Development Kit (ADK)](https://google.github.io/adk-docs/) and powered by **Gemini 2.0 Flash**, TraceX processes raw requirement documents (PDF, DOCX, TXT) and sequentially runs them through **7 specialized AI agents** to produce comprehensive traceability artifacts — including test cases, edge cases, compliance checks, traceability matrices, and integration test plans.

### 🤔 What Problem Does TraceX Solve?

In software development, **requirements traceability** — the ability to trace requirements through design, implementation, and testing — is critical for regulatory compliance (ISO 26262, DO-178C, FDA, etc.), quality assurance, and audit readiness. Traditionally, this process is:

- ⏳ **Time-consuming** — Manual creation of traceability matrices takes days
- 🐛 **Error-prone** — Human oversight often misses edge cases and gaps
- 📝 **Tedious** — Writing test cases for every requirement is repetitive

TraceX automates this entire pipeline in seconds, delivering production-grade traceability artifacts with a single API call.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **Multi-Agent Pipeline** | 7 AI agents working sequentially to analyze requirements end-to-end |
| 📄 **Document Ingestion** | Upload PDF, DOCX, or TXT files — text is auto-extracted |
| 🧪 **Auto Test Generation** | Generates comprehensive test cases and edge cases from requirements |
| ✅ **Compliance Checking** | Validates requirements against industry standards and regulations |
| 🔗 **Traceability Matrix** | Automatically maps requirements → tests → components |
| 🔌 **Integration Testing** | Produces integration test plans across system boundaries |
| 📚 **Knowledge Base Lookup** | Queries a RAG-based knowledge base for contextual enrichment |
| 🏗️ **Cloud-Native** | Dockerized and ready for Google Cloud Run deployment |
| ⚡ **MCP Integrations** | Connects to Jira, BigQuery, and RAG via Model Context Protocol servers |

---

## 🏗️ Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        TraceX Backend                                │
│                                                                      │
│  ┌──────────┐    ┌──────────────────────────────────────────────┐    │
│  │ FastAPI   │    │       Sequential Agent Pipeline              │    │
│  │ REST API  │───▶│                                              │    │
│  │           │    │  ┌─────────┐  ┌────────┐  ┌──────────────┐  │    │
│  │ /run      │    │  │ Ingest  │─▶│   KB   │─▶│  Test Case   │  │    │
│  │ /run/upload│   │  │ Agent   │  │ Agent  │  │    Agent     │  │    │
│  │ /health   │    │  └─────────┘  └────────┘  └──────┬───────┘  │    │
│  └──────────┘    │                                    │          │    │
│                  │  ┌─────────────┐  ┌────────────┐  ▼          │    │
│                  │  │ Integration │◀─│Traceability│◀─┌────────┐  │    │
│                  │  │   Agent     │  │   Agent    │  │Edge    │  │    │
│                  │  └─────────────┘  └────────────┘  │Case    │  │    │
│                  │                                    │Agent   │  │    │
│                  │  ┌────────────┐                    └───┬────┘  │    │
│                  │  │Compliance  │◀───────────────────────┘      │    │
│                  │  │  Agent     │                                │    │
│                  │  └────────────┘                                │    │
│                  └──────────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────────── MCP Tool Servers ──────────────────────────┐  │
│  │  📊 BigQuery MCP  │  📋 Jira MCP  │  📚 RAG Knowledge Base   │  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### Agent Pipeline

The agents execute **sequentially** in the following order, each building upon the output of the previous:

| # | Agent | Responsibility |
|---|---|---|
| 1 | **IngestAgent** | Parses and structures raw requirement text into a normalized format |
| 2 | **KbAgent** | Enriches requirements with context from the RAG knowledge base |
| 3 | **TestCaseAgent** | Generates functional and non-functional test cases for each requirement |
| 4 | **EdgeCaseAgent** | Identifies edge cases, boundary conditions, and negative test scenarios |
| 5 | **ComplianceAgent** | Checks requirements against compliance standards and regulatory rules |
| 6 | **TraceabilityAgent** | Builds a traceability matrix mapping requirements to tests and components |
| 7 | **IntegrationAgent** | Produces integration test plans for cross-component interactions |

### MCP Tool Servers

TraceX leverages the **Model Context Protocol (MCP)** to integrate with external services:

- **BigQuery MCP Server** — Query historical project data from Google BigQuery
- **Jira MCP Server** — Fetch and sync requirements/issues from Jira
- **RAG MCP Server** — Retrieve relevant knowledge from a vector-based RAG knowledge base

---

## 📂 Project Structure

```
TraceX-backend/
├── agents/                     # AI Agent modules
│   ├── IngestAgent/            # Requirement ingestion & parsing
│   ├── KbAgent/                # Knowledge base lookup agent
│   ├── TestCaseAgent/          # Test case generation agent
│   ├── EdgeCaseAgent/          # Edge case identification agent
│   ├── ComplianceAgent/        # Compliance verification agent
│   ├── TraceabilityAgent/      # Traceability matrix generation
│   ├── IntegrationAgent/       # Integration test planning agent
│   └── __init__.py
├── agent_tools/                # MCP server tool integrations
│   ├── bigquery_mcp_server/    # BigQuery MCP connection
│   ├── jira_mcp_server/        # Jira MCP connection
│   ├── rag_mcp_server/         # RAG knowledge base MCP connection
│   └── __init__.py
├── app.py                      # FastAPI application (with file upload)
├── rest_api.py                 # FastAPI application (text-only API)
├── main.py                     # CLI interactive runner
├── seq_flow.py                 # Sequential workflow runner with file output
├── requirements.txt            # Python dependencies
├── pyproject.toml              # Project metadata (uv/pip)
├── Dockerfile                  # Docker container configuration
├── .env                        # Environment variables
└── .python-version             # Python version specification
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Google Cloud Project** with Vertex AI enabled
- **Google Application Credentials** (service account key JSON)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### 1. Clone the Repository

```bash
git clone https://github.com/MadhanMohanReddy2301/TraceX-backend.git
cd TraceX-backend
```

### 2. Set Up Environment Variables

Create a `.env` file in the project root:

```env
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GEMINI_MODEL=gemini-2.0-flash
GOOGLE_APPLICATION_CREDENTIALS=key.json
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-east4

# MCP Server URLs
JIRA_MCP_SERVER_URL=https://your-jira-mcp-server-url/sse
BIGQUERY_MCP_SERVER_URL=https://your-bigquery-mcp-server-url/sse
KB_RAG_MCP_SERVER_URL=https://your-rag-mcp-server-url/sse

# Google API Key (for non-Vertex AI usage)
GOOGLE_API_KEY=your-api-key
```

> **Note:** Place your Google Cloud service account key file (e.g., `key.json`) in the project root.

### 3. Install Dependencies

**Using uv (recommended):**
```bash
uv sync
```

**Using pip:**
```bash
pip install -r requirements.txt
```

### 4. Run the Application

**Option A — FastAPI Server (recommended for production):**
```bash
python app.py
# or
uvicorn app:app --host 0.0.0.0 --port 8080
```

**Option B — Interactive CLI:**
```bash
python main.py
```

The server will start at `http://localhost:8080`.

---

## 📡 API Reference

### `POST /run` — Analyze Requirements (Text Input)

Submit raw requirement text for analysis.

**Request:**
```json
{
  "requirement_text": "The system shall authenticate users via OAuth 2.0...",
  "user_id": "user1",
  "session_id": "session1",
  "timeout_seconds": 60
}
```

**Response:**
```json
{
  "aggregated": "Combined output from all agents...",
  "per_agent": [
    {
      "agent_name": "IngestAgent",
      "outputs": ["Parsed requirement: ..."]
    },
    {
      "agent_name": "TestCaseAgent",
      "outputs": ["TC-001: Verify OAuth 2.0 login flow..."]
    },
    {
      "agent_name": "ComplianceAgent",
      "outputs": ["PASS: Meets OWASP authentication standards..."]
    }
  ]
}
```

### `POST /run/upload` — Analyze Requirements (File Upload)

Upload a document file (`.pdf`, `.docx`, `.txt`) for analysis.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | ✅ | Requirement document (.pdf, .docx, .txt) |
| `user_id` | string | ❌ | User identifier (default: `user1`) |
| `session_id` | string | ❌ | Session identifier (default: `session1`) |
| `timeout_seconds` | integer | ❌ | Max execution time (default: `600`) |

**cURL Example:**
```bash
curl -X POST http://localhost:8080/run/upload \
  -F "file=@requirements_document.pdf" \
  -F "timeout_seconds=300"
```

**Response:**
```json
{
  "aggregated": "Combined output from all agents...",
  "per_agent": [...],
  "extracted_text_length": 4520
}
```

### `GET /health` — Health Check

```bash
curl http://localhost:8080/health
```

**Response:**
```json
{
  "status": "ok",
  "agent": "SequentialRequirementWorkflowAPI"
}
```

---

## 🐳 Deployment

### Docker

```bash
# Build the image
docker build -t tracex-backend .

# Run the container
docker run -p 8080:8080 \
  -v $(pwd)/key.json:/app/key.json \
  --env-file .env \
  tracex-backend
```

### Google Cloud Run

```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/tracex-backend

# Deploy to Cloud Run
gcloud run deploy tracex-backend \
  --image gcr.io/YOUR_PROJECT_ID/tracex-backend \
  --platform managed \
  --region us-east4 \
  --port 8080 \
  --allow-unauthenticated
```

---

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| [Google ADK](https://google.github.io/adk-docs/) | Agent Development Kit for building and orchestrating AI agents |
| [Gemini 2.0 Flash](https://ai.google.dev/gemini-api) | LLM powering each AI agent |
| [FastAPI](https://fastapi.tiangolo.com/) | High-performance async REST API framework |
| [Google Cloud BigQuery](https://cloud.google.com/bigquery) | Historical data queries via MCP |
| [Jira (MCP)](https://www.atlassian.com/software/jira) | Issue/requirement tracking integration |
| [PyPDF2](https://pypdf2.readthedocs.io/) | PDF text extraction |
| [python-docx](https://python-docx.readthedocs.io/) | DOCX text extraction |
| [Docker](https://www.docker.com/) | Containerization |
| [Google Cloud Run](https://cloud.google.com/run) | Serverless deployment |

---

## 🧪 Usage Example

### Interactive CLI

```
$ python main.py
Initializing [🤖] : SequentialRequirementWorkflow
Enter your requirement text (empty to exit):
> The system shall support user registration with email verification

==================================================
------------------- IngestAgent IS RUNNING ----------------------
==================================================
[Parsed and structured requirements...]

==================================================
------------------- KbAgent IS RUNNING ----------------------
==================================================
[Knowledge base enrichment results...]

==================================================
------------------- TestCaseAgent IS RUNNING ----------------------
==================================================
[Generated test cases...]

... (continues through all 7 agents)
```

---

## 📜 License

This project is for educational and demonstration purposes.

---

## 👤 Author

**Madhan Mohan Reddy**
- GitHub: [@MadhanMohanReddy2301](https://github.com/MadhanMohanReddy2301)

---

<p align="center">
  Built with ❤️ using Google ADK & Gemini
</p>
