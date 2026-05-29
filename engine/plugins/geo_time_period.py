from registry import vision_node, NodeProcessor

@vision_node(
    type_id='geo_time_period',
    label='Time Period',
    category='geography',
    icon='Calendar',
    description="Defines a time period (start and end dates) to share across geography nodes.",
    inputs=[],
    outputs=[
        {'id': 'date_start', 'color': 'string', 'label': 'Start Date'},
        {'id': 'date_end',   'color': 'string', 'label': 'End Date'},
    ],
    params=[
        {'id': 'date_start', 'label': 'Start Date (YYYY-MM-DD)', 'type': 'date', 'default': '2024-01-01'},
        {'id': 'date_end',   'label': 'End Date (YYYY-MM-DD)',   'type': 'date', 'default': '2024-06-01'},
    ]
)
class GeoTimePeriodNode(NodeProcessor):
    def process(self, inputs, params):
        date_start = str(params.get('date_start', '2024-01-01')).strip()
        date_end   = str(params.get('date_end', '2024-06-01')).strip()
        
        return {
            'date_start': date_start,
            'date_end': date_end
        }
