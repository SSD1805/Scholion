use serde_json::Value;
use std::env;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Mutex;

const MAX_REQUEST_BYTES: usize = 128 * 1024;

// Each one-shot Python bridge process composes application services that may open the
// same DuckDB-backed projections. DuckDB does not support overlapping writer processes
// against one database file, so native bridge calls must cross that boundary serially.
// Long-running Processing workers use a separate command path and are not held behind
// this lock.
static BRIDGE_PROCESS_LOCK: Mutex<()> = Mutex::new(());

pub(crate) fn configured_python() -> PathBuf {
    if let Ok(value) = env::var("SCHOLION_PYTHON") {
        if !value.trim().is_empty() {
            return PathBuf::from(value);
        }
    }

    if cfg!(debug_assertions) {
        let repo_root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let candidate = if cfg!(windows) {
            repo_root.join(".venv").join("Scripts").join("python.exe")
        } else {
            repo_root.join(".venv").join("bin").join("python")
        };
        if candidate.is_file() {
            return candidate;
        }
    }

    PathBuf::from("python")
}

fn python_unavailable_message() -> String {
    if cfg!(debug_assertions) {
        "Scholion's local Python service is unavailable. From the repository root run `python3.12 scripts/bootstrap_python.py`, or set SCHOLION_PYTHON to a compatible interpreter."
            .to_string()
    } else {
        "Scholion's local Python service is unavailable".to_string()
    }
}

fn python_exit_message() -> String {
    if cfg!(debug_assertions) {
        "Scholion's local Python service exited unexpectedly. From frontend run `npm run doctor:desktop` to verify the source environment before retrying."
            .to_string()
    } else {
        "Scholion's local Python service exited unexpectedly".to_string()
    }
}

fn request_method(request: &Value) -> &str {
    request
        .get("method")
        .and_then(Value::as_str)
        .unwrap_or("<unknown>")
}

fn run_python_request(module: &'static str, request: Value) -> Result<Value, String> {
    let _bridge_guard = BRIDGE_PROCESS_LOCK
        .lock()
        .map_err(|_| "Scholion's local desktop bridge is unavailable".to_string())?;

    let method = request_method(&request).to_string();
    let encoded =
        serde_json::to_vec(&request).map_err(|_| "Could not encode desktop request".to_string())?;
    if encoded.len() > MAX_REQUEST_BYTES {
        return Err("Desktop request exceeded the safe size limit".to_string());
    }

    let python = configured_python();
    if cfg!(debug_assertions) {
        eprintln!(
            "[scholion-desktop] bridge start module={module} method={method} python={}",
            python.display()
        );
    }

    let mut child = Command::new(&python)
        .args(["-m", module])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|_| python_unavailable_message())?;

    let mut stdin = child
        .stdin
        .take()
        .ok_or_else(|| "Could not open the Scholion desktop bridge".to_string())?;
    stdin
        .write_all(&encoded)
        .map_err(|_| "Could not send the request to Scholion".to_string())?;
    drop(stdin);

    let output = child
        .wait_with_output()
        .map_err(|_| "Scholion's local Python service did not finish cleanly".to_string())?;

    if cfg!(debug_assertions) {
        eprintln!(
            "[scholion-desktop] bridge finish module={module} method={method} status={} stdout_bytes={} stderr_bytes={}",
            output.status,
            output.stdout.len(),
            output.stderr.len()
        );
    }

    if !output.status.success() {
        return Err(python_exit_message());
    }

    serde_json::from_slice(&output.stdout).map_err(|_| {
        if cfg!(debug_assertions) {
            eprintln!(
                "[scholion-desktop] bridge parse failure module={module} method={method} stdout_bytes={} stderr_bytes={}",
                output.stdout.len(),
                output.stderr.len()
            );
        }
        "Scholion's local Python service returned an invalid response".to_string()
    })
}

async fn request_module(module: &'static str, request: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || run_python_request(module, request))
        .await
        .map_err(|_| "Scholion's local service task could not be completed".to_string())?
}

pub(crate) async fn playback_authorization_request(request: Value) -> Result<Value, String> {
    request_module("scholion.desktop.playback_bridge", request).await
}

#[tauri::command]
pub async fn desktop_request(request: Value) -> Result<Value, String> {
    request_module("scholion.desktop.bridge", request).await
}

#[tauri::command]
pub async fn transcript_tools_request(request: Value) -> Result<Value, String> {
    request_module("scholion.desktop.transcript_tools_bridge", request).await
}

#[tauri::command]
pub async fn lifecycle_request(request: Value) -> Result<Value, String> {
    request_module("scholion.desktop.custody_bridge", request).await
}
