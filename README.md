# HospitalShield AI

Climate-Resilient Hospital Digital Twin (Hackathon FUSION 2026, problem HC-03 Mayo Clinic).

## Architecture
```
[Frontend: React + TS + Vite] <--- API ---> [Backend: FastAPI + Python]
```

## Running Locally

1. **Backend:**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.lock.txt
uvicorn app.main:app --reload
```

2. **Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Docker
```bash
docker-compose up --build
```

## API
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/health` | Healthcheck |
| GET | `/api/v1/hospital/baseline` | Get baseline hospital stats |
| GET | `/api/v1/scenarios` | Get predefined scenarios |
| POST | `/api/v1/simulations` | Run a simulation |
| POST | `/api/v1/comparisons` | Compare baseline vs treatment |
| POST | `/api/v1/plans` | Generate action plan |
| POST | `/api/v1/ensembles` | Run ensemble (3 seeds, P10/P50/P90) |
| POST | `/api/v1/sensitivity` | Sensitivity / tornado analysis |
| GET | `/api/v1/simulations/{run_id}` | Retrieve run from history |
| GET | `/api/v1/simulations/{run_id}/report` | Export markdown report |

## Limitations
- **Data:** All hospital values are SYNTHETIC. Heat-to-demand multipliers are SCENARIO ASSUMPTIONS, not predictions.
- **Constraints:** Power is an abstract operational constraint; no claims about real generator, ICU, or life-support safety are made.
- **Usage:** Outputs are for planning exploration only, NOT for clinical, engineering, or live operational decisions. Real-world use requires validated local data and expert review.
