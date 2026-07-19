// VNPad — LAN remote-control server for VNStudio.
//
// An Android/tablet "stream-deck" connects over the local network and sends
// `add_node` / `set_param` commands. This module owns a small WebSocket server
// bound to the LAN, a per-session pairing token, and a QR payload the desktop
// UI shows so the phone can pair without typing an IP.
//
// The engine (127.0.0.1:8765) is never exposed: commands land here, are
// authenticated, then re-emitted to the React frontend as a `vnpad-command`
// Tauri event. The frontend already knows how to apply that command shape.

use std::sync::Mutex;

use futures_util::{Sink, SinkExt, Stream, StreamExt};
use serde::Serialize;
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::broadcast;
use tokio_tungstenite::tungstenite::Message;

/// LAN port the pad server listens on. Distinct from the engine (8765).
pub const VNPAD_PORT: u16 = 8770;

/// Token character set — unambiguous (no 0/O/1/I) so it survives manual entry.
const TOKEN_ALPHABET: &[u8] = b"ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const TOKEN_LEN: usize = 8;

/// Shared server state managed by Tauri.
pub struct VNPadState {
    /// Per-session pairing secret. Regenerated every launch.
    pub token: String,
    /// The menu's node list (type/label/category) pushed from the frontend, so
    /// the pad editor can offer a name-based picker. Defaults to `[]`.
    pub schemas: Mutex<Value>,
    /// Broadcasts a ready-to-send `schemas` message whenever the list updates,
    /// so already-connected pads refresh without reconnecting.
    pub schema_tx: broadcast::Sender<String>,
}

impl VNPadState {
    pub fn new() -> Self {
        let (schema_tx, _) = broadcast::channel(8);
        Self {
            token: gen_token(),
            schemas: Mutex::new(Value::Array(vec![])),
            schema_tx,
        }
    }
}

/// Build the wire message that carries the node list to a pad.
fn schemas_message(nodes: &Value) -> String {
    json!({ "type": "schemas", "nodes": nodes }).to_string()
}

impl Default for VNPadState {
    fn default() -> Self {
        Self::new()
    }
}

fn gen_token() -> String {
    use rand::Rng;
    let mut rng = rand::thread_rng();
    (0..TOKEN_LEN)
        .map(|_| TOKEN_ALPHABET[rng.gen_range(0..TOKEN_ALPHABET.len())] as char)
        .collect()
}

/// Pairing payload returned to the desktop UI for QR display.
#[derive(Serialize)]
pub struct Pairing {
    pub ip: String,
    pub port: u16,
    pub token: String,
    /// Self-contained SVG of the QR encoding `{ip, port, token}`.
    pub qr_svg: String,
}

/// Command: return the pairing info + a ready-to-render QR SVG.
#[tauri::command]
pub fn vnpad_pairing(state: tauri::State<VNPadState>) -> Result<Pairing, String> {
    let ip = local_ip_address::local_ip()
        .map_err(|e| format!("no LAN IP found: {e}"))?
        .to_string();

    let payload = json!({ "ip": ip, "port": VNPAD_PORT, "token": state.token });
    let code = qrcode::QrCode::new(payload.to_string().as_bytes())
        .map_err(|e| format!("QR encode failed: {e}"))?;
    let qr_svg = code
        .render::<qrcode::render::svg::Color>()
        .min_dimensions(240, 240)
        .quiet_zone(true)
        .build();

    Ok(Pairing {
        ip,
        port: VNPAD_PORT,
        token: state.token.clone(),
        qr_svg,
    })
}

/// Command: frontend pushes the current node schemas so the pad editor can
/// browse node types without touching the engine directly.
#[tauri::command]
pub fn vnpad_set_schemas(state: tauri::State<VNPadState>, schemas: Value) {
    let message = schemas_message(&schemas);
    if let Ok(mut cached) = state.schemas.lock() {
        *cached = schemas;
    }
    // Push to any already-connected pads. Err just means no pad is listening.
    let _ = state.schema_tx.send(message);
}

/// Spawn the LAN WebSocket server on its own thread + runtime so it stays
/// isolated from Tauri's event loop.
pub fn start_server(app: AppHandle) {
    std::thread::spawn(move || {
        let rt = match tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
        {
            Ok(rt) => rt,
            Err(e) => {
                eprintln!("[VNPad] runtime build failed: {e}");
                return;
            }
        };

        rt.block_on(async move {
            let listener = match TcpListener::bind(("0.0.0.0", VNPAD_PORT)).await {
                Ok(l) => l,
                Err(e) => {
                    eprintln!("[VNPad] bind 0.0.0.0:{VNPAD_PORT} failed: {e}");
                    return;
                }
            };
            println!("[VNPad] listening on 0.0.0.0:{VNPAD_PORT}");

            loop {
                match listener.accept().await {
                    Ok((stream, addr)) => {
                        let app = app.clone();
                        tokio::spawn(async move {
                            if let Err(e) = handle_conn(stream, app).await {
                                eprintln!("[VNPad] connection {addr} ended: {e}");
                            }
                        });
                    }
                    Err(e) => eprintln!("[VNPad] accept error: {e}"),
                }
            }
        });
    });
}

