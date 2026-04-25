from registry import vision_node, NodeProcessor

@vision_node(
    type_id="data_group_dicts",
    label="Group Dicts",
    category="util",
    icon="Layers",
    description="Groups multiple dictionaries (e.g. data outputs) into a single list of dictionaries.",
    inputs=[
        {"id": "dict1", "color": "dict"},
        {"id": "dict2", "color": "dict"},
        {"id": "dict3", "color": "dict"},
        {"id": "dict4", "color": "dict"},
    ],
    outputs=[
        {"id": "main", "color": "list"}
    ],
    params=[]
)
class GroupDictsNode(NodeProcessor):
    def process(self, inputs, params):
        grouped = []
        for i in range(1, 5):
            d = inputs.get(f"dict{i}")
            if isinstance(d, dict):
                grouped.append(d)
                
        return {"main": grouped if len(grouped) > 0 else None}
