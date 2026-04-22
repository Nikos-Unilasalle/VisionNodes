import json

with open('galets.vn', 'r') as f:
    galets = json.load(f)

# Change "Marble Analysis" to "Marker Analysis" in the new nodes
for n in galets['nodes']:
    if n.get('data', {}).get('label') == 'Marble Analysis':
        n['data']['label'] = 'Marker Analysis'

# Create formatted JS representations
nodes_js = json.dumps(galets['nodes'], indent=6).replace('\n', '\n      ')
edges_js = json.dumps(galets['edges'], indent=6).replace('\n', '\n      ')

new_example = f"""  {{
    name: "Galets Segmenter",
    description: "Segmente chaque galet avec watershed : seuillage Otsu, nettoyage morphologique, transform distance, filtrage des marqueurs par aire et analyse.",
    nodes: {nodes_js},
    edges: {edges_js}
  }}"""

with open('src/data/examples.ts', 'r') as f:
    content = f.read()

start_marker = 'name: "Marble Segmenter"'
# Find the start of the object {
start_idx = content.rfind('  {', 0, content.find(start_marker))
# Find the end of the object
# It's the last element in the array, so we can just look for the last '  }' before '];\n'
end_idx = content.find('  }', content.find(start_marker)) + 3

new_content = content[:start_idx] + new_example + content[end_idx:]

with open('src/data/examples.ts', 'w') as f:
    f.write(new_content)

print("Examples updated successfully")
