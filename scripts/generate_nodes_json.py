import os
import json
import ast
import re

def parse_vision_node_decorator(decorator):
    if not isinstance(decorator, ast.Call):
        return None
    
    metadata = {}
    
    # Process positional arguments if any (unlikely for our decorator)
    # Process keyword arguments
    for keyword in decorator.keywords:
        key = keyword.arg
        value = keyword.value
        
        if key == "type_id":
            metadata["type"] = value.value
        elif isinstance(value, ast.Constant):
            metadata[key] = value.value
        elif isinstance(value, ast.List):
            items = []
            for elt in value.elts:
                if isinstance(elt, ast.Dict):
                    dict_val = {}
                    for k, v in zip(elt.keys, elt.values):
                        if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                            dict_val[k.value] = v.value
                        elif isinstance(k, ast.Constant) and isinstance(v, ast.List):
                             dict_val[k.value] = [e.value for e in v.elts if isinstance(e, ast.Constant)]
                    items.append(dict_val)
                elif isinstance(elt, ast.Constant):
                    items.append(elt.value)
            metadata[key] = items
    
    return metadata

def scan_files(root_dir):
    all_nodes = []
    
    search_paths = [
        os.path.join(root_dir, "engine", "engine.py"),
        os.path.join(root_dir, "engine", "plugins")
    ]
    
    for path in search_paths:
        if os.path.isfile(path):
            files = [path]
        else:
            files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(".py")]
            
        for file_path in files:
            with open(file_path, "r") as f:
                try:
                    tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            for decorator in node.decorator_list:
                                if isinstance(decorator, ast.Call) and getattr(decorator.func, "id", "") == "vision_node":
                                    metadata = parse_vision_node_decorator(decorator)
                                    if metadata:
                                        all_nodes.append(metadata)
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}")
                    
    return all_nodes

def group_by_category(nodes, ts_path):
    import re
    
    # Parse categories.ts
    with open(ts_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    cats_config = []
    current_cat = None
    
    for line in content.split('\n'):
        cat_match = re.search(r"{\s*id:\s*'([^']+)',\s*label:\s*'([^']+)'", line)
        if cat_match:
            current_cat = {
                'id': cat_match.group(1),
                'label': cat_match.group(2),
                'nodes': []
            }
            cats_config.append(current_cat)
            
        # Also capture description and label from TS to override python defaults
        type_match = re.search(r"type:\s*'([^']+)',\s*label:\s*'([^']+)'(?:,\s*description:\s*'([^']*)')?", line)
        if type_match and current_cat:
            current_cat['nodes'].append({
                'type': type_match.group(1),
                'ts_label': type_match.group(2),
                'ts_desc': type_match.group(3) if type_match.group(3) else ""
            })
            
    # Now build the final grouped structure
    # Map nodes by type for quick lookup
    node_map = { n["type"]: n for n in nodes if "type" in n }
    seen_types = set()
    
    sorted_cats = []
    
    for cat in cats_config:
        cat_group = {
            "id": cat["id"],
            "label": cat["label"],
            "nodes": []
        }
        
        for n_info in cat["nodes"]:
            t = n_info["type"]
            if t in node_map and t not in seen_types:
                seen_types.add(t)
                node_data = node_map[t].copy()
                # Override label, description and CATEGORY with the TS ones for perfect consistency
                node_data["category"] = cat["id"]
                if n_info["ts_label"]:
                    node_data["label"] = n_info["ts_label"]
                if n_info["ts_desc"]:
                    node_data["description"] = n_info["ts_desc"]
                cat_group["nodes"].append(node_data)
                
        if cat_group["nodes"]:
            sorted_cats.append(cat_group)
            
    # Nodes that are in python but not in TS categories
    # We can optionally group them under 'Uncategorized' or just ignore them.
    # We will put them in a 'developer' category at the end if they exist.
    mapped_types = { n_info["type"] for cat in cats_config for n_info in cat["nodes"] }
    unmapped = [n for n in nodes if n.get("type") not in mapped_types]
    
    if unmapped:
        unmapped.sort(key=lambda x: x.get("label", ""))
        sorted_cats.append({
            "id": "unmapped",
            "label": "Other / Internal",
            "nodes": unmapped
        })
        
    return sorted_cats

if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ts_path = os.path.join(project_root, "src", "data", "categories.ts")
    nodes = scan_files(project_root)
    grouped = group_by_category(nodes, ts_path)
    
    output_path = os.path.join(project_root, "website", "src", "data", "nodes.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(grouped, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully generated {output_path}")
    print(f"Total nodes in Python: {len(nodes)}")
    print(f"Mapped categories: {len(grouped)}")
