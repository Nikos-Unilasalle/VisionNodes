// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::{AppHandle, Manager};

enum ChildProcess {
    Std(std::process::Child),
    Sidecar(tauri_plugin_shell::process::CommandChild),
}

struct EngineProcess(Mutex<Option<ChildProcess>>);

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_fs::init())
        .setup(|app| {
            #[cfg(not(debug_assertions))]
            {
                use tauri_plugin_shell::ShellExt;
                let sidecar_cmd = app.shell().sidecar("engine-bin");
                
                let mut launched = false;
                if let Ok(cmd) = sidecar_cmd {
                    if let Ok((_rx, child)) = cmd.spawn() {
                        app.manage(EngineProcess(Mutex::new(Some(ChildProcess::Sidecar(child)))));
                        println!("Sidecar engine launched.");
                        launched = true;
                    }
                }

                if !launched {
                    println!("Sidecar 'engine-bin' not found or failed to launch. Trying local venv fallback...");
                    // Fallback to local venv if available (useful for portable source builds)
                    let mut root = std::env::current_dir().unwrap();
                    // If we are inside the .app bundle, we might need to look elsewhere, 
                    // but for a simple build folder, this works.
                    let venv_path = root.join(".venv/bin/python3");
                    let engine_path = root.join("engine/engine.py");

                    if venv_path.exists() && engine_path.exists() {
                        if let Ok(child) = std::process::Command::new(venv_path).arg(engine_path).spawn() {
                            app.manage(EngineProcess(Mutex::new(Some(ChildProcess::Std(child)))));
                            println!("Local fallback engine launched.");
                        }
                    } else {
                        println!("Warning: No engine found (sidecar or local venv). The app will start but nodes won't work.");
                    }
                }
            }

            #[cfg(debug_assertions)]
            {
                // Fallback to script-based launch for development
                let mut root = std::env::current_dir().unwrap();
                if root.ends_with("src-tauri") {
                    root.pop();
                }
                let venv_path = root.join(".venv/bin/python3");
                let engine_path = root.join("engine/engine.py");

                println!("Dev Engine: {:?}", engine_path);

                if venv_path.exists() && engine_path.exists() {
                    let child = std::process::Command::new(venv_path)
                        .arg(engine_path)
                        .spawn()
                        .expect("Failed to start dev engine");
                    app.manage(EngineProcess(Mutex::new(Some(ChildProcess::Std(child)))));
                } else {
                    println!("Warning: Dev engine or venv not found. Sidecar might be required.");
                }
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // Kill the sidecar when closing
                if let Some(state) = window.try_state::<EngineProcess>() {
                    if let Ok(mut lock) = state.0.lock() {
                        if let Some(child) = lock.take() {
                            match child {
                                ChildProcess::Std(mut c) => {
                                    let _ = c.kill().ok();
                                }
                                ChildProcess::Sidecar(c) => {
                                    let _ = c.kill().ok();
                                }
                            }
                            println!("Engine terminated.");
                        }
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
