"""
ml_best_params.py — Parameter Optimizer node to find the best iteration based on custom weights.
"""
from registry import NodeProcessor, vision_node

@vision_node(
    type_id='ml_best_params',
    label='Parameter Optimizer',
    category='Machine Learning',
    icon='Target',
    description="Tracks training metrics and calculates the best epoch based on user-defined weights.",
    dynamic_inputs=True,
    inputs=[
        {'id': 'counter', 'color': 'scalar', 'label': 'Counter'},
        {'id': 'metrics_dict', 'color': 'dict', 'label': 'Metrics Dict'},
    ],
    outputs=[
        {'id': 'best_step',     'color': 'scalar', 'label': 'Best Step'},
        {'id': 'best_values',   'color': 'dict',   'label': 'Best Values'},
    ],
    params=[
        {'id': 'reset', 'label': 'Reset History', 'type': 'trigger', 'default': 0},
        {'id': 'port_labels', 'label': 'Port Labels Mapping', 'type': 'string', 'default': '{}'},
    ],
)
class MLBestParamsNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.history = {}       # dict: step_key (int) -> {metric_name: float/str}
        self.current_counter = 0.0

    def process(self, inputs: dict, params: dict) -> dict:
        # Check if reset was triggered
        if int(params.get('reset', 0)) == 1:
            self.history = {}
            self.current_counter = 0.0
            return {
                'best_step': 0.0,
                'best_values': {},
                'counter': 0.0,
                'current_values': {},
                'best_step_values': {}
            }

        import json
        port_labels = {}
        port_labels_str = params.get('port_labels', '{}')
        try:
            port_labels = json.loads(port_labels_str)
        except Exception:
            pass

        current_vals = {}

        # Iterate over all inputs to extract values and unpack dictionaries
        for k, val in inputs.items():
            if k == 'counter' or val is None:
                continue

            # Look up label from port_labels
            label = None
            if k in port_labels:
                label = port_labels[k]
            else:
                for pid, plabel in port_labels.items():
                    if pid.endswith(k) or k.endswith(pid):
                        label = plabel
                        break
            metric_name = label or k.split('__')[-1]

            # If the input value is a dictionary (from any port), unpack it
            if isinstance(val, dict):
                current_vals[metric_name] = '__dict__'
                for sub_k, sub_v in val.items():
                    try:
                        current_vals[str(sub_k)] = float(sub_v)
                    except (ValueError, TypeError):
                        pass
            else:
                # If it's a scalar value, map it to its port label or key name
                try:
                    current_vals[metric_name] = float(val)
                except (ValueError, TypeError):
                    pass

        # Parse weights and active states from params for each metric
        weights = {}
        for key in current_vals.keys():
            # A key is active by default (if not explicitly disabled)
            is_active = params.get(f'active_{key}', True)
            if isinstance(is_active, str):
                is_active = is_active.lower() == 'true'
            elif isinstance(is_active, (int, float)):
                is_active = bool(is_active)

            if is_active:
                # Default weight is 0.0
                weight_val = params.get(f'weight_{key}', 0.0)
                try:
                    weights[key] = float(weight_val)
                except (ValueError, TypeError):
                    weights[key] = 0.0

        # Retrieve scalar counter value
        counter_input = inputs.get('counter')
        if counter_input is not None:
            try:
                self.current_counter = float(counter_input)
                step_key = int(self.current_counter)
            except (ValueError, TypeError):
                step_key = 0

            # Record/update metrics for the current step
            if current_vals:
                if step_key not in self.history:
                    self.history[step_key] = {}
                self.history[step_key].update(current_vals)

        # Calculate scores and find the best step index
        best_step_idx = 0
        best_score = -float('inf')

        for step_key, step_data in self.history.items():
            score = 0.0
            for k, val in step_data.items():
                if val == '__dict__':
                    continue
                weight = weights.get(k, 0.0)
                score += weight * val
            if score > best_score:
                best_score = score
                best_step_idx = step_key

        best_step_values = self.history.get(best_step_idx, {})

        return {
            'best_step': float(best_step_idx),
            'best_values': best_step_values,
            'counter': self.current_counter,
            'current_values': current_vals,
            'best_step_values': best_step_values
        }
