// Hustler Desktop Shell — K-006 + K-010
//
// K-006: Python sidecar başlatma
//   - port=0 trick ile dinamik port
//   - token/port env ile verilir, hazır olma /health ile yoklanır
//   - Windows Job Object ile yetim süreç önlenir
//
// K-010: IPC Köprüsü
//   - Frontend hiçbir zaman doğrudan HTTP çağrısı yapmaz
//   - Rust, Bearer token'ı ekleyerek 127.0.0.1'e proxy eder
//   - İzin listesi dışı rotalar reddedilir

use std::{
    io::{Read, Write},
    net::{TcpListener, TcpStream},
    process::{Child, Command, Stdio},
    time::Duration,
};

use anyhow::Context;
use serde::{Deserialize, Serialize};
use tauri::{Emitter, Manager, State};

// ---------------------------------------------------------------------------
// Sidecar durumu — Tauri State'e eklenir, frontend'e asla açılmaz
// ---------------------------------------------------------------------------
pub struct SidecarState {
    pub port: u16,
    pub token: String,
    pub client: reqwest::Client,
}

// ---------------------------------------------------------------------------
// İzin listesi — K-010 ve K-702 Akış Rotaları
// ---------------------------------------------------------------------------
fn is_route_allowed(route: &str) -> bool {
    let exact_matches = [
        "/health",
        "/events",
        "/api/v1/system/shutdown",
        "/api/v1/discovery/run",
        "/api/v1/jobs",
        "/api/v1/channels",
        "/api/v1/pipeline/script",
        "/api/v1/pipeline/script/save",
        "/api/v1/pipeline/audio",
        "/api/v1/pipeline/assets",
        "/api/v1/pipeline/preview",
        "/api/v1/pipeline/render",
        "/api/v1/pipeline/session/active",
        "/api/v1/pipeline/session/save",
        "/api/v1/pipeline/chat",
        "/api/v1/assistant/chat",
        "/api/v1/diagnostics/export",
    ];
    if exact_matches.contains(&route) {
        return true;
    }
    if route.starts_with("/api/v1/jobs/")
        || route.starts_with("/api/v1/channels/")
        || route.starts_with("/api/v1/diagnostics/export")
    {
        return true;
    }
    false
}

// ---------------------------------------------------------------------------
// IPC proxy komutu (K-010 ve K-702)
// ---------------------------------------------------------------------------
#[derive(Debug, Serialize, Deserialize)]
pub struct ProxyRequest {
    pub method: String,
    pub route: String,
    pub body: Option<serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ProxyResponse {
    pub status: u16,
    pub body: serde_json::Value,
}

pub mod ipc {
    use super::*;

    pub async fn execute_sidecar_call(
        state: &SidecarState,
        method: &str,
        route: &str,
        body: Option<serde_json::Value>,
    ) -> Result<ProxyResponse, String> {
        if !is_route_allowed(route) {
            return Err(format!("Route '{}' is not in the allowlist", route));
        }

        let url = format!("http://127.0.0.1:{}{}", state.port, route);

        let mut builder = match method.to_uppercase().as_str() {
            "GET" => state.client.get(&url),
            "POST" => state.client.post(&url),
            "DELETE" => state.client.delete(&url),
            m => return Err(format!("Unsupported method: {m}")),
        }
        .header("Authorization", format!("Bearer {}", state.token))
        .timeout(Duration::from_secs(30));

        if let Some(ref b) = body {
            builder = builder.json(b);
        }

        let resp = builder
            .send()
            .await
            .map_err(|e| format!("Request failed: {e}"))?;

        let status = resp.status().as_u16();
        let resp_body: serde_json::Value = resp
            .json()
            .await
            .unwrap_or(serde_json::json!({"raw": "non-json response"}));

        Ok(ProxyResponse {
            status,
            body: resp_body,
        })
    }

    #[tauri::command]
    pub async fn proxy_request(
        req: ProxyRequest,
        state: State<'_, SidecarState>,
    ) -> Result<ProxyResponse, String> {
        execute_sidecar_call(&state, &req.method, &req.route, req.body).await
    }

