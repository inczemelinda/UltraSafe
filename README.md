# UltraSafe

UltraSafe is a local insurance workflow application for property quotes, contracts, claim submission, and underwriter review.

The visible product brand is **UltraSafe** by **ZeroRisk**. The Python package is still named `underwright`, so backend commands use `underwright.api.main`.

## Requirements

Install these tools on Windows:

- Python 3.12.0: https://www.python.org/downloads/release/python-3120/
- Node.js LTS: https://nodejs.org/en/download
- Docker Desktop for Windows 64-bit / AMD64: https://www.docker.com/products/docker-desktop/
- Visual Studio Code: https://code.visualstudio.com/
- Git for Windows: https://git-scm.com/download/win

During Python installation, enable `Add python.exe to PATH`.

Verify the tools:

```powershell
python --version
node --version
npm --version
docker --version
docker compose version
git --version
```

## Setup

Open the project:

```powershell
cd "E:\ClujHackathon\ZeroRisk_UltraSafe"
code .
```

Create and activate the Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

If PowerShell blocks activation, run once:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Create environment files:

```powershell
Copy-Item .env.example .env
cd "E:\ClujHackathon\ZeroRisk_UltraSafe\frontend"
Copy-Item .env.example .env
```

Install frontend packages:

```powershell
cd "E:\ClujHackathon\ZeroRisk_UltraSafe\frontend"
npm install
```

## Run

Use three terminals.

Terminal 1 - database:

```powershell
cd "E:\ClujHackathon\ZeroRisk_UltraSafe"
docker-compose up -d --build
docker-compose ps
docker logs underwright-postgres --tail 80
```

Terminal 2 - backend:

```powershell
cd "E:\ClujHackathon\ZeroRisk_UltraSafe"
.\.venv\Scripts\Activate.ps1
python -m uvicorn underwright.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 3 - frontend:

```powershell
cd "E:\ClujHackathon\ZeroRisk_UltraSafe\frontend"
npm run dev
```

Open:

```text
http://127.0.0.1:5173/
```

Backend:

```text
http://127.0.0.1:8000/
```

## Demo Accounts

Client:

```text
ana.popescu@client.com
client123
```

Underwriter:

```text
ioana.polita@ultrasafe.ro
employee123
```

## Stop

Stop frontend/backend with `Ctrl+C` in their terminals.

Stop Docker while keeping database data:

```powershell
cd "E:\ClujHackathon\ZeroRisk_UltraSafe"
docker-compose down
```

Reset the database from scratch:

```powershell
cd "E:\ClujHackathon\ZeroRisk_UltraSafe"
docker-compose down -v --rmi local --remove-orphans
docker-compose up -d --build
```

## Useful Commands

Build frontend:

```powershell
cd "E:\ClujHackathon\ZeroRisk_UltraSafe\frontend"
npm run build
```

Check database logs:

```powershell
cd "E:\ClujHackathon\ZeroRisk_UltraSafe"
docker logs underwright-postgres --tail 80
```

Frontend mode is controlled by `frontend\.env`:

```text
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK_API=false
VITE_BACKEND_PRICING=true
```

Use `VITE_USE_MOCK_API=true` only for a frontend-only demo.
