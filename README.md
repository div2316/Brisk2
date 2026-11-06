# BRISK2 – Cardiovascular Risk Prediction (end-to-end)

Login → **Dashboard** (CVD risk % + what contributes to it) → **Risk analysis** → **Report** (PDF download).
The web app shows no model internals. Research prototype – not a medical diagnosis.

| Part | Technology |
|---|---|
| Frontend | React + Vite + Tailwind, served by nginx (proxies `/api` to the backend) |
| Backend | FastAPI, scikit-learn model, occlusion-based explanation, ReportLab PDF |
| Database | PostgreSQL 16 (users, sessions, assessments, audit) |
| Packaging | Docker Compose (3 containers: `db`, `backend`, `frontend`) |

## Run

```bash
docker compose up --build
```
Open **http://localhost:8080**, create an account, sign in, and run an assessment.
The first build takes a few minutes because the model is trained inside the backend image (about 30 s of that).
Optional: copy `.env.example` to `.env` to change the port or database password.

Stop with `docker compose down` (add `-v` to also delete the database).

## Routes

`/` welcome · `/signin` · `/signup` · `/forgot-password` · `/reset-password` ·
`/dashboard` · `/assessment` · `/risk-analysis` · `/report` (these four need login; unknown URLs go to the dashboard).

## About the default model

The default training file is `data/cardiovascular_disease_dataset.csv` (1,000 patients, 12 clinical inputs: chest pain type,
exercise angina, resting blood pressure, serum cholesterol, fasting blood sugar, resting ECG, maximum heart rate, ST depression,
ST slope, number of major vessels, age and sex). The assessment form is generated from exactly these inputs, with the clinical
groups first and age/sex last. The model learns the weight of each input from the data; nothing is hand-weighted.

Two files are kept for reference: `cardio_clean.csv` (public cardio_train data, 11 inputs, profile `cardio`) and the Indian
10,000-record file, which carries almost no signal (AUC about 0.5), so it is not used.

### Use a different dataset

Edit the `TRAIN_*` build arguments in `backend/Dockerfile` (or pass `--build-arg`), put the CSV in `data/`, then rebuild:

| Variable | Meaning |
|---|---|
| `TRAIN_CSV` | path inside the image, e.g. `/srv/data/mydata.csv` |
| `TRAIN_TARGET` | name of the 0/1 outcome column |
| `TRAIN_ID_COLUMNS` | columns to ignore (IDs) |
| `TRAIN_DROP_COLUMNS` | other columns to leave out |
| `TRAIN_PROFILE` | `heart13`, `cardio`, `india10k`, or `custom` (automatic labels) |

The assessment form is generated from the trained model, so it adapts to the new columns.
Labels, units and groups for a new dataset can be added in `backend/app/profiles.py`.

## Notes

* **Password reset:** there is no e-mail service. The reset link is written to the backend log
  (`docker compose logs backend`).
* **Data:** assessments are stored per account in PostgreSQL; users can delete them from the Report page.
* **Local development (no Docker):** `cd backend && pip install -r requirements.txt`, train with
  `python -m app.cli train --csv ../data/cardio_clean.csv --target Cardio_Disease --profile cardio --threshold-strategy youden`,
  run `uvicorn app.main:get_app --factory --port 8000`; then `cd frontend && npm install && VITE_API_URL=http://localhost:8000 npm run dev`.
  Without `DATABASE_URL` the backend uses a local SQLite file.
* **Tests:** `cd backend && python -m unittest discover -s tests -t .`