/// One client connection: authenticate, then relay commands.
async fn handle_conn(stream: TcpStream, app: AppHandle) -> Result<(), String> {
    let ws = tokio_tungstenite::accept_async(stream)
        .await
        .map_err(|e| format!("handshake failed: {e}"))?;
    let (mut tx, mut rx) = ws.split();

    let (token, mut schema_rx) = {
        let state = app.state::<VNPadState>();
        (token_of(&state), state.schema_tx.subscribe())
    };

    // Phase 1: authenticate. Only a valid hello proceeds.
    if !authenticate(&mut tx, &mut rx, &token).await? {
        return Ok(());
    }

    // On connect, immediately push the current node list so the editor's picker
    // is populated without an extra round-trip.
    let cached = current_schemas(&app);
    if !is_empty_array(&cached) {
        let _ = tx.send(Message::text(schemas_message(&cached))).await;
    }

    // Phase 2: relay commands from the pad and schema updates to the pad.
    loop {
        tokio::select! {
            incoming = rx.next() => {
                let Some(frame) = incoming else { break };
                let frame = frame.map_err(|e| e.to_string())?;
                if !frame.is_text() { continue; }
                let text = frame.into_text().map_err(|e| e.to_string())?;
                let v: Value = match serde_json::from_str(&text) {
                    Ok(v) => v,
                    Err(_) => continue,
                };
                match v.get("type").and_then(Value::as_str).unwrap_or("") {
                    "get_schemas" => {
                        let schemas = current_schemas(&app);
                        let _ = tx.send(Message::text(schemas_message(&schemas))).await;
                    }
                    "add_node" | "set_param" => {
                        // Re-emit to the React frontend, which applies it via addNode.
                        let _ = app.emit("vnpad-command", &v);
                        let _ = tx.send(Message::text(r#"{"type":"ack"}"#)).await;
                    }
                    "ping" => { let _ = tx.send(Message::text(r#"{"type":"pong"}"#)).await; }
                    _ => {}
                }
            }
            update = schema_rx.recv() => {
                match update {
                    Ok(msg) => { let _ = tx.send(Message::text(msg)).await; }
                    Err(broadcast::error::RecvError::Lagged(_)) => {
                        // Missed some updates; re-send the latest full list.
                        let schemas = current_schemas(&app);
                        let _ = tx.send(Message::text(schemas_message(&schemas))).await;
                    }
                    Err(broadcast::error::RecvError::Closed) => {}
                }
            }
        }
    }

    Ok(())
}

fn token_of(state: &VNPadState) -> String {
    state.token.clone()
}

fn current_schemas(app: &AppHandle) -> Value {
    app.state::<VNPadState>()
        .schemas
        .lock()
        .map(|s| s.clone())
        .unwrap_or_else(|_| Value::Array(vec![]))
}

fn is_empty_array(v: &Value) -> bool {
    v.as_array().map(|a| a.is_empty()).unwrap_or(true)
}

/// Read frames until a valid `hello` arrives (returns true) or the client sends
/// a bad token / disconnects (returns false).
async fn authenticate(
    tx: &mut (impl Sink<Message, Error = tokio_tungstenite::tungstenite::Error> + Unpin),
    rx: &mut (impl Stream<Item = Result<Message, tokio_tungstenite::tungstenite::Error>> + Unpin),
    token: &str,
) -> Result<bool, String> {
    while let Some(frame) = rx.next().await {
        let frame = frame.map_err(|e| e.to_string())?;
        if !frame.is_text() {
            continue;
        }
        let text = frame.into_text().map_err(|e| e.to_string())?;
        let v: Value = match serde_json::from_str(&text) {
            Ok(v) => v,
            Err(_) => continue,
        };
        let ok = v.get("type").and_then(Value::as_str) == Some("hello")
            && v.get("token").and_then(Value::as_str) == Some(token);
        if ok {
            let _ = tx.send(Message::text(r#"{"type":"welcome"}"#)).await;
            return Ok(true);
        }
        let _ = tx.send(Message::text(r#"{"type":"error","reason":"auth"}"#)).await;
        return Ok(false);
    }
    Ok(false)
}
