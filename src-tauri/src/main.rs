// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{AppHandle, Manager};
use std::process::{Command, Child};
use std::sync::Mutex;

struct EngineProcess(Mutex<Option<Child>>);

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let mut root = std::env::current_dir().unwrap();
            if root.ends_with("src-tauri") {
                root.pop();
            }
            
            let venv_path = root.join(".venv/bin/python3");
            let engine_path = root.join("engine/engine.py");

            println!("Launching engine from: {:?}", engine_path);
            println!("Using python from: {:?}", venv_path);

            // Start the Python sidecar automatically using the local venv
            let child = Command::new(venv_path)
                .arg(engine_path)
                .spawn()
                .expect("Failed to start OpenCV engine. Make sure .venv exists in project root.");
            
            app.manage(EngineProcess(Mutex::new(Some(child))));
            
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // Kill the sidecar when closing
                if let Some(state) = window.try_state::<EngineProcess>() {
                    if let Ok(mut lock) = state.0.lock() {
                        if let Some(mut child) = lock.take() {
                            let _ = child.kill();
                            println!("Engine sidecar terminated.");
                        }
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
