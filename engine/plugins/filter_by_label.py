from __main__ import vision_node, NodeProcessor

@vision_node(
    type_id='util_filter_label',
    label='Label Filter',
    category='util',
    icon='Search',
    description="Filters a list of detections to keep only specific labels (e.g., 'person').",
    inputs=[{'id': 'list_in', 'color': 'list'}],
    outputs=[
        {'id': 'list_out', 'color': 'list'},
        {'id': 'item_out', 'color': 'dict'},
        {'id': 'labels_list', 'color': 'list'}
    ],
    params=[
        {'id': 'query', 'label': 'Label Tag', 'default': 'person', 'type': 'string'}
    ]
)
class LabelFilterNode(NodeProcessor):
    def process(self, inputs, params):
        items = inputs.get('list_in')
        if not isinstance(items, list): return {"list_out": [], "item_out": None, "labels_list": []}
        
        # Extract all unique labels present in the input list
        all_labels = sorted(list(set([str(item.get('label', 'unknown')) for item in items if isinstance(item, dict)])))
        
        query = str(params.get('query', 'person')).lower()
        filtered = [item for item in items if isinstance(item, dict) and str(item.get('label', '')).lower() == query]
        
        display = f"Found: {', '.join(all_labels)}" if all_labels else "No labels found"
        
        return {
            "list_out": filtered,
            "item_out": filtered[0] if filtered else None,
            "labels_list": all_labels,
            "display_text": display
        }
