from registry import vision_node, NodeProcessor


@vision_node(
    type_id='geo_grain_report',
    label='Grain Report',
    category='geology',
    icon='BarChart2',
    description="Displays grain population statistics as a dashboard. Connect the 'Report' output of Grain Population Stats.",
    inputs=[
        {'id': 'report', 'color': 'dict', 'label': 'Report (from Grain Population Stats)'},
    ],
    outputs=[
        {'id': 'report', 'color': 'dict', 'label': 'Report'},
    ],
    params=[]
)
class GeoGrainReportNode(NodeProcessor):
    def process(self, inputs, params):
        return {'report': inputs.get('report') or {}}
