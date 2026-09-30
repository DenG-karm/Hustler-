// Hustler Desktop Shell — K-006 + K-010
//
// K-006: Python sidecar başlatma
//   - port=0 trick ile dinamik port
//   - stdout'tan HUSTLER_BIND::PORT=x::TOKEN=y okunur
//   - Windows Job Object ile yetim süreç önlenir
//
// K-010: IPC Köprüsü
//   - Frontend hiçbir zaman doğrudan HTTP çağrısı yapmaz
//   - Rust, Bearer token'ı ekleyerek 127.0.0.1'e proxy eder
//   - İzin listesi dışı rotalar reddedilir

use std::{
    collections::HashSet,
    io::{BufRead, BufReader},
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
            Threading::{OpenProcess, PROCESS_ALL_ACCESS},
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
            OpenProcess(PROCESS_ALL_ACCESS, false, pid).context("Süreç handle alınamadı")?;

        AssignProcessToJobObject(job, proc_handle).context("Job Object ataması başarısız")?;
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// Sidecar başlatma — stdout'tan port/token oku (K-006)
// ---------------------------------------------------------------------------
fn spawn_sidecar() -> anyhow::Result<(Child, u16, String)> {
    let mut core_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    core_dir.pop(); // src-tauri -> desktop
    core_dir.pop(); // desktop -> apps
    core_dir.pop(); // apps -> Hustler
    let core_dir = core_dir.join("services").join("core");

    let mut child = Command::new("uv")
        .args(["run", "python", "-m", "hustler.main"])
        .current_dir(&core_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .context("Python sidecar başlatılamadı")?;

    // Windows Job Object — yetim süreç koruması
    #[cfg(windows)]
    {
        let pid = child.id();
        attach_job_object(pid).context("Job Object ataması başarısız")?;
    }

    // stdout'tan HUSTLER_BIND satırını oku
    let stdout = child.stdout.take().context("stdout alınamadı")?;
    let mut reader = BufReader::new(stdout);
    let mut line = String::new();

    let start = std::time::Instant::now();
    loop {
        if start.elapsed() > Duration::from_secs(10) {
            anyhow::bail!("Sidecar 10 saniye içinde BIND mesajı basmadı");
        }
        line.clear();
        reader.read_line(&mut line)?;
        if line.contains("HUSTLER_BIND::") {
            break;
        }
    }

    // HUSTLER_BIND::PORT=xxxxx::TOKEN=yyyyy
    let port = line
        .split("PORT=")
        .nth(1)
        .and_then(|s| s.split("::").next())
        .and_then(|s| s.trim().parse::<u16>().ok())
        .context("Port ayrıştırılamadı")?;

    let token = line
        .split("TOKEN=")
        .nth(1)
        .map(|s| s.trim().to_string())
        .context("Token ayrıştırılamadı")?;

    Ok((child, port, token))
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
