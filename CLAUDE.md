# VNStudio — Claude context file (auto-loaded each session)

## What is this project?

VNStudio is a **node-based computer vision studio** built with:
- **Frontend**: Tauri v2 + React 18 + ReactFlow + TypeScript + Tailwind CSS
- **Backend**: Python WebSocket engine (`engine/engine.py`) running as a sidecar
- **Communication**: WebSocket on port 8765, JSON messages, base64-encoded frames at ~30fps

The user builds visual pipelines by connecting nodes (webcam input → filters → output display). The Python engine executes the graph on each frame.

## Key architecture

```
src/
  App.tsx                     — main component (~1850 lines), multi-canvas state
  context/NodesDataContext.ts — React Context for live frame data (avoids 30fps re-renders)
  hooks/
    useVisionEngine.ts        — WebSocket client, frame data, notifications, exponential backoff
    useHistory.ts             — per-canvas undo/redo (50 snapshots, Cmd+Z / Cmd+Shift+Z)
  components/
    Nodes.tsx                 — all ReactFlow node components, use useNodeData() for live data
    NodeInspectorPanel.tsx    — right-panel inspector, extracted from App.tsx
  types/
    NodeSchema.ts             — TypedDict-style TS interfaces: ParamSpec, PortSpec, NodeSchema, NodeData, VNNode

engine/
  engine.py                   — WebSocket server, plugin loader, graph executor
  registry.py                 — single source of truth: NODE_SCHEMAS, NODE_CLASS_REGISTRY,
                                vision_node decorator, NodeProcessor ABC, topological_sort (Kahn)
  plugins/                    — 67+ plugins, all import from registry (NOT __main__)
  tests/                      — pytest suite (registry, csv_export, logic_python)

src-tauri/
  capabilities/default.json  — Tauri permissions (fs ops scoped to $HOME/**)
```

## Multi-canvas (scenes)

4 canvases (c1–c4), each has `{ id, name, nodes, edges, filePath }`. `setNodes`/`setEdges` always operate on the active canvas via `activeCanvasIdRef`.

## File management (per canvas)

- **Save**: overwrites known `filePath`, dialog if none
- **Save +**: Blender-style incremental (`name.vn` → `name 01.vn` + `name 02.vn`)
- **New/Open**: triggers "unsaved changes?" dialog if scene has content
- **My Projects**: work directory stored in localStorage, lists `.vn` files

## Performance pattern

`nodesData` (30fps WebSocket updates) lives in `NodesDataContext`, NOT in `nodesWithData` memo. Node components call `useNodeData(useNodeId())` to subscribe directly. Inspector uses `selectedNodeLiveData` useMemo.

## Keyboard shortcuts (Mac)

| Shortcut | Action |
|---|---|
| Cmd+Z | Undo |
| Cmd+Shift+Z | Redo |
| Cmd+C / Cmd+V | Copy / Paste nodes |
| Cmd+A | Select all |
| Cmd+S | Save |
| Cmd+O | Open |
| Cmd+M | Toggle add-node menu |
| Cmd+F | Fit view |
| Cmd+Shift+F | Fullscreen |

## Python plugin contract

```python
@vision_node(
    type_id='my_node', label='My Node', category='cv', icon='Zap',
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[{'id': 'threshold', 'type': 'int', 'default': 128, 'min': 0, 'max': 255}]
)
class MyNode(NodeProcessor):
    def process(self, inputs, params):
        ...
        return {'main': result}
```

Param types: `int`, `float`, `number`, `string`, `bool`, `toggle`, `enum`, `trigger`, `code`, `color`

## Tests

```bash
pytest engine/tests/          # Python: registry, csv_export, logic_python
npm test                      # Vitest: nodesDataContext, project-serialization
```

## Dev server

```bash
npm run studio   # kills ports 8765/1420, installs if needed, launches tauri dev
```

## Dynamic-input nodes

Three node types use dynamic ports — ports that appear on connection and grow one by one:

| Node | Handle color | "factory" handle id | Port id strategy |
|---|---|---|---|
| `sci_plotter` | any (white) | `any__DYNAMIC_NEW_HANDLE` | unique: `${color}__${idx}_${random}` |
| `export_py` | any (white) | `any__DYNAMIC_NEW_HANDLE` | unique: `${color}__${idx}_${random}` |
| `output_display` | image (blue) | `image__DYNAMIC_NEW_HANDLE` | unique: `image_${idx}_${random}` |
| `group_output` | any (white) | `any__DYNAMIC_NEW_HANDLE` | unique: `${color}__${idx}_${random}` |

### How it works (frontend)

**`StyledHandle`** prepends color to id: `handleId = '${color}__${id}'`. A handle with `id="DYNAMIC_NEW_HANDLE"` and `color="any"` registers as `any__DYNAMIC_NEW_HANDLE`.

**`onConnect`** (App.tsx): for each dynamic node type, when `params.targetHandle.endsWith('__DYNAMIC_NEW_HANDLE')`:
1. Generates a unique `portId` using `${color}__${idx}_${randomString}`.
2. Creates `newPort = { id: portId, color, label }` and pushes to node's `data.ports` via `setViewNodes`.
3. Creates edge with the specific `targetHandle: portId` via `setViewEdges`.
4. If an user connects to an **occupied** handle, the system automatically treats it as a connection to the factory and creates a new port instead of replacing the existing one.

**`isValidConnection`** (App.tsx): previously blocked occupied ports, now just checks for color compatibility. `onConnect` handles the "create vs replace" logic.

**Engine side**: `th = e.get('targetHandle','').split('__')[-1]` strips color prefix. `sci_plotter` reads all `inputs` keys as series names.

### Handle position: always pixels, never percentages

ReactFlow measures handle positions via `getBoundingClientRect()`. Percentage `top` (e.g. `55%`) can resolve to 0 if parent height isn't committed.

**Fix**: use pixel positions (`45px + i * 32px`).

### Rules when modifying dynamic nodes

- "factory" handle id = `DYNAMIC_NEW_HANDLE`.
- `onConnect` must check `params.targetHandle.endsWith('__DYNAMIC_NEW_HANDLE')` or handle occupancy.
- Disconnecting an edge should (ideally) remove the corresponding port.
- Keep `Nodes.tsx` and `App.tsx` in sync regarding these IDs.

## Recent major work (April 2026)

- Phase 1: NodesDataContext perf fix, exponential WS backoff, CSV persistent handle, async ML model loading
- Phase 2: registry.py plugin decoupling, NodeInspectorPanel extraction, typed contracts (TS + Python TypedDicts)
- Phase 3: exec() sandboxing (logic_python), pytest + vitest suites, dead file cleanup
- Undo/Redo: useHistory hook, per-canvas history
- File management: incremental save, work directory panel, unsaved-changes dialog

## User preferences

- Communicates in French
- Caveman mode active (terse responses, no filler)
- Mac user (use Cmd not Ctrl in docs/shortcuts)
