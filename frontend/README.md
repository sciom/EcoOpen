# EcoOpen LLM Frontend

Minimal Vue 3 + Vite frontend to interact with the FastAPI backend.

## Prerequisites
- Node.js 18+

## Setup
```bash
cd frontend
npm install
```

## Run
```bash
npm run dev
```
Open http://localhost:5173

## Configure API base URL (optional)
Create `.env` in `frontend/` with:
```
VITE_API_BASE=http://localhost:8000
```
Defaults to `http://localhost:8000` if not set.

You can also change the API base in the app under Settings → API Configuration. That override is saved in localStorage and takes precedence over `VITE_API_BASE`.

## Authentication
- Use the Login tab to sign in or register; after registering, the app auto‑logs in.
- Password rules: at least 8 characters and include letters and numbers; registration requires confirming the password.
- Auth state is shown in the header chip; click it to open the menu with Settings and Logout.
- Single analyze, batch analyze, job status, and CSV export all require you to be logged in.
- If your token expires or becomes invalid, the app automatically logs you out and sends you to the Login tab. Tokens are stored in localStorage and sent as `Authorization: Bearer <token>`. 
