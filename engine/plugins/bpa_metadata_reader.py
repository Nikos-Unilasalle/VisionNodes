from registry import vision_node, NodeProcessor, send_notification
import re
import os

_PATTERNS = {
    'room_temp':      r'Room Temp\s*=\s*([\d.]+)',
    'room_humidity':  r'Room Humidity\s*=\s*([\d.]+)',
    'hematocrit':     r'Hematocrit\s*=\s*([\d.]+)',
    'blood_volume':   r'Blood Volume\s*=\s*([\d.]+)',
    'dowel_angle':    r'Dowel Angle\s*:\s*([\d.]+)',
    'dowel_height':   r'Dowel height station\s*:\s*([\d.]+)',
    'moment_arm':     r'Moment arm\s*:\s*([\d.]+)',
    'bungees':        r'# of Rubber Bungees\s*:\s*([\d.]+)',
    'image_scale_px': r'([\d.]+)\s*pixel/cm',
    'x_o':            r'x_o\s*=\s*([\d.]+)',
    'y_o':            r'y_o\s*=\s*([\d.]+)',
    'z_o':            r'z_o\s*=\s*([\d.]+)',
    'x_t':            r'x_[tp]\s*=\s*([\d.]+)',
    'y_t':            r'y_[tp]\s*=\s*([\d.]+)',
    'z_t':            r'z_[tp]\s*=\s*([\d.]+)',
}

_STR_PATTERNS = {
    'blood_supply':    r'Blood supply\s*=\s*(.+)',
    'target_position': r'Target position\s*:\s*(.+)',
}


def _parse_txt(path: str) -> dict:
    with open(path, 'r', errors='replace') as f:
        text = f.read()

    result = {}
    for key, pat in _PATTERNS.items():
        m = re.search(pat, text, re.IGNORECASE)
        result[key] = float(m.group(1)) if m else None

    for key, pat in _STR_PATTERNS.items():
        m = re.search(pat, text, re.IGNORECASE)
        result[key] = m.group(1).strip() if m else None

    # Double-origin case (e.g. HP_62): x_o line may have two values
    m_double = re.search(r'x_o\s*=\s*([\d.]+)\s*cm,\s*and\s*([\d.]+)', text, re.IGNORECASE)
    if m_double:
        result['x_o'] = float(m_double.group(1))
        result['x_o2'] = float(m_double.group(2))
        result['double_origin'] = True
    else:
        result['x_o2'] = None
        result['double_origin'] = False

    return result


@vision_node(
    type_id='bpa_metadata_reader',
    label='BPA Metadata Reader',
    category='forensics',
    icon='FileText',
    description="Parses Attinger bloodstain pattern metadata (.txt). Outputs origin/target coords, blood properties, and image path.",
    inputs=[],
    outputs=[
        {'id': 'meta',         'color': 'dict',   'label': 'Meta'},
        {'id': 'image_path',   'color': 'string', 'label': 'Image Path'},
        {'id': 'sample_id',    'color': 'string', 'label': 'Sample ID'},
        {'id': 'x_o',         'color': 'scalar', 'label': 'X origin (cm)'},
        {'id': 'y_o',         'color': 'scalar', 'label': 'Y origin (cm)'},
        {'id': 'z_o',         'color': 'scalar', 'label': 'Z origin (cm)'},
        {'id': 'x_t',         'color': 'scalar', 'label': 'X target (cm)'},
        {'id': 'y_t',         'color': 'scalar', 'label': 'Y target (cm)'},
        {'id': 'z_t',         'color': 'scalar', 'label': 'Z target (cm)'},
        {'id': 'dowel_angle', 'color': 'scalar', 'label': 'Dowel Angle (°)'},
        {'id': 'hematocrit',  'color': 'scalar', 'label': 'Hematocrit (%)'},
        {'id': 'blood_volume','color': 'scalar', 'label': 'Blood Vol (ml)'},
        {'id': 'room_temp',   'color': 'scalar', 'label': 'Temp (°C)'},
        {'id': 'room_humidity','color': 'scalar','label': 'Humidity (%)'},
    ],
    params=[
        {'id': 'dataset_path', 'type': 'string', 'default': '', 'label': 'Dataset Folder'},
        {'id': 'sample_id',    'type': 'string', 'default': 'HP_19', 'label': 'Sample ID'},
    ]
)
class BPAMetadataReaderNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._cache_key = None
        self._cache_data = None

    def process(self, inputs, params):
        dataset_path = params.get('dataset_path', '').strip()
        sample_id    = params.get('sample_id', '').strip()

        null = {
            'meta': None, 'image_path': None, 'sample_id': sample_id,
            'x_o': None, 'y_o': None, 'z_o': None,
            'x_t': None, 'y_t': None, 'z_t': None,
            'dowel_angle': None, 'hematocrit': None, 'blood_volume': None,
            'room_temp': None, 'room_humidity': None,
        }

        if not dataset_path or not sample_id:
            return null

        sample_dir = os.path.join(dataset_path, sample_id)
        txt_path   = os.path.join(sample_dir, f'{sample_id}.txt')
        img_path   = os.path.join(sample_dir, f'{sample_id}.jpg')

        if not os.path.isfile(txt_path):
            send_notification(f'BPA: not found — {txt_path}', level='error', notif_id='bpa_meta')
            return null

        cache_key = txt_path
        if cache_key != self._cache_key:
            try:
                self._cache_data = _parse_txt(txt_path)
                self._cache_key  = cache_key
                d = self._cache_data
                send_notification(
                    f'BPA: {sample_id} — origin ({d["x_o"]}, {d["y_o"]}, {d["z_o"]}) cm'
                    + (' [DOUBLE]' if d['double_origin'] else ''),
                    notif_id='bpa_meta'
                )
            except Exception as e:
                send_notification(f'BPA parse error: {e}', level='error', notif_id='bpa_meta')
                return null

        d = self._cache_data
        return {
            'meta':          {**d, 'sample_id': sample_id, 'txt_path': txt_path, 'img_path': img_path},
            'image_path':    img_path if os.path.isfile(img_path) else None,
            'sample_id':     sample_id,
            'x_o':           d['x_o'],
            'y_o':           d['y_o'],
            'z_o':           d['z_o'],
            'x_t':           d['x_t'],
            'y_t':           d['y_t'],
            'z_t':           d['z_t'],
            'dowel_angle':   d['dowel_angle'],
            'hematocrit':    d['hematocrit'],
            'blood_volume':  d['blood_volume'],
            'room_temp':     d['room_temp'],
            'room_humidity': d['room_humidity'],
        }
