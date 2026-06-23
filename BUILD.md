# Building VisionNodes for distribution (macOS, Windows & Linux)

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

### Linux
- x86_64 (build on the oldest glibc you need to support)
- [`uv`](https://docs.astral.sh/uv/): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Rust toolchain + Node, plus the Tauri system deps from `INSTALL.md`
  (`libwebkit2gtk-4.1-dev`, `libgtk-3-dev`, `patchelf`…)

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

### Linux

```bash
# 1. Bundle the self-contained Python engine into src-tauri/resources/
#    (build_pyengine.sh is plain bash + uv — works on Linux as on macOS)
./scripts/build_pyengine.sh

# 2. Build the AppImage + .deb
npm run tauri build
```

Output:
```
src-tauri/target/release/bundle/appimage/VNStudio_0.1.0_amd64.AppImage
src-tauri/target/release/bundle/deb/VNStudio_0.1.0_amd64.deb
```

> The release binary forces `WEBKIT_DISABLE_DMABUF_RENDERER=1` itself (see
> `src-tauri/src/main.rs`), so the packaged app won't show the Wayland white screen.

**Re-run `build_pyengine.sh` (macOS/Linux) or `.ps1` (Windows) only when `engine/requirements.txt` changes; otherwise just `npm run tauri build`.**

## Runtime dependencies (user overlay)

The bundled interpreter's `site-packages` is **read-only**, so nodes that pull
extra packages on demand (`ensure_packages` — Copernicus Marine, Sentinel Hub,
diffusers, user-dropped plugins…) can't install into the bundle. In a packaged
build the engine detects this and installs into a writable overlay instead:

```
~/.vnstudio/lib/python3.x/site-packages   (Linux/macOS, via PYTHONUSERBASE)
```

This dir is added to `sys.path` at engine startup, so freshly installed packages
import without a restart. `pip --user` resolves against the bundled packages, so
heavy deps already in the bundle (torch, rasterio…) are reused, not redownloaded.
`--break-system-packages` is passed because python-build-standalone ships a
PEP 668 `EXTERNALLY-MANAGED` marker. In **dev** (`.venv`, writable) none of this
applies — installs go to the venv as before.

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
