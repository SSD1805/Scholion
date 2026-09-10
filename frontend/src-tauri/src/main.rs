#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;
mod playback;
mod processing;
mod update_verify;

use tauri::Manager;

fn maybe_run_update_verifier() -> Option<i32> {
    let arguments: Vec<_> = std::env::args_os().skip(1).collect();
    let requests_verifier = arguments.first().and_then(|argument| argument.to_str())
        == Some(update_verify::VERIFY_ARGUMENT);
    if !requests_verifier {
        return None;
    }
    if arguments.len() != 1 {
        return Some(2);
    }
    Some(update_verify::run_cli())
}

fn main() {
    if let Some(exit_code) = maybe_run_update_verifier() {
        std::process::exit(exit_code);
    }

    let playback_sessions = playback::PlaybackSessions::default();
    let playback_protocol = playback_sessions.clone();

    tauri::Builder::default()
        .setup(|app| {
            let runtime =
                backend::DesktopRuntime::discover(app.handle()).map_err(std::io::Error::other)?;
            app.manage(runtime);
            Ok(())
        })
        .manage(processing::ProcessingProcesses::default())
        .manage(playback_sessions)
        .plugin(tauri_plugin_dialog::init())
        .register_asynchronous_uri_scheme_protocol(
            "scholion-media",
            move |_context, request, responder| {
                responder.respond(playback_protocol.protocol_response(request));
            },
        )
        .invoke_handler(tauri::generate_handler![
            backend::desktop_request,
            backend::transcript_tools_request,
            backend::lifecycle_request,
            backend::update_request,
            processing::processing_start_task,
            processing::processing_task_status,
            processing::processing_cancel_task,
            playback::playback_prepare,
            playback::playback_release,
        ])
        .run(tauri::generate_context!())
        .expect("Scholion desktop host could not start");
}
