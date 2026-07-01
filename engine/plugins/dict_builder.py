from registry import NodeProcessor, vision_node


@vision_node(
    type_id="dict_builder",
    label="Build Dict",
    category="data",
    icon="Package",
    description=(
        "Assemble a dictionary from multiple scalar inputs. Keys are auto-labelled "
        "from the connected source and can be renamed in the inspector."
    ),
    dynamic_inputs=True,
    inputs=[],
    outputs=[{"id": "dict", "color": "dict"}],
    params=[],
)
class DictBuilderNode(NodeProcessor):
    """Collect every connected input into one dict, keyed by (renamed) input name."""

    def process(self, inputs, params):
        out = {}
        for key, value in inputs.items():
            if key == "raw_frame" or value is None:
                continue
            name = params.get(f"name_{key}")
            name = str(name).strip() if name not in (None, "") else key
            out[name] = value
        return {"dict": out}
