Planned Roadmap (Next Steps)

- **Latency Monitoring**: Formatted the `ms` latency counter in the unit inspector to 2 decimal places to prevent UI "jitter".
- **Graph Layout**: Implemented an initial `fitView` logic to ensure the node graph is centered on load.
- **Persistence**: Implemented a browser-native "Save" button using `Blob` and `URL.createObjectURL` as a robust fallback.
- **Native Save/Load**: Bridge the existing `saveGraph` Javascript logic with the native `writeTextFile` API now that the plugin is configured.
- **Modular UI**: Re-implement the "Analysis Data" window as a floating, draggable panel using `Panel` from `reactflow`.
- *Drawing Tools**: Fix the `Draw Text` node which currently fails to render text overlays correctly.
- **Plugin Schema System**: Stabilize the dynamic category loading from `pluginSchemas` to avoid UI crashes when no plugins are loaded.

