# VisionNodes

VisionNodes is a professional-grade node-based interface for real-time OpenCV image processing.

## Architecture
- **Desktop Shell**: Tauri (Rust)
- **Node Engine**: Python 3.11+ with OpenCV & WebSockets
- **Frontend**: React, React Flow, TypeScript, Tailwind CSS
- **Communication**: High-frequency WebSockets for 60fps video streaming

## Prerequisites
1. **Rust**: [Install Rust](https://rustup.rs/)
2. **Node.js**: [Install Node.js](https://nodejs.org/)
3. **Python 3.11+**:
   ```bash
   pip install opencv-python numpy websockets
   ```

## Getting Started

### 1. Install Dependencies
```bash
npm install
```

### 2. Run in Development
```bash
npm run tauri dev
```

The application will automatically:
- Start the Python engine sidecar.
- Launch the Tauri window.
- Connect the frontend to the engine via WebSocket.

## Features
- **Topological Solver**: Ensures nodes are executed in the correct dependency order.
- **Real-time Processing**: adjust Canny thresholds or Blur kernels and see the results instantly on the live stream.
- **Blender-like UI**: Professional dark theme with industrial design aesthetics.
- **Extensible**: Add new nodes in `engine/engine.py` and `src/components/Nodes.tsx`.
