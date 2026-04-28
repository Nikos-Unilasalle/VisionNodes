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

def group_by_category(nodes):
    categories = {}
    # Preferred order and labels for categories
    CAT_ORDER = [
        ("src", "Sources"),
        ("cv", "Computer Vision"),
        ("mask", "Masks"),
        ("geom", "Geometry"),
        ("track", "Tracking"),
        ("features", "Features"),
        ("analysis", "Analysis"),
        ("visualize", "Visualizers"),
        ("draw", "Drawing"),
        ("util", "Utilities"),
        ("math", "Mathematics"),
        ("strings", "Strings"),
        ("logic", "Logic"),
        ("blend", "Blending"),
        ("out", "Output"),
        ("canvas", "Canvas")
    ]
    
    cat_map = {id: label for id, label in CAT_ORDER}
    
    for node in nodes:
        cat_id = node.get("category", "custom")
        if cat_id not in categories:
            categories[cat_id] = {
                "id": cat_id,
                "label": cat_map.get(cat_id, cat_id.capitalize()),
                "nodes": []
            }
        
        # Deduplicate nodes by type_id
        if not any(n["type"] == node["type"] for n in categories[cat_id]["nodes"]):
            categories[cat_id]["nodes"].append(node)
            
    # Sort categories based on CAT_ORDER
    sorted_cats = []
    seen_cats = set()
    for cat_id, label in CAT_ORDER:
        if cat_id in categories:
            sorted_cats.append(categories[cat_id])
            seen_cats.add(cat_id)
            
    for cat_id in categories:
        if cat_id not in seen_cats:
            sorted_cats.append(categories[cat_id])
            
    # Sort nodes within categories alphabetically
    for cat in sorted_cats:
        cat["nodes"].sort(key=lambda x: x.get("label", ""))
        
    return sorted_cats

if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    nodes = scan_files(project_root)
    grouped = group_by_category(nodes)
    
    output_path = os.path.join(project_root, "website", "src", "data", "nodes.json")
    with open(output_path, "w") as f:
        json.dump(grouped, f, indent=2)
    
    print(f"Successfully generated {output_path}")
    print(f"Total nodes: {len(nodes)}")
    print(f"Categories: {len(grouped)}")
