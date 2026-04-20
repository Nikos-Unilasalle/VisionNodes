from __main__ import vision_node, NodeProcessor
import csv
import time
import os

@vision_node(
    type_id='util_csv_export',
    label='CSV Export',
    category='out',
    icon='Database',
    description="Expote les données vers un fichier CSV. Un nouveau fichier est créé à chaque activation.",
    inputs=[
        {'id': 'val_1', 'color': 'any'},
        {'id': 'val_2', 'color': 'any'},
        {'id': 'val_3', 'color': 'any'},
        {'id': 'val_4', 'color': 'any'},
        {'id': 'val_5', 'color': 'any'},
        {'id': 'val_6', 'color': 'any'},
        {'id': 'val_7', 'color': 'any'},
        {'id': 'val_8', 'color': 'any'}
    ],
    outputs=[],
    params=[
        {'id': 'record', 'label': 'Recording', 'type': 'toggle', 'default': False},
        {'id': 'filename', 'label': 'Base Name', 'type': 'string', 'default': 'capture'},
        {'id': 'path', 'label': 'Folder Path', 'type': 'string', 'default': 'exports'},
        {'id': 'auto_timestamp', 'label': 'Auto Timestamp', 'type': 'bool', 'default': True}
    ]
)
class CSVExportNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.active_file = None
        self.last_record_status = False
        self.file_initialized = False

    def process(self, inputs, params):
        record = params.get('record', False)
        
        # Front montant : création d'un nouveau fichier
        if record and not self.last_record_status:
            base_name = params.get('filename', 'capture')
            export_dir = params.get('path', 'exports')
            auto_time = params.get('auto_timestamp', True)
            
            # Gestion du dossier
            if not os.path.exists(export_dir):
                try:
                    os.makedirs(export_dir)
                except Exception as e:
                    print(f"CSV Export Error: Cannot create dir {export_dir} -> {e}")
                    export_dir = "." # Fallback
            
            # Nom du fichier
            ts = f"_{int(time.time())}" if auto_time else ""
            self.active_file = os.path.join(export_dir, f"{base_name}{ts}.csv")
            self.file_initialized = False
            
        self.last_record_status = record
        
        if not record or self.active_file is None:
            return {}
            
        current_time = time.time()
        
        # Collecte des 8 valeurs
        vals = [current_time]
        header = ['timestamp']
        for i in range(1, 9):
            key = f'val_{i}'
            vals.append(inputs.get(key))
            header.append(key)
        
        try:
            mode = 'a' if self.file_initialized else 'w'
            with open(self.active_file, mode, newline='') as f:
                writer = csv.writer(f)
                if not self.file_initialized:
                    writer.writerow(header)
                    self.file_initialized = True
                
                row = []
                for v in vals:
                    if v is None:
                        row.append("")
                    elif isinstance(v, (int, float)):
                        row.append(f"{v:.6f}")
                    else:
                        row.append(str(v))
                writer.writerow(row)
        except Exception as e:
            print(f"Erreur d'écriture CSV: {e}")
            
        return {}
