# Vimani Orchestrator POC (scaffold)

FastAPI backend scaffold for the Vimani POC. Includes placeholder modules for the orchestrator, planner, executor, and archivist. Endpoints are stubbed so imports resolve.

## Running locally

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
 --port 8000
uvicorn app.main:app --reload --port 8000 --app-dir backend
        

python backend\scratch_test_orchestrator.py

```
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload