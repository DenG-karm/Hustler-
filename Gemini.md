# HUSTLER CORE — STRICT ENGINEERING DIRECTIVES

## 1. TOKEN & OUTPUT DISCIPLINE
- NO CHATTER: Never greet, apologize, summarize, or explain what you are about to do.
- DIFF & PROOF ONLY: Output only the required code changes and the raw terminal verification output.
- SURGICAL EDITS: Modify ONLY the files explicitly named in the user prompt. Never scan the whole repo unless asked.
- ZERO NEW PACKAGES: Do not run `npm install`, `pnpm add`, `uv add`, or `cargo add`. Use stdlib and existing workspace packages only.

## 2. ARCHITECTURE & DATABASE CONTRACTS (DO NOT VIOLATE)
- SQLite Engine (`services/core/hustler/db/engine.py`):
  - READS: Must use `reader = await self.db.get_reader()` inside `try / finally: await reader.close()`.
  - WRITES: Must use `await self.db.execute_write(sql, params)` or `executemany_write`.
  - QUERIES: Zero N+1 queries. Use `LEFT JOIN ... GROUP BY` for aggregations. No correlated subqueries in loops.
- FastAPI (`services/core/hustler/api/`):
  - All protected routes require `Depends(verify_token)`.
  - Zero `# type: ignore`, zero `Any`. Strict Pydantic v2 / `@dataclass` contracts.
- Desktop IPC & Store (`apps/desktop/src/`):
  - Zero `any`, zero `@ts-ignore`, zero index signatures (`[key: string]: unknown`).
  - Zero hardcoded/mock data in `ipc.ts` or Zustand slices.
  - Every new API route must be whitelisted in both `src-tauri/src/lib.rs` (`is_route_allowed`) and `src/lib/securityGuard.ts`.

## 3. MANDATORY COMPILER GATES (RUN BEFORE FINISHING)
- Backend change: `uv run ruff check services/ --select C901 --config "lint.mccabe.max-complexity = 10" && uv run mypy --strict services/core/hustler/`
- Frontend change: `pnpm --filter desktop exec tsc -b`
- Budget limit: Raw JS bundle <= 500.0 KB, Gzip <= 150.0 KB (`uv run python tools/bench/run_bench.py`).