    #[tauri::command]
    pub async fn flow_discovery_run(
        topic: String,
        state: State<'_, SidecarState>,
    ) -> Result<ProxyResponse, String> {
        let payload = serde_json::json!({
            "topic": topic,
            "max_results": 20,
            "score_threshold": 30.0
        });
        execute_sidecar_call(&state, "POST", "/api/v1/discovery/run", Some(payload)).await
    }

    #[tauri::command]
    pub async fn flow_generate_script(
        idea_id: String,
        topic: String,
        title: String,
        state: State<'_, SidecarState>,
    ) -> Result<ProxyResponse, String> {
        let payload = serde_json::json!({
            "idea_id": idea_id,
            "topic": topic,
            "title": title
        });
        execute_sidecar_call(&state, "POST", "/api/v1/pipeline/script", Some(payload)).await
    }

    #[tauri::command]
    pub async fn flow_save_script(
        script_id: String,
        title: String,
        full_text: String,
        scenes: Vec<serde_json::Value>,
        claims: Vec<serde_json::Value>,
        is_approved: bool,
        state: State<'_, SidecarState>,
    ) -> Result<ProxyResponse, String> {
        let payload = serde_json::json!({
            "script_id": script_id,
            "title": title,
            "full_text": full_text,
            "scenes": scenes,
            "claims": claims,
            "is_approved": is_approved
        });
        execute_sidecar_call(&state, "POST", "/api/v1/pipeline/script/save", Some(payload)).await
    }

    #[tauri::command]
    pub async fn flow_generate_audio(
        script_id: String,
        voice_id: String,
        text: String,
        state: State<'_, SidecarState>,
    ) -> Result<ProxyResponse, String> {
        let payload = serde_json::json!({
            "script_id": script_id,
            "voice_id": voice_id,
            "text": text
        });
        execute_sidecar_call(&state, "POST", "/api/v1/pipeline/audio", Some(payload)).await
    }

    #[tauri::command]
    pub async fn flow_prepare_assets(
        script_id: String,
        slots: Vec<serde_json::Value>,
        state: State<'_, SidecarState>,
    ) -> Result<ProxyResponse, String> {
        let payload = serde_json::json!({
            "script_id": script_id,
            "slots": slots
        });
        execute_sidecar_call(&state, "POST", "/api/v1/pipeline/assets", Some(payload)).await
    }

    #[tauri::command]
    pub async fn flow_generate_preview(
        script_id: String,
        state: State<'_, SidecarState>,
    ) -> Result<ProxyResponse, String> {
        let payload = serde_json::json!({
            "script_id": script_id
        });
        execute_sidecar_call(&state, "POST", "/api/v1/pipeline/preview", Some(payload)).await
    }

    #[tauri::command]
    pub async fn flow_trigger_render(
        profile: String,
        script_id: String,
        state: State<'_, SidecarState>,
    ) -> Result<ProxyResponse, String> {
        let payload = serde_json::json!({
            "profile": profile,
            "script_id": script_id
        });
        execute_sidecar_call(&state, "POST", "/api/v1/pipeline/render", Some(payload)).await
    }

    #[tauri::command]
    pub async fn flow_get_job_status(
        job_id: String,
        state: State<'_, SidecarState>,
    ) -> Result<ProxyResponse, String> {
        let route = format!("/api/v1/jobs/{}", job_id);
        execute_sidecar_call(&state, "GET", &route, None).await
    }

    #[tauri::command]
    pub async fn flow_cancel_job(
        job_id: String,
        state: State<'_, SidecarState>,
    ) -> Result<ProxyResponse, String> {
        let route = format!("/api/v1/jobs/{}/cancel", job_id);
        execute_sidecar_call(&state, "POST", &route, None).await
    }

    #[tauri::command]
    pub async fn flow_get_active_session(
        state: State<'_, SidecarState>,
    ) -> Result<ProxyResponse, String> {
        execute_sidecar_call(&state, "GET", "/api/v1/pipeline/session/active", None).await
    }

    #[tauri::command]
    pub async fn flow_save_active_session(
        payload: serde_json::Value,
        state: State<'_, SidecarState>,
    ) -> Result<ProxyResponse, String> {
        execute_sidecar_call(&state, "POST", "/api/v1/pipeline/session/save", Some(payload)).await
    }

