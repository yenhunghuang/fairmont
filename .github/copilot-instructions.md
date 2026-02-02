```markdown
# Copilot Instructions for Fairmont Furniture Quotation System

## Tech Stack & Architecture
- **Backend**: Python 3.11+, FastAPI, Pydantic, Uvicorn
- **Frontend**: Streamlit (Python)
- **AI Integration**: Google Gemini 3 Flash Preview
- **PDF/Image Processing**: PyMuPDF (fitz)
- **Config System**: YAML-based "Skills" for vendor/output/merge rules
- **Storage**: In-memory cache (1hr TTL, no DB)
- **Containerization**: Docker, docker-compose

## Key Directories & Files
- `backend/`: FastAPI backend
  - `app/api/routes/`: API endpoints
  - `app/services/`: Business logic (PDF parsing, merging, Excel generation)
  - `app/models/`: Data models
- `frontend/`: Streamlit frontend (`app.py`)
- `skills/`: YAML config for vendors, output formats, merge rules
- `specs/`: Functional specs, data models, OpenAPI contracts
- `docs/`: Architecture, deployment, quick reference
- `CLAUDE.md`: Developer guide (detailed conventions, standards)
- `README.md`: Project overview, setup, usage

## Build & Test Commands

### Backend
```bash
cd backend
pip install -r requirements.txt
pip install -e ".[dev]"
uvicorn app.main:app --reload         # Start dev server
pytest                                # Run all tests
pytest -v --cov-report=term-missing   # Coverage report
ruff check . --fix && black .         # Lint & format
```

### Frontend
```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

### Docker (Full Stack)
```bash
docker-compose up -d --build          # Start frontend + backend
docker-compose logs -f backend        # Backend logs
docker-compose logs -f frontend       # Frontend logs
docker-compose down                   # Stop all
```

### Production Backend Only
```bash
docker-compose -f docker-compose.prod.yml up -d --build
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml down
```

## Project Conventions
- **Test-first**: Write tests before implementation; target ≥80% coverage
- **Code Style**: PEP8, Black (line length 100), Ruff
- **Languages**: Docs/UI in Traditional Chinese; code in English
- **Config**: `.env` required (`GEMINI_API_KEY`, `API_KEY`)
- **No DB**: All state in memory (1hr TTL)
- **PDF Limit**: Max 5 files, 50MB each, 200 pages per run

## API Usage
- Main endpoint: `POST /api/v1/process` (multipart PDF upload, returns parsed items)
- SSE endpoint: `POST /api/v1/process/stream` (real-time progress)
- Swagger UI: `http://localhost:8000/docs` (API_KEY required)

## Reference
- See `CLAUDE.md` for detailed architecture, standards, and key file explanations.
- See `README.md` for quickstart, deployment, and sample files.
```