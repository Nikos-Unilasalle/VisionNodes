from registry import vision_node, NodeProcessor

@vision_node(
    type_id="data_list_selector",
    label="List Selector",
    category='util',
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
    category='util',
    icon="Scissors",
    description="Splits an {x, y} coordinate dictionary into two separate values.",
    inputs=[{"id": "coord", "color": "dict"}],
    outputs=[{"id": "x", "color": "scalar"}, {"id": "y", "color": "scalar"}]
)
class CoordSplitterNode(NodeProcessor):
    def process(self, inputs, params):
        c = inputs.get('coord')
        if not c or not isinstance(c, dict): return {"x": 0, "y": 0}
        return {"x": c.get('x', 0), "y": c.get('y', 0)}

@vision_node(
    type_id="data_coord_combine",
    label="Coord Combine",
    category='util',
    icon="PlusSquare",
    description="Combines two separate values into a single {x, y} coordinate dictionary.",
    inputs=[{"id": "x", "color": "scalar"}, {"id": "y", "color": "scalar"}],
    outputs=[{"id": "coord", "color": "dict"}]
)
class CoordCombineNode(NodeProcessor):
    def process(self, inputs, params):
        return {"coord": {"x": inputs.get('x', 0), "y": inputs.get('y', 0)}}