    #[tauri::command]
    pub async fn diagnostics_export_bundle(
        format: Option<String>,
        state: State<'_, SidecarState>,
    ) -> Result<ProxyResponse, String> {
        let fmt = format.unwrap_or_else(|| "json".to_string());
        let route = format!("/api/v1/diagnostics/export?format={}", fmt);
        execute_sidecar_call(&state, "POST", &route, None).await
    }
}

// ---------------------------------------------------------------------------
// Windows Job Object — parent ölünce child da ölür (K-006)
// ---------------------------------------------------------------------------
#[cfg(windows)]
fn attach_job_object(pid: u32) -> anyhow::Result<()> {
    use windows::{
        Win32::System::{
            JobObjects::{
                AssignProcessToJobObject, CreateJobObjectW,
                JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JobObjectExtendedLimitInformation,
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
            },
            Threading::{OpenProcess, PROCESS_SET_QUOTA, PROCESS_TERMINATE},
        },
    };

    unsafe {
        let job = CreateJobObjectW(None, None).context("Job Object oluşturulamadı")?;

        let mut info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;

        windows::Win32::System::JobObjects::SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            &raw const info as *const _,
            std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
        )
        .context("Job bilgisi ayarlanamadı")?;

        let proc_handle =
            OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, false, pid).context("Süreç handle alınamadı")?;

        AssignProcessToJobObject(job, proc_handle).context("Job Object ataması başarısız")?;
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// Sidecar başlatma (K-006)
//   - Token Rust'ta üretilir, ortam değişkeniyle iletilir (argv süreç listesinde
//     görünür, stdout loglara/pipe'lara sızar). Python okuyunca env'den siler.
//   - Port Rust'ta ayrılır (HUSTLER_PORT); hazır olma /health yoklamasıyla anlaşılır.
//   - stdout/stderr null: kimsenin okumadığı pipe dolunca sidecar bloklanır/kırılır.
// ---------------------------------------------------------------------------
const TOKEN_ENV_VAR: &str = "HUSTLER_SESSION_TOKEN";
const PORT_ENV_VAR: &str = "HUSTLER_PORT";
const STARTUP_TIMEOUT: Duration = Duration::from_secs(20);

fn generate_token() -> anyhow::Result<String> {
    let mut bytes = [0u8; 32];
    getrandom::fill(&mut bytes).map_err(|e| anyhow::anyhow!("CSPRNG hatası: {e}"))?;
    Ok(bytes.iter().map(|b| format!("{b:02x}")).collect())
}

fn reserve_free_port() -> anyhow::Result<u16> {
    let listener = TcpListener::bind(("127.0.0.1", 0)).context("Boş port bulunamadı")?;
    Ok(listener.local_addr()?.port())
}

fn health_ok(port: u16) -> bool {
    let addr = std::net::SocketAddr::from(([127, 0, 0, 1], port));
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(300)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    if stream
        .write_all(b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        .is_err()
    {
        return false;
    }
    let mut buf = [0u8; 32];
    matches!(stream.read(&mut buf), Ok(n) if n > 0 && buf[..n].starts_with(b"HTTP/1.1 200"))
}

static SHUTDOWN_TRIGGERED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

pub fn send_graceful_shutdown(port: u16, token: &str) {
    if SHUTDOWN_TRIGGERED.swap(true, std::sync::atomic::Ordering::SeqCst) {
        return;
    }
    let addr = std::net::SocketAddr::from(([127, 0, 0, 1], port));
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(500)) else {
        log::warn!("[Shutdown] Sidecar TCP soketine bağlanılamadı (port: {port})");
        return;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(1500)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(1000)));

    let request = format!(
        "POST /api/v1/system/shutdown HTTP/1.1\r\n\
         Host: 127.0.0.1\r\n\
         Authorization: Bearer {token}\r\n\
         Content-Length: 0\r\n\
         Connection: close\r\n\r\n"
    );

    if let Err(e) = stream.write_all(request.as_bytes()) {
        log::warn!("[Shutdown] Sidecar kapanış komutu gönderilemedi: {e}");
        return;
    }

    let mut buf = [0u8; 128];
    let _ = stream.read(&mut buf);
    log::info!("[Shutdown] Sidecar zarifçe kapatıldı (/api/v1/system/shutdown tetiklendi).");

