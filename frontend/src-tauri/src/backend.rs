use serde_json::Value;
use std::env;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Manager, State};

const MAX_REQUEST_BYTES: usize = 128 * 1024;
const NATIVE_UPDATE_VERIFIER_ENV: &str = "SCHOLION_NATIVE_UPDATE_VERIFIER";

// Each one-shot Python bridge process composes application services that may open the
// same DuckDB-backed projections. DuckDB does not support overlapping writer processes
// against one database file, so native bridge calls must cross that boundary serially.
// Long-running Processing workers use a separate command path and are not held behind
// this lock.
static BRIDGE_PROCESS_LOCK: Mutex<()> = Mutex::new(());

#[derive(Clone, Copy)]
pub(crate) enum RuntimeMode {
    DesktopBridge,
    CustodyBridge,
    PlaybackBridge,
    ProcessingWorker,
    TranscriptToolsBridge,
    UpdateBridge,
}

impl RuntimeMode {
    fn frozen_argument(self) -> &'static str {
        match self {
            Self::DesktopBridge => "bridge",
            Self::CustodyBridge => "custody",
            Self::PlaybackBridge => "playback",
            Self::ProcessingWorker => "processing-worker",
            Self::TranscriptToolsBridge => "transcript-tools",
            Self::UpdateBridge => "update",
        }
    }

    fn python_module(self) -> &'static str {
        match self {
            Self::DesktopBridge => "scholion.desktop.bridge",
            Self::CustodyBridge => "scholion.desktop.custody_bridge",
            Self::PlaybackBridge => "scholion.desktop.playback_bridge",
            Self::ProcessingWorker => "scholion.desktop.processing_worker",
            Self::TranscriptToolsBridge => "scholion.desktop.transcript_tools_bridge",
            Self::UpdateBridge => "scholion.desktop.update_bridge",
        }
    }
}

#[derive(Clone, Copy)]
enum RuntimeKind {
    Python,
    Frozen,
}

#[derive(Clone)]
pub(crate) struct DesktopRuntime {
    executable: PathBuf,
    kind: RuntimeKind,
    native_update_verifier: Option<PathBuf>,
}

fn packaged_native_update_verifier(resource_dir: &Path) -> Option<PathBuf> {
    let current_executable = env::current_exe().ok()?;
    let expected_catalog = crate::update_verify::catalog_path_for_executable(&current_executable)?;
    let resource_catalog = resource_dir.join("update-keys.json");
    if expected_catalog != resource_catalog
        || !crate::update_verify::catalog_is_valid(&resource_catalog)
    {
        return None;
    }
    Some(current_executable)
}

impl DesktopRuntime {
    pub(crate) fn discover(app: &AppHandle) -> Result<Self, String> {
        if cfg!(debug_assertions) {
            if let Ok(value) = env::var("SCHOLION_RUNTIME") {
                if !value.trim().is_empty() {
                    return Ok(Self {
                        executable: PathBuf::from(value),
                        kind: RuntimeKind::Frozen,
                        native_update_verifier: None,
                    });
                }
            }

            if let Ok(value) = env::var("SCHOLION_PYTHON") {
                if !value.trim().is_empty() {
                    return Ok(Self {
                        executable: PathBuf::from(value),
                        kind: RuntimeKind::Python,
                        native_update_verifier: None,
                    });
                }
            }

            let repo_root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
            let candidate = if cfg!(windows) {
                repo_root.join(".venv").join("Scripts").join("python.exe")
            } else {
                repo_root.join(".venv").join("bin").join("python")
            };
            return Ok(Self {
                executable: if candidate.is_file() {
                    candidate
                } else {
                    PathBuf::from("python")
                },
                kind: RuntimeKind::Python,
                native_update_verifier: None,
            });
        }

        let resource_dir = app
            .path()
            .resource_dir()
            .map_err(|_| "Scholion could not resolve its packaged runtime directory".to_string())?;
        let executable_name = if cfg!(windows) {
            "scholion-runtime.exe"
        } else {
            "scholion-runtime"
        };
        let candidate = resource_dir.join("runtime").join(executable_name);
        if !candidate.is_file() {
            return Err("Scholion's packaged local runtime is missing".to_string());
        }
        let native_update_verifier = packaged_native_update_verifier(&resource_dir);
        Ok(Self {
            executable: candidate,
            kind: RuntimeKind::Frozen,
            native_update_verifier,
        })
    }

    pub(crate) fn command(&self, mode: RuntimeMode) -> Command {
        let mut command = Command::new(&self.executable);
        match self.kind {
            RuntimeKind::Python => {
                command.args(["-m", mode.python_module()]);
            }
            RuntimeKind::Frozen => {
                command.arg(mode.frozen_argument());
            }
        }
        command.env_remove(NATIVE_UPDATE_VERIFIER_ENV);
        if let RuntimeMode::UpdateBridge = mode {
            if let Some(verifier) = &self.native_update_verifier {
                command.env(NATIVE_UPDATE_VERIFIER_ENV, verifier);
            }
        }
        command
    }
}

fn runtime_unavailable_message() -> String {
    if cfg!(debug_assertions) {
        "Scholion's local Python service is unavailable. From the repository root run `python3.12 scripts/bootstrap_python.py`, or set SCHOLION_PYTHON to a compatible interpreter."
            .to_string()
    } else {
        "Scholion's packaged local service is unavailable".to_string()
    }
}

