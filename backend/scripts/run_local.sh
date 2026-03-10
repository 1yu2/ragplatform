#!/usr/bin/env bash
set -euo pipefail

export APP_ENV=${APP_ENV:-local}
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