    // HTTP yanıtı sonrası sürecin ve TCP dinleyicisinin kapanmasını bekle (maksimum 2 saniye)
    let wait_start = std::time::Instant::now();
    let max_wait = Duration::from_secs(2);
    while wait_start.elapsed() < max_wait {
        std::thread::sleep(Duration::from_millis(50));
        if TcpStream::connect_timeout(&addr, Duration::from_millis(50)).is_err() {
            log::info!(
                "[Shutdown] Sidecar soketi kapandı ({:?} içinde temiz kapanış doğrulandı).",
                wait_start.elapsed()
            );
            break;
        }
    }
}

fn resolve_sidecar_binary() -> Option<std::path::PathBuf> {
    if cfg!(debug_assertions) && std::env::var("HUSTLER_FORCE_BUNDLED_SIDECAR").is_err() {
        return None;
    }

    // 1. Üretim paketi: Mevcut uygulamanın yanında veya binaries klasöründe
    if let Ok(current_exe) = std::env::current_exe() {
        if let Some(parent) = current_exe.parent() {
            let candidates = [
                parent.join("hustler-sidecar.exe"),
                parent.join("hustler-sidecar-x86_64-pc-windows-msvc.exe"),
                parent.join("binaries").join("hustler-sidecar-x86_64-pc-windows-msvc.exe"),
                parent.join("binaries").join("hustler-sidecar.exe"),
            ];
            for candidate in candidates {
                if candidate.exists() {
                    return Some(candidate);
                }
            }
        }
    }

    // 2. Geliştirme modu yedek: src-tauri/binaries dizini
    let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let dev_candidates = [
        manifest_dir.join("binaries").join("hustler-sidecar-x86_64-pc-windows-msvc.exe"),
        manifest_dir.join("binaries").join("hustler-sidecar.exe"),
    ];
    dev_candidates
        .into_iter()
        .find(|candidate| candidate.exists())
}

fn spawn_sidecar() -> anyhow::Result<(Child, u16, String)> {
    let port = reserve_free_port()?;
    let token = generate_token()?;

    let mut child = if let Some(binary_path) = resolve_sidecar_binary() {
        log::info!("Sidecar yürütülebilir dosyadan başlatılıyor: {:?}", binary_path);
        let mut cmd = Command::new(binary_path);
        cmd.env(TOKEN_ENV_VAR, &token)
            .env(PORT_ENV_VAR, port.to_string())
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());

        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
        }

        cmd.spawn().context("Derlenmiş Python sidecar binary'si başlatılamadı")?
    } else {
        log::info!("Sidecar geliştirme modunda 'uv' üzerinden başlatılıyor");
        let mut repo_root = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        repo_root.pop(); // src-tauri -> desktop
        repo_root.pop(); // desktop -> apps
        repo_root.pop(); // apps -> Hustler

        let mut cmd = Command::new("uv");
        cmd.args(["run", "python", "-m", "services.core.hustler.main"])
            .current_dir(&repo_root)
            .env(TOKEN_ENV_VAR, &token)
            .env(PORT_ENV_VAR, port.to_string())
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());

        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
        }

        cmd.spawn().context("Python sidecar başlatılamadı")?
    };

    // Windows Job Object — yetim süreç koruması
    #[cfg(windows)]
    {
        let pid = child.id();
        if let Err(e) = attach_job_object(pid) {
            let _ = child.kill();
            return Err(e.context("Job Object ataması başarısız"));
        }
    }

    let start = std::time::Instant::now();
    loop {
        if health_ok(port) {
            return Ok((child, port, token));
        }
        if let Some(status) = child.try_wait()? {
            anyhow::bail!("Sidecar erken sonlandı: {status}");
        }
        if start.elapsed() > STARTUP_TIMEOUT {
            let _ = child.kill();
            anyhow::bail!("Sidecar {STARTUP_TIMEOUT:?} içinde /health yanıtı vermedi");
        }
        std::thread::sleep(Duration::from_millis(150));
    }
}

