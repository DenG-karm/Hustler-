set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

default:
    Write-Host "Available commands: gen, check"

gen:
    python tools/generate_contracts.py

check:
    uv run ruff check services/core
    uv run mypy services/core
    pnpm --filter @hustler/desktop run lint
    cargo clippy --workspace -- -D warnings
