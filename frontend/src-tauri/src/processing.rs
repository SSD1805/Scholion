use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::io::{Read, Write};
use std::process::{Child, Command, ExitStatus, Stdio};
use std::sync::Mutex;
use tauri::State;

const MAX_TASK_BYTES: usize = 64 * 1024;
const MAX_TASK_RESULT_BYTES: usize = 8 * 1024;
const MAX_PUBLIC_ERROR_CODE_BYTES: usize = 128;
const MAX_PUBLIC_ERROR_MESSAGE_BYTES: usize = 1024;
const WORKER_PROTOCOL_VERSION: u8 = 1;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
enum TaskKind {
    TranscriptionStart,
    TranscriptionResume,
    TranscriptionRetry,
    ModelInstall,
    ModelRemove,
}

#[derive(Debug, Deserialize)]
struct TaskEnvelope {
    task_id: String,
    kind: TaskKind,
}

#[derive(Debug, Deserialize)]
struct WorkerError {
    code: String,
    message: String,
}

#[derive(Debug, Deserialize)]
struct WorkerOutcome {
    protocol_version: u8,
    ok: bool,
    error: Option<WorkerError>,
}

#[derive(Clone, Serialize)]
pub struct TaskStatus {
    task_id: String,
    state: &'static str,
    exit_code: Option<i32>,
    error_code: Option<String>,
    error_message: Option<String>,
}

struct ProcessEntry {
    child: Option<Child>,
    state: &'static str,
    exit_code: Option<i32>,
    error_code: Option<String>,
    error_message: Option<String>,
}

impl ProcessEntry {
    fn running(child: Child) -> Self {
        Self {
            child: Some(child),
            state: "running",
            exit_code: None,
            error_code: None,
            error_message: None,
        }
    }

    fn refresh(&mut self) -> Result<(), String> {
        let Some(child) = self.child.as_mut() else {
            return Ok(());
        };
        let status = child
            .try_wait()
            .map_err(|_| "Scholion could not inspect the local processing task".to_string())?;
        if let Some(status) = status {
            self.finish(status);
        }
        Ok(())
    }

    fn finish(&mut self, status: ExitStatus) {
        let outcome = self.child.as_mut().and_then(read_worker_outcome);
        self.exit_code = status.code();
        self.state = if worker_completed(status.success(), outcome.as_ref()) {
            "completed"
        } else {
            "failed"
        };
        if self.state == "failed" {
            if let Some(error) = outcome.filter(|item| !item.ok).and_then(|item| item.error) {
                self.error_code = Some(error.code);
                self.error_message = Some(error.message);
            } else {
                self.error_code = Some("worker_failed".to_string());
                self.error_message = Some("Local processing stopped before completion".to_string());
            }
        }
        self.child = None;
    }

    fn status(&self, task_id: &str) -> TaskStatus {
        TaskStatus {
            task_id: task_id.to_string(),
            state: self.state,
            exit_code: self.exit_code,
            error_code: self.error_code.clone(),
            error_message: self.error_message.clone(),
        }
    }
}

fn worker_completed(process_succeeded: bool, outcome: Option<&WorkerOutcome>) -> bool {
    process_succeeded && matches!(outcome, Some(item) if item.ok)
}

fn valid_worker_error(error: &WorkerError) -> bool {
    !error.code.is_empty()
        && error.code.len() <= MAX_PUBLIC_ERROR_CODE_BYTES
        && error
            .code
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'_')
        && !error.message.trim().is_empty()
        && error.message.len() <= MAX_PUBLIC_ERROR_MESSAGE_BYTES
}

fn parse_worker_outcome(bytes: &[u8]) -> Option<WorkerOutcome> {
    if bytes.is_empty() || bytes.len() > MAX_TASK_RESULT_BYTES {
        return None;
    }
    let outcome: WorkerOutcome = serde_json::from_slice(bytes).ok()?;
    if outcome.protocol_version != WORKER_PROTOCOL_VERSION {
        return None;
    }
    match (&outcome.ok, &outcome.error) {
        (true, None) => Some(outcome),
        (false, Some(error)) if valid_worker_error(error) => Some(outcome),
        _ => None,
    }
}

