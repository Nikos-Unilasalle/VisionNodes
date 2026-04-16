from __main__ import vision_node, NodeProcessor
import csv
import time

@vision_node(
    type_id='util_csv_export',
    label='CSV Export',
    category='util',
    icon='Database',
    inputs=[
        {'id': 'val_1', 'color': 'any'},
        {'id': 'val_2', 'color': 'any'},
        {'id': 'val_3', 'color': 'any'},
        {'id': 'val_4', 'color': 'any'}
    ],
    outputs=[],
    params=[
        {'id': 'record', 'min': 0, 'max': 1, 'step': 1, 'default': 0}
    ]
)
class CSVExportNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.filename = None
        self.file_initialized = False
        self.last_record_status = False

    def process(self, inputs, params):
        record = int(params.get('record', 0)) == 1
        
        # Détection du front montant pour créer un nouveau fichier
        if record and not self.last_record_status:
            self.filename = f"export_{int(time.time())}.csv"
            self.file_initialized = False
            
        self.last_record_status = record
        
        if not record or self.filename is None:
            return {}
            
        current_time = time.time()
        
        vals = [
            current_time,
            inputs.get('val_1'),
            inputs.get('val_2'),
            inputs.get('val_3'),
            inputs.get('val_4')
        ]
        
        mode = 'a' if self.file_initialized else 'w'
        try:
            with open(self.filename, mode, newline='') as f:
                writer = csv.writer(f)
                if not self.file_initialized:
                    writer.writerow(['timestamp', 'val_1', 'val_2', 'val_3', 'val_4'])
                    self.file_initialized = True
                
                row = []
                for v in vals:
                    if isinstance(v, float):
                        row.append(f"{v:.4f}")
                    elif isinstance(v, (dict, list)):
                        row.append(str(v))
                    elif v is None:
                        row.append("")
                    else:
                        row.append(str(v))
                writer.writerow(row)
        except Exception as e:
            print(f"Erreur d'écriture CSV: {e}")
            
        return {}
