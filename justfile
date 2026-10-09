set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

default:
    Write-Host "Available commands: gen, gen-check, lint, typecheck, test, test-gate, check"

gen:
    uv run python tools/generate_contracts.py

gen-check: gen
    git diff --exit-code packages/contracts

lint:
    uv run ruff check .

typecheck:
    uv run mypy

test:
    uv run pytest

test-gate:
    uv run python tools/ci/check_tests.py --gate

lint-web:
    pnpm --filter @hustler/desktop run lint

lint-rust:
    cargo clippy --workspace -- -D warnings

check: lint typecheck test test-gate lint-web lint-rust
