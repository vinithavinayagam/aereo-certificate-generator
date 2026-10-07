# AEREO Certificate Generator - Full Stack

FastAPI + SQLite + SQLAlchemy + ReportLab backend and React/Vite frontend for the AEREO practical assignment.

## Backend
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```
Backend: http://127.0.0.1:8000/docs

## Frontend
Open a second terminal:
```powershell
cd frontend
npm install
npm run dev
```
Frontend: http://localhost:5173

## Flow
React -> POST /jobs -> validation -> SQLite -> background PDF generation -> GET /jobs/{id} polling -> certificate download.

## Design
Bulk jobs are accepted once and processed in the background. Each certificate has its own status so one failure does not stop other recipients. For production scale, the worker can be moved to Celery/RQ + Redis and PDFs to object storage.
