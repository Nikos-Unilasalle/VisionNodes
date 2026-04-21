# 👁️ VisionNodes Studio

**VisionNodes** is a high-performance, node-based development environment designed for rapid prototyping of **Computer Vision (CV)** and **Artificial Intelligence (AI)** algorithms. 

It provides a modern, interactive "Studio" experience where you can chain complex models, scientific analysis tools, and custom logic in real-time.

<p align="center">
  <img src="./src/assets/logo.svg" width="180" alt="VisionNodes Logo">
</p>

---

## 🌟 Core Pillars

- ⚡ **Real-Time Execution**: See the impact of every parameter change instantly on the video flux.
- 🧠 **AI-Native**: Deep integration with state-of-the-art models like YOLOv11 and MediaPipe.
- 🧪 **Scientific Precision**: Built-in tools for quantitative analysis (Watershed, Marker Analysis, Statistics).
- 🛠️ **Zero-Friction Extensibility**: Add custom Python nodes or dynamic plugins by simply dropping a file.
- 🎨 **Visual Programming**: Powered by ReactFlow for a sleek, responsive, and intuitive graph interface.

---

## 🚀 Key Features & Models

### 🧠 Modern AI & Tracking
VisionNodes comes pre-loaded with industry-standard AI capabilities:
- **Object Detection**: YOLOv11 (Ultralytics) for robust, high-speed multi-class detection.
- **Human Sensing**: MediaPipe integration for **Face Mesh**, **Hand Tracking**, and **Pose Estimation**.
- **Robust Tracking**: 
  - **SORT**: Simple Online and Realtime Tracking for high-speed ID persistence.
  - **DeepSORT**: Advanced tracking with CNN visual embeddings to handle occlusions.
- **Tracker Visualization**: Customizable trails, ID labels, and historic trajectories.

### 📊 Scientific & Quantitative Analysis
Move beyond simple detection to real scientific data extraction:
- **Watershed Analysis**: Advanced segmentation for separating touching or overlapping objects.
- **Marker Analysis**: Automatically extracts coordinates, area/surface (px), and intensity for every segmented island.
- **Universal Monitor**: Real-time counter and scalar display for any connected data stream.
- **Scientific Plotter**: Live graphing of numerical data (brightness, object counts, areas) with history buffers.

### 🛠️ Custom Logic & Scripting
- **Python Script Node**: Write custom logic directly in the UI. 
  - **Persistent State**: Use the `state` dictionary to store data between frames (e.g., cumulative counters).
  - **Syntax Highlighting**: Modern Python editor with real-time feedback.
- **Math & Strings**: Complete suite of boolean, arithmetic, and string manipulation nodes.
- **Coord Splitter/Combine**: Seamlessly convert between dictionary objects and raw scalars.

### 🎨 Drawing & Visuals
- **Dynamic Overlays**: Layer text, points, lines, and polygons over your vision results.
- **Draw Text**: Native OpenCV text rendering with dynamic variable injection.
- **Blend Modes**: Alpha compositing and advanced blending for multi-layer masks.

---

## 📂 Examples Library

VisionNodes includes a built-in library of templates to get you started:
- **Pedestrian Counter**: YOLO + DeepSORT + Cumulative Python Counter.
- **OCR Scanner**: Tesseract-based reading with EAST text detection.
- **Interactive Painter**: Hand landmark tracking used as a virtual brush.
- **Cell Segmenter**: Scientific workflow using Watershed to count segmented cells.
- **Ghost Trail**: Background subtraction combined with temporal blending.

---

## 🛠️ Developer Guide: Creating Custom Nodes

VisionNodes uses a **Dynamic Plugin System**. Any `.py` file placed in `engine/plugins/` is automatically discovered.

### Plugin Example: `engine/plugins/my_node.py`
```python
from __main__ import vision_node, NodeProcessor

@vision_node(
    type_id='my_filter', label='My Custom Filter', category='cv', icon='Zap',
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}]
)
class MyNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        # Your OpenCV / AI logic here
        return {'main': img}
```

---

## 🤝 Fork & Contribute

VisionNodes is an open-source project designed to grow with the community. We highly encourage you to:

1. 🍴 **Fork this repository** to create your own custom nodes and workflows.
2. 🐛 **Open Issues** for bugs or feature requests (like new model integrations).
3. 🚀 **Submit Pull Requests** to improve the core engine or add to the plugin library.

Whether you are a researcher, a hobbyist, or a pro developer, your contributions help make VisionNodes the most powerful visual tool for AI Vision.

---

## 📦 Tech Stack
- **Frontend**: React, ReactFlow, Vite, Tailwind CSS.
- **Backend Engine**: Python 3.10+, FastAPI (WebSockets), OpenCV, PyTorch, MediaPipe.
- **Desktop**: Rust & Tauri for native performance and OS integration.

---

## 📜 License
Developed for educational and research purposes. Free to use under the **MIT License**.
