# Rock Classifier — third-party model

`model_SA.py` is vendored from **zhh-pixel/rock**:
- Repo: https://github.com/zhh-pixel/rock
- Paper: *Nature Scientific Reports* 2025, https://doi.org/10.1038/s41598-025-03706-0
- Architecture: EfficientNet-B0 + Spatial Attention (SA), trained with the
  Lion optimizer and DiffuseMix augmentation.

Weights (`model_aug_SA_lion.pth`, 5 classes) auto-download at runtime from the
upstream repo into `~/.vnstudio/models/`.

## License

The upstream project states: **"intended for academic research purposes only.
For commercial use, please contact the authors."** Respect that license when
using this node.

## Class names

The repo ships no `class_indices.json`, so the 5 output class indices have no
public semantic names. Set the real rock-type names (in the dataset's
alphabetical folder order) via the node's *Class Names* parameter.
