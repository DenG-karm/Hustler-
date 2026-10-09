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
    collections::HashSet,
    io::{Read, Write},
    net::{TcpListener, TcpStream},
    process::{Child, Command, Stdio},
    sync::OnceLock,
    time::Duration,
};

use anyhow::Context;
use serde::{Deserialize, Serialize};
use tauri::{Manager, State};

// ---------------------------------------------------------------------------
// Sidecar durumu — Tauri State'e eklenir, frontend'e asla açılmaz
// ---------------------------------------------------------------------------
pub struct SidecarState {
    pub port: u16,
    pub token: String,
    pub client: reqwest::Client,
}

// ---------------------------------------------------------------------------
// İzin listesi — OpenAPI'den üretilecek, şimdilik sabit
// ---------------------------------------------------------------------------
static ALLOWED_ROUTES: OnceLock<HashSet<&'static str>> = OnceLock::new();

fn allowed_routes() -> &'static HashSet<&'static str> {
    ALLOWED_ROUTES.get_or_init(|| {
        let mut s = HashSet::new();
        s.insert("/health");
        s.insert("/events");
        s
    })
}

// ---------------------------------------------------------------------------
// IPC proxy komutu (K-010)
// ---------------------------------------------------------------------------
#[derive(Debug, Serialize, Deserialize)]
pub struct ProxyRequest {
    pub method: String,
    pub route: String,
    pub body: Option<serde_json::Value>,
}

#[derive(Debug, Serialize)]
pub struct ProxyResponse {
    pub status: u16,
    pub body: serde_json::Value,
}

pub mod ipc {
    use super::*;

    #[tauri::command]
    pub async fn proxy_request(
        req: ProxyRequest,
        state: State<'_, SidecarState>,
    ) -> Result<ProxyResponse, String> {
        // İzin listesi denetimi
        if !allowed_routes().contains(req.route.as_str()) {
            return Err(format!("Route '{}' is not in the allowlist", req.route));
        }

        let url = format!("http://127.0.0.1:{}{}", state.port, req.route);

        let mut builder = match req.method.to_uppercase().as_str() {
            "GET" => state.client.get(&url),
            "POST" => state.client.post(&url),
            "DELETE" => state.client.delete(&url),
            m => return Err(format!("Unsupported method: {m}")),
        }
        .header("Authorization", format!("Bearer {}", state.token))
        .timeout(Duration::from_secs(30));

        if let Some(body) = req.body {
            builder = builder.json(&body);
        }

        let resp = builder
            .send()
            .await
            .map_err(|e| format!("Request failed: {e}"))?;

        let status = resp.status().as_u16();
        let body: serde_json::Value = resp
            .json()
            .await
            .unwrap_or(serde_json::json!({"raw": "non-json response"}));

        Ok(ProxyResponse { status, body })
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

fn spawn_sidecar() -> anyhow::Result<(Child, u16, String)> {
    let mut repo_root = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    repo_root.pop(); // src-tauri -> desktop
    repo_root.pop(); // desktop -> apps
    repo_root.pop(); // apps -> Hustler

    let port = reserve_free_port()?;
    let token = generate_token()?;

    // Modül yolu `services.core.hustler...` olduğundan çalışma dizini repo kökü olmalı.
    let mut child = Command::new("uv")
        .args(["run", "python", "-m", "services.core.hustler.main"])
        .current_dir(&repo_root)
        .env(TOKEN_ENV_VAR, &token)
        .env(PORT_ENV_VAR, port.to_string())
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .context("Python sidecar başlatılamadı")?;

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
// Tauri giriş noktası
// ---------------------------------------------------------------------------
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
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

            app.manage(SidecarState { port, token, client });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![ipc::proxy_request])
        .run(tauri::generate_context!())
        .expect("Tauri başlatılamadı");
}
