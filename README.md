# 🛡️ IT Ops Copilot

An AI-assisted IT Operations (Incident Management) platform. IT Ops Copilot lets IT teams **create, track, update, and manage incident tickets** through a modern Jira-style dashboard, backed by a REST API and a **vector database (ChromaDB)** that enables semantic search for similar past incidents — the foundation for an AI copilot that can suggest resolutions from historical ticket data.

---

## 📖 Project Description

In real IT operations, teams handle hundreds of incidents (server outages, database failures, network issues, security alerts). IT Ops Copilot centralizes that workflow:

1. **Ticket Management API (FastAPI)** — A clean REST API to create, list, filter, update, and delete incident tickets. Tickets are auto-assigned human-friendly incident IDs like `INC-1001`, and business rules are enforced (e.g., a ticket **cannot** be resolved without resolution notes).
2. **Relational Storage (SQLite + SQLAlchemy)** — Ticket data is persisted locally in `it_ops.db` via SQLAlchemy ORM — no external database server needed.
3. **Vector Search (ChromaDB)** — Every ticket is indexed into the `it_incidents` Chroma collection (title, description, category, priority, status, server, resolution notes). This powers *semantic similarity search*: when a new incident comes in, the system can retrieve historically similar tickets and their resolutions, which is the core of the "copilot" experience.
4. **Streamlit Dashboard (Frontend)** — A polished, Atlassian/Jira-inspired UI (blue/white theme) with:
   - 📊 **Dashboard** — incident metrics, priority/status/category breakdowns and charts
   - 🎫 **All Tickets** — browse and filter every ticket
   - ➕ **New Ticket** — create incidents via a form
   - ✏️ **Update Ticket** — change status, priority, assignment, add resolution notes
   - ✦ **AI Chat Drawer** — a side chat panel ("IT Ops Copilot AI") ready to be wired to the agent endpoint

### Project Status

- ✅ Complete: Ticket CRUD API, SQLite persistence, ChromaDB indexing + similarity search, full dashboard UI
- 🚧 In progress: Connecting the chat panel to a live AI/agent backend for automated replies

---

## 🏗️ Project Structure

```
it-ops-copilot/
├── frontend/
│   ├── app.py                  # Streamlit dashboard UI (main app)
│   └── components/
│       └── chat_panel.py       # AI chat drawer component
├── src/
│   ├── main.py                 # FastAPI app entrypoint (lifespan creates DB tables)
│   ├── api/
│   │   └── tickets.py          # Ticket CRUD endpoints (/api/tickets)
│   ├── models/
│   │   └── ticket.py           # SQLAlchemy Ticket model
│   ├── database/
│   │   └── db.py               # SQLite engine/session (it_ops.db)
│   └── vector_store/
│       └── chroma_db.py        # ChromaDB indexing + similar-ticket search
├── data/
│   ├── chroma_db/              # ChromaDB persistent storage
│   ├── raw/                    # Raw data files
│   └── processed/              # Processed data files
├── notebooks/                  # Jupyter notebooks for experimentation
├── tests/                      # Test scripts (e.g., ChromaDB connectivity)
├── .streamlit/config.toml      # Streamlit theme config
├── requirements.txt            # Python dependencies
├── it_ops.db                   # SQLite database (auto-created)
└── README.md
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python, FastAPI, Pydantic |
| Database | SQLite + SQLAlchemy ORM |
| Vector Store | ChromaDB (persistent client) |
| Frontend | Streamlit, Pandas, Requests |
| Styling / Charts | Custom CSS (Atlassian-themed), Altair/Matplotlib |
| Server | Uvicorn |

---

## ⚙️ Requirements

- **Python 3.12+** (the project venv uses Python 3.14)
- **pip** (comes with Python)
- No external database or vector-store server required — SQLite and ChromaDB run locally as files.

### Key Python Dependencies (`requirements.txt`)

| Package | Purpose |
|---------|---------|
| `fastapi`, `uvicorn` | REST API server |
| `sqlalchemy` | ORM / SQLite persistence |
| `pydantic` | Request validation |
| `streamlit` | Dashboard frontend |
| `chromadb` | Vector database for similar-incident search |
| `pandas`, `numpy` | Data handling |
| `requests`, `httpx` | Frontend ↔ API communication |
| `scikit-learn`, `scipy` | ML / similarity utilities |
| `matplotlib`, `seaborn`, `altair` | Charts |
| `jupyter` | Notebooks for experimentation |

---

## 🚀 Steps to Run the Project

### 1. Clone the repository

```bash
git clone https://github.com/Deekshakhathi/it-ops-copilot.git
cd it-ops-copilot
```

### 2. Create & activate a virtual environment

```bash
# create the venv
python -m venv .venv