fn runtime_exit_message() -> String {
    if cfg!(debug_assertions) {
        "Scholion's local Python service exited unexpectedly. From frontend run `npm run doctor:desktop` to verify the source environment before retrying."
            .to_string()
    } else {
        "Scholion's packaged local service exited unexpectedly".to_string()
    }
}

fn request_method(request: &Value) -> &str {
    request
        .get("method")
        .and_then(Value::as_str)
        .unwrap_or("<unknown>")
}

fn run_runtime_request(
    runtime: &DesktopRuntime,
    mode: RuntimeMode,
    request: Value,
) -> Result<Value, String> {
    let _bridge_guard = BRIDGE_PROCESS_LOCK
        .lock()
        .map_err(|_| "Scholion's local desktop bridge is unavailable".to_string())?;

    let method = request_method(&request).to_string();
    let encoded =
        serde_json::to_vec(&request).map_err(|_| "Could not encode desktop request".to_string())?;
    if encoded.len() > MAX_REQUEST_BYTES {
        return Err("Desktop request exceeded the safe size limit".to_string());
    }

    if cfg!(debug_assertions) {
        eprintln!(
            "[scholion-desktop] bridge start mode={} method={method}",
            mode.frozen_argument()
        );
    }

    let mut child = runtime
        .command(mode)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|_| runtime_unavailable_message())?;

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
        .map_err(|_| "Scholion's local service task did not finish cleanly".to_string())?;

    if cfg!(debug_assertions) {
        eprintln!(
            "[scholion-desktop] bridge finish mode={} method={method} status={} stdout_bytes={} stderr_bytes={}",
            mode.frozen_argument(),
            output.status,
            output.stdout.len(),
            output.stderr.len()
        );
    }

    if !output.status.success() {
        return Err(runtime_exit_message());
    }

    serde_json::from_slice(&output.stdout).map_err(|_| {
        if cfg!(debug_assertions) {
            eprintln!(
                "[scholion-desktop] bridge parse failure mode={} method={method} stdout_bytes={} stderr_bytes={}",
                mode.frozen_argument(),
                output.stdout.len(),
                output.stderr.len()
            );
        }
        "Scholion's local service returned an invalid response".to_string()
    })
}

async fn request_mode(
    mode: RuntimeMode,
    request: Value,
    runtime: DesktopRuntime,
) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || run_runtime_request(&runtime, mode, request))
        .await
        .map_err(|_| "Scholion's local service task could not be completed".to_string())?
}

pub(crate) async fn playback_authorization_request(
    request: Value,
    runtime: DesktopRuntime,
) -> Result<Value, String> {
    request_mode(RuntimeMode::PlaybackBridge, request, runtime).await
}

#[tauri::command]
pub async fn desktop_request(
    request: Value,
    runtime: State<'_, DesktopRuntime>,
) -> Result<Value, String> {
    request_mode(RuntimeMode::DesktopBridge, request, runtime.inner().clone()).await
}

#[tauri::command]
pub async fn transcript_tools_request(
    request: Value,
    runtime: State<'_, DesktopRuntime>,
) -> Result<Value, String> {
    request_mode(
        RuntimeMode::TranscriptToolsBridge,
        request,
        runtime.inner().clone(),
    )
    .await
}

#[tauri::command]
pub async fn lifecycle_request(
    request: Value,
    runtime: State<'_, DesktopRuntime>,
) -> Result<Value, String> {
    request_mode(RuntimeMode::CustodyBridge, request, runtime.inner().clone()).await
}

#[tauri::command]
pub async fn update_request(
    request: Value,
    runtime: State<'_, DesktopRuntime>,
) -> Result<Value, String> {
    request_mode(RuntimeMode::UpdateBridge, request, runtime.inner().clone()).await
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ffi::OsStr;

    fn runtime(verifier: Option<&str>) -> DesktopRuntime {
        DesktopRuntime {
            executable: PathBuf::from("runtime"),
            kind: RuntimeKind::Frozen,
            native_update_verifier: verifier.map(PathBuf::from),
        }
    }

    #[test]
    fn update_command_receives_only_configured_native_verifier() {
        let command = runtime(Some("trusted-native")).command(RuntimeMode::UpdateBridge);
        let verifier = command
            .get_envs()
            .find(|(name, _)| *name == OsStr::new(NATIVE_UPDATE_VERIFIER_ENV))
            .and_then(|(_, value)| value);
        assert_eq!(verifier, Some(OsStr::new("trusted-native")));
    }

    #[test]
    fn commands_scrub_ambient_native_verifier_when_not_authorized() {
        let command = runtime(None).command(RuntimeMode::UpdateBridge);
        let verifier = command
            .get_envs()
            .find(|(name, _)| *name == OsStr::new(NATIVE_UPDATE_VERIFIER_ENV));
        assert_eq!(
            verifier,
            Some((OsStr::new(NATIVE_UPDATE_VERIFIER_ENV), None))
        );

        let command = runtime(Some("trusted-native")).command(RuntimeMode::DesktopBridge);
        let verifier = command
            .get_envs()
            .find(|(name, _)| *name == OsStr::new(NATIVE_UPDATE_VERIFIER_ENV));
        assert_eq!(
            verifier,
            Some((OsStr::new(NATIVE_UPDATE_VERIFIER_ENV), None))
        );
    }
}
