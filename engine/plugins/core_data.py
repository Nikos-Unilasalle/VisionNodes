from registry import vision_node, NodeProcessor

@vision_node(
    type_id="data_list_selector",
    label="List Selector",
    category='utility',
    icon="List",
    description="Extracts a specific item from a list by its index.",
    inputs=[{"id": "list", "color": "list"}],
    outputs=[{"id": "item", "color": "any"}],
    params=[{"id": "index", "label": "Index", "type": "int", "default": 0}]
)
class ListSelectorNode(NodeProcessor):
    def process(self, inputs, params):
        lst = inputs.get('list')
        if not lst or not isinstance(lst, list): return {"item": None}
        idx = int(params.get('index', 0))
        if 0 <= idx < len(lst): return {"item": lst[idx]}
        return {"item": None}

@vision_node(
    type_id="data_coord_splitter",
    label="Coord Splitter",
    category="data",
    icon="Box",
    description="Splits a coordinate dictionary into 4 scalar values.",
    inputs=[{"id": "data", "color": "coords"}],
    outputs=[
        {"id": "x", "color": "scalar"},
        {"id": "y", "color": "scalar"},
        {"id": "w", "color": "scalar"},
        {"id": "h", "color": "scalar"}
    ]
)
class CoordSplitterNode(NodeProcessor):
    def process(self, inputs, params):
        d = inputs.get('data')
        if not isinstance(d, dict): return {"x": None, "y": None, "w": None, "h": None}
        return {"x": d.get("xmin"), "y": d.get("ymin"), "w": d.get("width"), "h": d.get("height")}

@vision_node(
    type_id="data_coord_combine",
    label="Coord Combine",
    category="data",
    icon="Box",
    description="Combines 4 scalar values into a coordinate dictionary.",
    inputs=[
        {"id": "x", "color": "scalar"},
        {"id": "y", "color": "scalar"},
        {"id": "w", "color": "scalar"},
        {"id": "h", "color": "scalar"}
    ],
    outputs=[{"id": "dict_out", "color": "coords"}]
)
class CoordCombineNode(NodeProcessor):
    def process(self, inputs, params):
        x = inputs.get("x")
        y = inputs.get("y")
        if x is None or y is None:
            return {"dict_out": None}
            
        return {"dict_out": {
            "xmin": float(x),
            "ymin": float(y),
            "width": float(inputs.get("w") or 0.0),
            "height": float(inputs.get("h") or 0.0),
        }}
