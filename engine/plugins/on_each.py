from registry import vision_node, NodeProcessor

@vision_node(
    type_id='util_on_each',
    label='On Each',
    category='data',
    icon='Layers',
    description="Applies a graphic template to every item in a coordinates list.",
    inputs=[
        {'id': 'list_in', 'color': 'list'},
        {'id': 'template', 'color': 'dict'}
    ],
    outputs=[{'id': 'list_out', 'color': 'list'}],
    params=[
        {'id': 'text_source', 'label': 'Text Content', 'type': 'enum', 
         'options': ['Template Default', 'ID / Index', 'Label', 'Area', 'Score', 'Coordinates'], 'default': 0}
    ]
)
class OnEachNode(NodeProcessor):
    def process(self, inputs, params):
        list_in = inputs.get('list_in')
        template = inputs.get('template')
        
        if not isinstance(list_in, list) or not isinstance(template, dict):
            return {"list_out": []}
            
        text_source = int(params.get('text_source', 0))
        results = []
        
        for i, item in enumerate(list_in):
            if not isinstance(item, dict): continue
            
            # 1. Extract Position from various formats
            x, y = None, None
            
            # Case 1: Direct x/y (Marker Analysis or similar)
            if 'x' in item and 'y' in item:
                x, y = item['x'], item['y']
            # Case 2: center dictionary
            elif 'center' in item and isinstance(item['center'], dict):
                x, y = item['center'].get('x'), item['center'].get('y')
            # Case 3: Bounding box (xmin/ymin/width/height)
            elif 'xmin' in item and 'ymin' in item:
                x = item['xmin'] + item.get('width', 0) / 2
                y = item['ymin'] + item.get('height', 0) / 2
            # Case 4: Points list
            elif 'pts' in item and len(item['pts']) > 0:
                # Handle list of [x, y]
                pt = item['pts'][0]
                x, y = pt[0], pt[1]
            # Case 5: Landmarks list
            elif 'landmarks' in item and len(item['landmarks']) > 0:
                lm = item['landmarks'][0]
                x, y = lm['x'], lm['y']
                
            if x is None or y is None: continue
            
            # 2. Clone Template and Update Position
            new_graphic = template.copy()
            new_graphic['pts'] = [[float(x), float(y)]]
            new_graphic['relative'] = True
            
            # 3. Dynamic Text handling
            # If the template is text or has a label, we can override it
            if new_graphic.get('shape') == 'text' or 'text' in new_graphic or 'label' in new_graphic:
                if text_source == 1: # ID / Index
                    new_graphic['text'] = str(item.get('id', i))
                    new_graphic['label'] = str(item.get('id', i))
                elif text_source == 2: # Label
                    txt = str(item.get('label', 'obj'))
                    new_graphic['text'] = txt
                    new_graphic['label'] = txt
                elif text_source == 3: # Area
                    val = item.get('area', 0)
                    txt = f"{val:.0f}"
                    new_graphic['text'] = txt
                    new_graphic['label'] = txt
                elif text_source == 4: # Score
                    val = item.get('score', 0)
                    txt = f"{val*100:.0f}%"
                    new_graphic['text'] = txt
                    new_graphic['label'] = txt
                elif text_source == 5: # Coordinates
                    txt = f"({x:.2f}, {y:.2f})"
                    new_graphic['text'] = txt
                    new_graphic['label'] = txt
            
            results.append(new_graphic)
            
        return {"list_out": results}