// ---------------------------------------------------------------------------
// K-703: SSE Olay Köprüsü (Tauri Event Bridge & Reconnect Resilience)
// ---------------------------------------------------------------------------
fn spawn_event_bridge(app_handle: tauri::AppHandle, port: u16, token: String) {
    tauri::async_runtime::spawn(async move {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(3600))
            .build()
            .unwrap_or_default();

        let url = format!("http://127.0.0.1:{port}/events");
        let mut attempt = 0u32;

        loop {
            attempt += 1;
            let state_str = if attempt == 1 { "connecting" } else { "reconnecting" };
            let _ = app_handle.emit("hustler:connection_state", serde_json::json!({
                "state": state_str,
                "attempt": attempt
            }));

            log::info!("[SSE Bridge] Bağlantı deneniyor (deneme {attempt}): {url}");

            let req = client
                .get(&url)
                .header("Authorization", format!("Bearer {token}"))
                .send()
                .await;

            match req {
                Ok(mut resp) if resp.status().is_success() => {
                    log::info!("[SSE Bridge] SSE Akışına bağlandı: 200 OK");
                    attempt = 0;
                    let _ = app_handle.emit("hustler:connection_state", serde_json::json!({
                        "state": "connected"
                    }));

                    let mut buffer = String::new();
                    loop {
                        match resp.chunk().await {
                            Ok(Some(chunk)) => {
                                if let Ok(text) = std::str::from_utf8(&chunk) {
                                    buffer.push_str(text);
                                    while let Some(pos) = buffer.find("\n\n") {
                                        let message = buffer[..pos].to_string();
                                        buffer = buffer[pos + 2..].to_string();

                                        for line in message.lines() {
                                            if let Some(json_str) = line.strip_prefix("data: ") {
                                                if let Ok(val) = serde_json::from_str::<serde_json::Value>(json_str) {
                                                    let _ = app_handle.emit("hustler:event", val);
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            Ok(None) => {
                                log::warn!("[SSE Bridge] SSE akışı kapandı (EOF).");
                                break;
                            }
                            Err(e) => {
                                log::warn!("[SSE Bridge] SSE okuma hatası: {e}");
                                break;
                            }
                        }
                    }
                }
                Ok(resp) => {
                    log::warn!("[SSE Bridge] Sunucu hatası: {}", resp.status());
                }
                Err(e) => {
                    log::warn!("[SSE Bridge] Bağlantı açılamadı: {e}");
                }
            }

            let _ = app_handle.emit("hustler:connection_state", serde_json::json!({
                "state": "disconnected",
                "attempt": attempt
            }));

            let backoff_ms = std::cmp::min(200u64.saturating_mul(1u64 << std::cmp::min(attempt, 5)), 5000u64);
            tokio::time::sleep(Duration::from_millis(backoff_ms)).await;
        }
    });
}

// ---------------------------------------------------------------------------
// Tauri giriş noktası
// ---------------------------------------------------------------------------
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let (_child, port, token) =
                spawn_sidecar().expect("Sidecar başlatılamadı");

            log::info!("Sidecar bağlandı: port={port}");

            let client = reqwest::Client::builder()
                .timeout(Duration::from_secs(30))
                .build()
                .expect("HTTP client oluşturulamadı");

            let handle_clone = app.handle().clone();
            spawn_event_bridge(handle_clone, port, token.clone());

            app.manage(SidecarState { port, token, client });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            ipc::proxy_request,
            ipc::flow_discovery_run,
            ipc::flow_generate_script,
            ipc::flow_save_script,
            ipc::flow_generate_audio,
            ipc::flow_prepare_assets,
            ipc::flow_generate_preview,
            ipc::flow_trigger_render,
            ipc::flow_get_job_status,
            ipc::flow_cancel_job,
            ipc::flow_get_active_session,
            ipc::flow_save_active_session,
            ipc::diagnostics_export_bundle
        ])
        .build(tauri::generate_context!())
        .expect("Tauri oluşturulamadı");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            log::info!("[Tauri] RunEvent::Exit yakalandı, pencereler gizleniyor ve sidecar zarifçe kapatılıyor...");
            for window in app_handle.webview_windows().values() {
                let _ = window.hide();
            }
            if let Some(state) = app_handle.try_state::<SidecarState>() {
                send_graceful_shutdown(state.port, &state.token);
            }
        }
    });
}
