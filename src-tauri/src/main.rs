// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;
use tauri::Manager;

#[allow(dead_code)]
enum ChildProcess {
    Std(std::process::Child),
    Sidecar(tauri_plugin_shell::process::CommandChild),
}

struct EngineProcess(Mutex<Option<ChildProcess>>);

fn main() {
    // On Linux/Wayland, WebKitGTK's DMABUF renderer often yields a blank white
    // window. Disable it before the webview is created. (`npm run studio` sets
    // the same flag for dev; this covers packaged AppImage/deb builds.)
    #[cfg(target_os = "linux")]
    if std::env::var_os("WEBKIT_DISABLE_DMABUF_RENDERER").is_none() {
        std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");
    }

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_fs::init())
        .setup(|app| {
            #[cfg(not(debug_assertions))]
            {
                // Launch the bundled, self-contained Python engine from the app
                // Resources (built by scripts/build_pyengine.sh or .ps1, see BUILD.md):
                //   macOS:   Resources/pyengine/bin/python3  Resources/engine/engine.py
                //   Windows: Resources/pyengine/Scripts/python.exe  Resources/engine/engine.py
                let resource_dir = app
                    .path()
                    .resource_dir()
                    .expect("failed to resolve resource dir");

                #[cfg(target_os = "windows")]
                let python_path = resource_dir.join("resources/pyengine/Scripts/python.exe");
                #[cfg(not(target_os = "windows"))]
                let python_path = resource_dir.join("resources/pyengine/bin/python3");

                let engine_path = resource_dir.join("resources/engine/engine.py");

                let mut launched = false;
                if python_path.exists() && engine_path.exists() {
                    match std::process::Command::new(&python_path).arg(&engine_path).spawn() {
                        Ok(child) => {
                            app.manage(EngineProcess(Mutex::new(Some(ChildProcess::Std(child)))));
                            println!("Bundled engine launched: {:?}", python_path);
                            launched = true;
                        }
                        Err(e) => println!("Failed to spawn bundled engine: {e}"),
                    }
                } else {
                    println!(
                        "Bundled engine not found (python={:?} exists={}, engine={:?} exists={}).",
                        python_path, python_path.exists(), engine_path, engine_path.exists()
                    );
                }

                if !launched {
                    // Last-resort fallback: a local .venv next to the binary (source builds).
                    let root = std::env::current_dir().unwrap();
                    let venv_path = root.join(".venv/bin/python3");
                    let local_engine = root.join("engine/engine.py");
                    if venv_path.exists() && local_engine.exists() {
                        if let Ok(child) = std::process::Command::new(venv_path).arg(local_engine).spawn() {
                            app.manage(EngineProcess(Mutex::new(Some(ChildProcess::Std(child)))));
                            println!("Local fallback engine launched.");
                        }
                    } else {
                        println!("Warning: No engine found. The app will start but nodes won't work.");
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
                if window.label() != "main" { return; }
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