# activate it
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows (PowerShell: .venv\Scripts\Activate.ps1)
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the FastAPI backend

```bash
# from the project root
uvicorn src.main:app --reload
```

- API is now running at: **http://localhost:8000**
- Interactive Swagger docs: **http://localhost:8000/docs**
- On startup, the SQLite database (`it_ops.db`) and the `tickets` table are created automatically.

> ℹ️ In a fresh setup, if Python can't find the `src` package when running commands like `python test_chroma.py`, set the path: `export PYTHONPATH=.` (Linux/macOS) or `$env:PYTHONPATH="."` (Windows PowerShell).

### 5. Start the Streamlit frontend (new terminal, venv active)

```bash
streamlit run frontend/app.py
```

- Dashboard opens at: **http://localhost:8501**

> ℹ️ The frontend talks to the API at `http://localhost:8000/api/tickets` (configured in `frontend/app.py`), so keep the backend running.

---

## 🌱 Generate Dummy Data (Seeding)

To populate the database with realistic test incidents, run the seeding script (backend and frontend do NOT need to be running):

```bash
python -m src.ingestion.seed_tickets
```

This creates **~100 fictional IT incident tickets** (database failures, website downtime, network issues, security alerts, backup failures, deployment problems, etc.) directly through the existing SQLAlchemy model, then indexes every ticket into the `it_incidents` ChromaDB collection.

It prints a summary with the number of tickets created, totals in SQLite, counts by status and priority, ChromaDB indexing counts, and any errors.

**Safety behavior:**
- ✅ **Idempotent** — already-seeded titles are skipped, so re-running never creates duplicates or resets data.
- ✅ **Safe on existing data** — user-created tickets are preserved; the script never drops tables or resets the database.
- ✅ **No duplicate vectors** — ChromaDB entries use upsert keyed on the stable `ticket_id`.
- ✅ Realistic status flow — only `Resolved`/`Closed` tickets carry resolution notes.

### Verify the dummy data

```bash
# ChromaDB connectivity + collection count
python test_chroma.py

# Inspect SQLite (or: python -c "..." if sqlite3 CLI isn't installed)
sqlite3 it_ops.db "SELECT COUNT(*), COUNT(DISTINCT ticket_id) FROM tickets;"
sqlite3 it_ops.db "SELECT ticket_id, status, priority, title FROM tickets LIMIT 10;"
```

Try a similarity search (mirrors `src/vector_store/chroma_db.py`):

```python
python - <<'EOF'
from src.vector_store.chroma_db import search_similar_tickets
results = search_similar_tickets("database connection timeout", limit=3)
print(results["ids"][0])
EOF
```

Expected: the database-connection-failure tickets (e.g., `INC-1001`–`INC-1004`) rank at the top.

---

## 🔌 API Endpoints

Base URL: `http://localhost:8000`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `POST` | `/api/tickets/` | Create a ticket (auto ID like `INC-1001`, status `Open`) |
| `GET` | `/api/tickets/` | List tickets (optional filters: `status`, `priority`, `category`) |
| `GET` | `/api/tickets/{ticket_id}` | Get a single ticket |
| `PATCH` | `/api/tickets/{ticket_id}` | Update ticket fields |
| `DELETE` | `/api/tickets/{ticket_id}` | Delete a ticket |

### Example: Create a ticket

```bash
curl -X POST http://localhost:8000/api/tickets/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Server down in prod",
    "description": "app-server-02 stopped responding to health checks",
    "category": "Infrastructure",
    "priority": "Critical",
    "affected_server": "app-server-02"
  }'
```

### Example: Filter open tickets

```bash
curl "http://localhost:8000/api/tickets/?status=Open&priority=Critical"
```

**Validation rules:**
- `category`: one of `Infrastructure, Application, Database, Network, Security, Performance, Other`
- `priority`: one of `Low, Medium, High, Critical`
- `status` (on update): one of `Open, In Progress, Resolved, Closed`
- Resolving a ticket **requires** `resolution_notes`

---

## 🧪 Verify the Setup

Test the ChromaDB connection:

```bash
python test_chroma.py
```

Expected output:

```
ChromaDB connected successfully!
Collection: it_incidents
Existing indexed tickets: <count>
```

---

## 🛣️ Roadmap

- [ ] Connect the AI chat drawer to a live LLM/agent backend
- [ ] Auto-categorization & priority prediction from incident description
- [ ] "Similar past incidents" suggestions using ChromaDB search in the UI
- [ ] Slack/Teams webhook integrations
- [ ] User authentication and role-based access
