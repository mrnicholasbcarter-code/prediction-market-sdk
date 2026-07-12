#!/bin/bash
echo ">>> Running Live Integration Tests (NO MOCKS) <<<"
source .venv/bin/activate
pytest tests/integration/ -v
