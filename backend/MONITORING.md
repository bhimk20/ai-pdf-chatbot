# Backend Monitoring

This file explains the monitoring work added to the FastAPI backend in simple terms.

## What Was Added

Three things were added:

1. Structured logs
2. Metrics
3. A debug status endpoint

These are all backend-only changes.

## Why This Exists

When something breaks, we want fast answers to questions like:

- Is the backend alive?
- Is Supabase reachable?
- Is chat failing more often than usual?
- Are requests slow?
- Is Gemini failing?

Before this, the backend mostly just returned errors.

Now it also records useful signals.

## Files Added Or Changed

- `backend/app/monitoring.py`
- `backend/app/main.py`
- `backend/app/retrieval.py`
- `backend/pyproject.toml`

## 1. Structured Logs

Location:

- `backend/app/monitoring.py`
- used from `backend/app/main.py`
- used from `backend/app/retrieval.py`

What it does:

- writes backend events as JSON logs
- adds a request id to each HTTP request
- logs request path, status code, and duration
- logs chat and ingest success/failure
- logs Gemini and Supabase call failures

Why this helps:

- logs become easier to search
- each request has a trace id
- easier to see what failed without digging through raw stack traces

Example log shape:

```json
{
  "event": "request_completed",
  "request_id": "1234",
  "method": "POST",
  "path": "/chat/stream",
  "status": 200,
  "duration_ms": 145.23
}
```

## 2. Metrics

Location:

- `backend/app/monitoring.py`
- exposed by `backend/app/main.py`

Endpoint:

- `GET /metrics`

What it does:

- exposes numeric counters and timings in Prometheus format

You do not need Prometheus right away.
You can still open the endpoint in the browser or use `curl`.

Example:

```bash
curl http://localhost:8000/metrics
```

Some metrics added:

- total HTTP requests
- HTTP request latency
- total ingest requests
- total document chunks ingested
- total chat requests
- active chat streams
- Gemini and Supabase external call counts
- Gemini and Supabase external call latency

Simple meaning:

- `Counter` = keeps going up
- `Gauge` = current value goes up/down
- `Histogram` = tracks timing/size distributions

## 3. Debug Status Endpoint

Endpoint:

- `GET /debug/status`

What it checks:

- whether key env vars are present
- whether Supabase `documents` table is reachable
- whether Supabase `match_documents` RPC is callable

What it does not do:

- it does not return secrets
- it does not fully test a live Gemini generation call

Example:

```bash
curl http://localhost:8000/debug/status
```

Example response shape:

```json
{
  "status": "ok",
  "env": {
    "google_api_key_present": true,
    "supabase_url_present": true,
    "supabase_service_role_key_present": true
  },
  "checks": {
    "documents_table_accessible": true,
    "match_documents_rpc_accessible": true
  }
}
```

If status is `degraded`, something important is misconfigured or unreachable.

## Where Monitoring Hooks Run

### In `main.py`

The backend now:

- sets up logging on startup
- tracks every HTTP request
- exposes `/metrics`
- exposes `/debug/status`
- records ingest success/failure
- records chat success/failure

### In `retrieval.py`

The backend now measures:

- Supabase document insert
- Gemini route decision call
- Gemini embed call
- Supabase `match_documents` RPC
- Gemini direct answer call
- Gemini streamed answer call

This is the part that tells us whether failures are coming from:

- Supabase
- Gemini
- the app itself

## Dependency Added

Added to backend dependencies:

- `prometheus-client`

Why:

- it generates the `/metrics` output

## How To Use This Locally

Start backend as usual:

```bash
cd /Users/bhimk/Personal_Repos/ai-pdf-chatbot/backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then check:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/debug/status
curl http://localhost:8000/metrics
```

## What To Look At First

If backend seems broken:

1. `GET /health`
2. `GET /debug/status`
3. backend terminal logs
4. `GET /metrics`

Good rule:

- `/health` says process up
- `/debug/status` says config + Supabase path up
- logs say what failed
- `/metrics` says whether failures/latency are trending

## Very Practical Reading Guide

If you are new to this, treat the tools like this:

- `health` = "is server running?"
- `debug/status` = "is config and Supabase setup usable?"
- logs = "what just failed?"
- metrics = "is this failing a lot, slowly, or continuously?"

## Limits Of Current Setup

This is phase 3 now.

Added in phase 2:

- Prometheus server
- Grafana dashboard
- Blackbox health probes
- basic alert rules

Added in phase 3:

- Alertmanager
- local email delivery for alerts
- Mailpit inbox for viewing alerts in browser

Still not added:

- Sentry
- frontend app-level instrumentation
- deep Gemini live probe endpoint
- Slack / external email integration

So right now this is strong local monitoring, with dashboards, rules, and local alert delivery, but not full production alert routing.

## Safe To Know

This monitoring should not expose secrets directly.

Still, do not make debug endpoints public on an open production server without thinking about access rules first.

## If You Want Next

