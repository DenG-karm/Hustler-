# HUSTLER FILE & CONTRACT MAP (READ THIS INSTEAD OF SCANNING REPO)

## Backend (Python 3.12 / FastAPI / SQLite WAL)
- `services/core/hustler/main.py`: App lifespan, `app.state.db`, `app.state.channel_repo`, router registration.
- `services/core/hustler/db/engine.py`: `Database` class (`get_reader()`, `execute_write()`, `executemany_write()`).
- `services/core/hustler/storage/channels.py`: `ChannelRepository(db)` — `init_table` (`channels` & `channel_templates`), `create`, `list_all_with_metrics`, `get_metrics`, `delete`, `record_research`, and template CRUD (`create_template`, `list_templates`, `get_template`, `update_template`, `delete_template`).
- `services/core/hustler/storage/scripts.py`: `ScriptRepository(db)` — `save_script`, `get_script`, `channel_id` relational linking.
- `services/core/hustler/services/channel_stats.py`: `fetch_channel_live_stats(url, refresh)` & `infer_channel_niche_query` — yt-dlp/HTML parser (`channel_total_videos`, `channel_total_views`, real published date maps for `/videos` and `/shorts`), automatic live niche benchmark search, 30-min in-memory cache.
- `services/core/hustler/services/channel_analytics.py`: `compute_channel_analytics(videos, shorts)` — Pandas/NumPy rolling mean, trend slope, format distribution, viral multiplier (`outliers`), and view tier histogram (`view_tiers`).
- `services/core/hustler/discovery/service.py`: `run_ytdlp_topic_discovery` (`_search_youtube_ytdlp_sync`) & `fallback_discovery` — live yt-dlp YouTube topic search with SQLite cache fallback.
- `services/core/hustler/api/routes/channels.py`: `/api/v1/channels` (GET, POST), `/{id}` (GET, DELETE), `/{id}/live-stats` (GET), `/{id}/templates` (GET, POST), `/{id}/templates/{tpl_id}/update` (POST), `/{id}/templates/{tpl_id}/analyze` (POST), `/{id}/templates/{tpl_id}/render` (POST), `/{id}/templates/{tpl_id}` (DELETE).
- `services/core/hustler/api/routes/discovery.py`: `/api/v1/discovery/run` (accepts `channel_id`, uses live yt-dlp search when `YOUTUBE_API_KEY` is absent).
- `services/core/hustler/api/routes/pipeline.py`: `/api/v1/pipeline/script` (accepts `channel_id`), `/api/v1/pipeline/chat` & `/api/v1/assistant/chat` (Hustler AI assistant).

## Desktop Shell & Security Proxy (Tauri Rust)
- `apps/desktop/src-tauri/src/lib.rs`: `is_route_allowed(route)` IPC proxy firewall, sidecar lifecycle via Windows Job Object.
- `apps/desktop/src/lib/securityGuard.ts`: Zero-Network CSP trap, `ALLOWED_IPC_COMMANDS`, `ALLOWED_PROXY_ROUTE_PREFIXES`.
- `apps/desktop/src/lib/ipc.ts`: `tauriIpcClient` (`listChannels`, `createChannel`, `getChannelDetail`, `deleteChannel`, `proxyRequest`).

## Frontend State & UI Studio (React + Zustand)
- `apps/desktop/src/store/flowTypes.ts`: Strict TS models (`ChannelItem`, `ChannelCreatePayload`, `ChannelLiveStats`, `DiscoveryItem`).
- `apps/desktop/src/store/flowStore.ts`: Combined Zustand store (`channelSlice`, `discoverySlice`, `scriptSlice`, `renderSlice`).
- `apps/desktop/src/store/slices/channelSlice.ts`: Channel state (`channels`, `activeChannelId`, `flowChannelId`) & `selectIdeaFromChannelAndStartFlow()`.
- `apps/desktop/src/components/channels/ChannelsScreen.tsx`: 4-Tab Studio UI (Left: Profile & AI Persona; Right: Benchmarks, Growth Trends, Paginated/Searchable/Outlier Archive Tables, Shorts Video Templates Vitrini with Hover Cover Player & Classic Template Editor Workspace [Left: Sample Reference Video, Center: Active 9:16 Template + Overlay & Subtitle Canvas, Bottom 1: Photo/Video Timeline Layer Slots, Bottom 2: AI Subtitle Analyzer & ElevenLabs Voice/Reels Renderer]).
- `apps/desktop/src/components/channels/globalPrototypes.ts`: Real-data transformer mapping live `niche_benchmarks`, `videos`/`shorts`, and `channelIdeas` to prototype cards (zero hardcoded/mock items).
- `apps/desktop/src/components/assistant/HustlerAiWidget.tsx`: Multi-thread persistent AI chat panel with fullscreen expansion (`isExpanded`) and mouse drag resize.
- `apps/desktop/src/components/channels/channelMetadata.ts`: Channel niche profiles, system prompts, audience tone mappings, and `deriveFallbackAnalytics` (with `outliers` & `view_tiers`).
- `apps/desktop/src/components/channels/charts/`: `ChannelTrendChart.tsx` (SVG line/slope), `ChannelDistributionChart.tsx` (SVG donut, Viral Multiplier `Nx` bars, and View Tier histogram).

## CI/CD Gates & Quality Budgets
- `tools/bench/run_bench.py`: K-804 Budget Gate (Frontend JS <= 550KB raw / <= 150KB gzip, SQLite queue, AST compilation).
- `tools/security/static_audit.py`: K-805 Security Gate (CSP Level 3, IPC allowlist matching, `127.0.0.1` loopback isolation).
