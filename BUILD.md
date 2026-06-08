# Building VisionNodes for distribution (macOS & Windows)

Goal: a **double-clickable `.app`/`.dmg` (macOS) or `.exe`/`.msi` (Windows)** that students run without installing
Python or any dependency. A self-contained Python interpreter (with torch, sam2,
opencv, rasterio…) is bundled inside the app.

## How it works

```
VisionNodes.app/Contents/Resources/
  resources/pyengine/bin/python3   ← self-contained CPython + all deps
  resources/engine/engine.py       ← the WebSocket engine + plugins
```

At launch (release build), `src-tauri/src/main.rs` spawns:
```
Resources/pyengine/bin/python3  Resources/engine/engine.py
```
The interpreter is a [python-build-standalone](https://github.com/astral-sh/python-build-standalone)
build (fetched via `uv`), which is **fully relocatable** — unlike a normal `venv`,
which hard-codes absolute paths and breaks when moved into a `.app`.

App Sandbox is **disabled** (see `src-tauri/entitlements.plist`): a sandboxed app
cannot spawn the embedded interpreter nor reach the user's files, both of which
VisionNodes needs.

## Prerequisites

### macOS
- Apple Silicon or Intel (build on same arch you distribute to)
- [`uv`](https://docs.astral.sh/uv/): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Rust toolchain + Node (already used for dev)

### Windows
- Windows 10+ (x64)
- [`uv`](https://docs.astral.sh/uv/): Run in PowerShell:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- Rust toolchain + Node (already used for dev)
- Visual Studio Build Tools (Rust/Tauri requirement on Windows)

## Build steps

### macOS

```bash
# 1. Bundle the self-contained Python engine into src-tauri/resources/
#    (slow: downloads CPython + installs torch/sam2/rasterio — several GB)
./scripts/build_pyengine.sh

# 2. Build the .app + .dmg
npm run tauri build
```

Output:
```
src-tauri/target/release/bundle/macos/VisionNodes.app
src-tauri/target/release/bundle/dmg/VisionNodes_0.1.0_aarch64.dmg
```

### Windows

```powershell
# 1. Bundle the self-contained Python engine into src-tauri/resources/
#    (slow: downloads CPython + installs torch/sam2/rasterio — several GB)
powershell -ExecutionPolicy Bypass -File scripts/build_pyengine.ps1

# 2. Build the .exe + .msi
npm run tauri build
```

Output:
```
src-tauri/target/release/bundle/msi/VisionNodes_0.1.0_x64_en-US.msi
src-tauri/target/release/VisionNodes.exe
```

**Re-run `build_pyengine.sh` (macOS) or `.ps1` (Windows) only when `engine/requirements.txt` changes; otherwise just `npm run tauri build`.**

## Bundle size

torch alone is ~2–3 GB. Expect a 3–6 GB `.app`. To trim, edit
`engine/requirements.txt` (e.g. CPU-only torch) before step 1, or prune unused
heavy plugins.

## Code signing & security

### macOS: Gatekeeper

The build is **ad-hoc signed** by default. On a student's Mac, first launch shows
"unidentified developer". Options, easiest first:

1. **Right-click → Open** once (per machine) to bypass Gatekeeper.
2. **Remove quarantine** after copying to /Applications:
   ```bash
   xattr -dr com.apple.quarantine /Applications/VisionNodes.app
   ```
3. **Proper signing + notarization** (no warning) — requires an Apple Developer
   account ($99/yr). Set in `tauri.conf.json` → `bundle.macOS.signingIdentity`
   and run `xcrun notarytool`. Overkill for a classroom; options 1–2 suffice.

### Windows: SmartScreen

First run may show "Windows protected your PC" → **More info → Run anyway**.
No extra steps needed; this is standard for new unsigned apps on Windows.

## Troubleshooting

- **App opens, nodes don't work** → engine didn't launch. Run the app from a
  terminal to see logs:
  ```bash
  /Applications/VisionNodes.app/Contents/MacOS/VisionNodes
  ```
  Look for `Bundled engine launched:` vs `Bundled engine not found`.
- **"python3 quit unexpectedly"** → a native dep failed to load. Confirm
  `disable-library-validation` is in entitlements and the app was rebuilt.
- **Verify the bundled engine standalone:**
  ```bash
  ./src-tauri/resources/pyengine/bin/python3 ./src-tauri/resources/engine/engine.py
  # then connect the dev frontend, or check it binds ws://localhost:8765
  ```

## Dev vs release

- **Dev** (`npm run studio`): uses your local `.venv` + `engine/` directly. The
  bundled `resources/` are ignored. Nothing changes in your dev workflow.
- **Release** (`npm run tauri build`): uses the bundled `resources/pyengine` (macOS & Windows).

## Cross-platform notes

- **Relative paths in engine/**: All plugin code uses relative imports from registry —
  works identically on macOS/Windows (Rust and Python both normalize path separators).
- **WebSocket**: Binds `127.0.0.1:8765` on both platforms.
- **Home directory**: `~/.vnstudio/` resolves correctly via Python on both OS.
- **Resource loading** (images, fonts): All relative paths work cross-platform.
