# VisionNodes Studio

VisionNodes is a node-based development environment for rapid prototyping of Computer Vision (CV) and AI algorithms. Built with React and powered by **OpenCV** and **MediaPipe**, it provides a modern and responsive interface for visual programming.

<p align="center">
  <img src="./src/assets/logo.svg" width="200" alt="VisionNodes Logo">
</p>

---

## Quick Installation

### 1. Prerequisites
- **Node.js** (v18+)
- **Python** (3.10+)

### 2. Setup & Dependencies
```bash
# Clone the repository
git clone https://github.com/Nikos-Unilasalle/VisionNodes.git
cd VisionNodes

# Install Frontend dependencies
npm install

# Setup Backend (Python virtual environment)
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install opencv-python mediapipe websockets numpy ultralytics
```

### 3. Running the Studio
To launch both the Python logic engine and the GUI in a single command:
```bash
npm run studio
```

### 4. Compiling a Standalone App
You can build a native desktop executable for your OS:
```bash
npm run tauri build
```

---

## Recent Features 🚀

### 📊 Advanced Scientific Analysis (Analysis Category)
VisionNodes now includes dedicated tools for quantitative data extraction:
- **Watershed Segmentation**: Separate complex or touching objects.
- **Marker Analysis**: Automatically calculate centroid (coordinates), surface (area), and ID for every segmented "island".
- **Statistics & Heatmaps**: Visualize real-time distributions and activity zones.

### 🔄 "On Each" Iterator & Dynamic Text
The **On Each** node allows powerful visualization loops:
- **Smart Overlay**: Repeat any graphic element (text, circle, rectangle) over a list of detections (YOLO, MediaPipe, or Marker Analysis).
- **Dynamic Variable Injection**: Automatically display IDs, Labels, Areas, or Confidence Scores at the center of each object.

### 🎨 Native Text Rendering
High-performance text rendering support via the OpenCV engine, accessible through the **Draw Text** node.

---

## Developer Guide: Creating Custom Nodes

VisionNodes uses a **Dynamic Plugin System**. You can add new features without touching the core engine or UI code.

### Plugin System
Any `.py` file placed in the `engine/plugins/` directory is automatically scanned and loaded at startup.

#### Node Structure Example:
Create a file `engine/plugins/my_filter.py`:

```python
from __main__ import vision_node, NodeProcessor
import cv2

@vision_node(
    type_id='my_unique_filter',    # Unique identifier
    label='Invert Colors',         # Display name in UI
    category='cv',                 # Category (cv, analysis, mask, util, visualize...)
    icon='Zap',                    # Lucide-React icon name
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'intensity', 'min': 0, 'max': 100, 'default': 50}
    ]
)
class InvertNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None}
        
        res = cv2.bitwise_not(img)
        return {'main': res}
```

### Handle Colors
Use these color IDs for connector compatibility:
- **`image`** (#3b82f6): Standard video flux (BGR).
- **`data` / `dict`** (#22c55e): Numerical objects or JSON dictionaries.
- **`list`** (#a855f7): Lists of detections (YOLO, MediaPipe).
- **`scalar`** (#eab308): Single numerical values.
- **`mask`** (#d1d5db): Binary masks (1-channel).
- **`flow`** (#ef4444): Optical Flow motion vectors.
- **`boolean`** (#22d3ee): Logic True/False values.
- **`any`** (#ffffff): Universal connector (accepts anything).

---

## Project Structure

```text
.
├── engine/              # Python Logic Engine (Core)
│   ├── engine.py        # Main logic & WebSocket server
│   └── plugins/         # Your custom nodes (.py)
├── src/                 # React Frontend source
│   ├── components/      # UI Node definitions
│   └── App.tsx          # Graph Logic management
├── src-tauri/           # Native Desktop integration (Rust/Tauri)
├── public/              # Static assets
└── package.json         # Node.js dependencies & scripts
```

---

## License
Developed for educational and research purposes. Free to use under the MIT License.