fn read_worker_outcome(child: &mut Child) -> Option<WorkerOutcome> {
    let stdout = child.stdout.take()?;
    let mut bounded = stdout.take((MAX_TASK_RESULT_BYTES + 1) as u64);
    let mut bytes = Vec::new();
    bounded.read_to_end(&mut bytes).ok()?;
    parse_worker_outcome(&bytes)
}

fn ensure_no_running_task(entries: &mut HashMap<String, ProcessEntry>) -> Result<(), String> {
    for entry in entries.values_mut() {
        entry.refresh()?;
    }
    if entries.values().any(|entry| entry.state == "running") {
        return Err(
            "Another local processing task is already running. Wait for it to finish or stop it first."
                .to_string(),
        );
    }
    Ok(())
}

#[derive(Default)]
pub struct ProcessingProcesses {
    entries: Mutex<HashMap<String, ProcessEntry>>,
}

impl Drop for ProcessingProcesses {
    fn drop(&mut self) {
        let Ok(entries) = self.entries.get_mut() else {
            return;
        };
        for entry in entries.values_mut() {
            if let Some(child) = entry.child.as_mut() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

fn validate_envelope(task: &Value) -> Result<TaskEnvelope, String> {
    let envelope: TaskEnvelope = serde_json::from_value(task.clone())
        .map_err(|_| "Processing task was invalid or unsupported".to_string())?;
    if envelope.task_id.is_empty()
        || envelope.task_id.len() > 128
        || !envelope
            .task_id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-' || byte == b'_')
    {
        return Err("Processing task identifier was invalid".to_string());
    }
    match envelope.kind {
        TaskKind::TranscriptionStart
        | TaskKind::TranscriptionResume
        | TaskKind::TranscriptionRetry
        | TaskKind::ModelInstall
        | TaskKind::ModelRemove => {}
    }
    Ok(envelope)
}

fn python_unavailable_message() -> String {
    if cfg!(debug_assertions) {
        "Scholion's local Python worker is unavailable. From the repository root run `python3.12 scripts/bootstrap_python.py`, or set SCHOLION_PYTHON to a compatible repository virtual-environment interpreter."
            .to_string()
    } else {
        "Scholion's local Python worker is unavailable".to_string()
    }
}

#[tauri::command]
pub async fn processing_start_task(
    task: Value,
    processes: State<'_, ProcessingProcesses>,
) -> Result<TaskStatus, String> {
    let encoded = serde_json::to_vec(&task)
        .map_err(|_| "Could not encode local processing task".to_string())?;
    if encoded.len() > MAX_TASK_BYTES {
        return Err("Processing task exceeded the safe size limit".to_string());
    }
    let envelope = validate_envelope(&task)?;

    let mut entries = processes
        .entries
        .lock()
        .map_err(|_| "Scholion processing state is unavailable".to_string())?;
    if entries.contains_key(&envelope.task_id) {
        return Err("Processing task identifier is already in use".to_string());
    }
    ensure_no_running_task(&mut entries)?;

    let mut child = Command::new(crate::backend::configured_python())
        .args(["-m", "scholion.desktop.processing_worker"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| python_unavailable_message())?;

    let write_result = child
        .stdin
        .take()
        .ok_or_else(|| "Could not open the Scholion processing worker".to_string())
        .and_then(|mut stdin| {
            stdin
                .write_all(&encoded)
                .map_err(|_| "Could not send the processing task to Scholion".to_string())
        });
    if let Err(message) = write_result {
        let _ = child.kill();
        let _ = child.wait();
        return Err(message);
    }

    let task_id = envelope.task_id;
    entries.insert(task_id.clone(), ProcessEntry::running(child));
    Ok(entries
        .get(&task_id)
        .expect("inserted processing task must exist")
        .status(&task_id))
}

#[tauri::command]
pub async fn processing_task_status(
    task_id: String,
    processes: State<'_, ProcessingProcesses>,
) -> Result<TaskStatus, String> {
    let mut entries = processes
        .entries
        .lock()
        .map_err(|_| "Scholion processing state is unavailable".to_string())?;
    let entry = entries
        .get_mut(&task_id)
        .ok_or_else(|| "Processing task is not known to this Scholion session".to_string())?;
    entry.refresh()?;
    Ok(entry.status(&task_id))
}

#[tauri::command]
pub async fn processing_cancel_task(
    task_id: String,
    processes: State<'_, ProcessingProcesses>,
) -> Result<TaskStatus, String> {
    let mut entries = processes
        .entries
        .lock()
        .map_err(|_| "Scholion processing state is unavailable".to_string())?;
    let entry = entries
        .get_mut(&task_id)
        .ok_or_else(|| "Processing task is not known to this Scholion session".to_string())?;
    entry.refresh()?;
    if let Some(child) = entry.child.as_mut() {
        child
            .kill()
            .map_err(|_| "Scholion could not stop the local processing task".to_string())?;
        let status = child.wait().map_err(|_| {
            "Scholion could not finish stopping the local processing task".to_string()
        })?;
        entry.exit_code = status.code();
        entry.state = "cancelled";
        entry.error_code = None;
        entry.error_message = None;
        entry.child = None;
    }
    Ok(entry.status(&task_id))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn completed_entry(state: &'static str) -> ProcessEntry {
        ProcessEntry {
            child: None,
            state,
            exit_code: None,
            error_code: None,
            error_message: None,
        }
    }

    #[test]
    fn worker_outcome_requires_a_valid_versioned_shape() {
        let success = br#"{"protocol_version":1,"ok":true,"error":null}"#;
        let failure = br#"{"protocol_version":1,"ok":false,"error":{"code":"transcription_failed","message":"Local transcription did not complete"}}"#;
        let wrong_version = br#"{"protocol_version":2,"ok":true,"error":null}"#;
        let success_with_error = br#"{"protocol_version":1,"ok":true,"error":{"code":"bad","message":"should not exist"}}"#;
        let failure_without_error = br#"{"protocol_version":1,"ok":false,"error":null}"#;

        assert!(parse_worker_outcome(success).is_some());
        assert!(parse_worker_outcome(failure).is_some());
        assert!(parse_worker_outcome(wrong_version).is_none());
        assert!(parse_worker_outcome(success_with_error).is_none());
        assert!(parse_worker_outcome(failure_without_error).is_none());
        assert!(parse_worker_outcome(&[]).is_none());
    }

    #[test]
    fn malformed_or_missing_outcome_never_counts_as_completed() {
        let success = parse_worker_outcome(br#"{"protocol_version":1,"ok":true,"error":null}"#);

        assert!(worker_completed(true, success.as_ref()));
        assert!(!worker_completed(true, None));
        assert!(!worker_completed(false, success.as_ref()));
    }

    #[test]
    fn worker_error_fields_are_bounded_and_structured() {
        let valid = WorkerError {
            code: "resource_admission_failed".to_string(),
            message: "Current resources are below the safe requirement".to_string(),
        };
        let invalid_code = WorkerError {
            code: "../../private".to_string(),
            message: "No".to_string(),
        };
        let oversized_message = WorkerError {
            code: "internal_error".to_string(),
            message: "x".repeat(MAX_PUBLIC_ERROR_MESSAGE_BYTES + 1),
        };

        assert!(valid_worker_error(&valid));
        assert!(!valid_worker_error(&invalid_code));
        assert!(!valid_worker_error(&oversized_message));
    }

    #[test]
    fn only_one_long_running_processing_task_can_be_active() {
        let mut entries = HashMap::from([("active".to_string(), completed_entry("running"))]);

        let error = ensure_no_running_task(&mut entries).expect_err("running task must block");
        assert!(error.contains("already running"));

        entries.get_mut("active").expect("entry exists").state = "completed";
        assert!(ensure_no_running_task(&mut entries).is_ok());
    }
}