Good next upgrades:

1. add a protected Gemini live test endpoint
2. add Slack / external email delivery
3. add frontend app-level metrics
4. add frontend error tracking
5. add production deployment config

## Phase 2 Stack

Phase 2 adds a local monitoring stack with three services:

1. Prometheus
2. Grafana
3. Blackbox Exporter

Files:

- `docker-compose.monitoring.yml`
- `monitoring/prometheus/prometheus.yml`
- `monitoring/prometheus/alert_rules.yml`
- `monitoring/blackbox/config.yml`
- `monitoring/grafana/provisioning/...`
- `monitoring/grafana/dashboards/ai-pdf-chatbot-overview.json`

## Phase 3 Stack

Phase 3 adds two more services:

1. Alertmanager
2. Mailpit

Files:

- `monitoring/alertmanager/alertmanager.yml`
- `docker-compose.monitoring.yml`

This means alerts are no longer only evaluated.
They are now routed to a local inbox you can open in the browser.

## What Each Service Does

### Prometheus

Prometheus stores time-series metrics.

In this project it does two jobs:

- scrapes backend metrics from `http://host.docker.internal:8000/metrics`
- evaluates alert rules

Open it at:

- `http://localhost:9090`

### Grafana

Grafana visualizes the data from Prometheus.

In this project it loads a ready-made dashboard automatically.

Open it at:

- `http://localhost:3001`

Default login:

- username: `admin`
- password: `admin`

### Blackbox Exporter

Blackbox Exporter checks whether URLs respond correctly.

In this project it probes:

- backend health: `/health`
- backend debug status: `/debug/status`
- frontend root page: `/`

This is different from app metrics.

Think:

- app metrics = "how is the app behaving internally?"
- blackbox probe = "does the URL respond from the outside?"

### Alertmanager

Alertmanager receives alerts from Prometheus and decides where to send them.

In this project it sends alerts to a local email inbox.

Open it at:

- `http://localhost:9093`

### Mailpit

Mailpit is a local fake email inbox for development.

It accepts alert emails and shows them in a browser UI.

Open it at:

- `http://localhost:8025`

This means you can test email alert delivery without using Gmail, SendGrid, or any real email provider.

## What The Dashboard Shows

The Grafana dashboard includes:

- backend health status
- frontend health status
- request rate by backend path
- request latency p95
- backend 5xx rate
- Gemini and Supabase external call rate
- Gemini and Supabase external call latency p95
- ingest success/error rate
- chat success/error rate
- active chat streams
- probe duration

## Alert Rules Added

Prometheus now evaluates basic rules for:

- backend health endpoint down
- frontend down
- high backend 5xx rate
- chat failures detected
- Supabase failures detected
- Gemini failures detected

Important:

These rules are now routed through Alertmanager.
For local development they are delivered to Mailpit.

So phase 3 gives you:

- Prometheus evaluates rules
- Alertmanager routes alerts
- Mailpit displays alert emails

## How To Start Phase 2

First make sure the app itself is running:

- frontend on `http://localhost:3000`
- backend on `http://localhost:8000`

Then start monitoring:

```bash
cd /Users/bhimk/Personal_Repos/ai-pdf-chatbot
docker compose -f docker-compose.monitoring.yml up -d
```

Then open:

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`
- Alertmanager: `http://localhost:9093`
- Mailpit inbox: `http://localhost:8025`

To stop:

```bash
docker compose -f docker-compose.monitoring.yml down
```

## Important Local Assumption

The monitoring containers use:

- `host.docker.internal:8000`
- `host.docker.internal:3000`

That means:

- backend and frontend are expected to run on your host machine
- Docker containers reach them through Docker Desktop host networking helpers

This works well on macOS Docker Desktop, which matches your setup.

If you later move the app into containers too, the Prometheus targets should be updated.

## Quick Verification

After everything is running:

1. open `http://localhost:3001`
2. log into Grafana
3. open dashboard `AI PDF Chatbot Overview`
4. send a few chats / upload a PDF
5. watch graphs move

If the dashboard is empty:

1. check backend is running on port `8000`
2. check frontend is running on port `3000`
3. open `http://localhost:9090/targets`
4. confirm targets are `UP`

## How To See Alert Delivery

Open:

- `http://localhost:8025`

That inbox will show alert emails sent by Alertmanager.

Open:

- `http://localhost:9093`

That UI shows:

- active alerts
- silences
- receivers

## Easy Way To Trigger A Test Alert

Stop the backend for a minute.

Example:

1. stop backend process
2. wait about 1 minute
3. Prometheus rule `BackendHealthEndpointDown` should fire
4. Alertmanager should receive it
5. Mailpit should show the alert email

Then restart backend.

After recovery, you should also see a resolved alert email.

## Practical Reading Guide For Phase 2

If something feels wrong, check in this order:

1. Grafana status panels
2. Prometheus targets page
3. `/debug/status`
4. backend logs
5. detailed Prometheus queries
