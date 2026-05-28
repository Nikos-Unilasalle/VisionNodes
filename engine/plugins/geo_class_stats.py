"""
geo_class_stats.py — Per-class area statistics from a categorical raster.

Takes a classified geo dict (from geo_rf_classifier, geo_time_align, or
any integer-class raster) and computes per-class pixel count and area in
hectares, using the raster's affine transform for accurate area.

Outputs a labeled DataFrame (class_value, class_name, pixels, area_ha,
fraction_pct) and a colorized bar chart image. Feed the DataFrame into
ml_bar_chart, ml_scatter_plot, or export_csv.
"""
from __future__ import annotations
import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_class_stats'

# WorldCover default class names for convenience
_WC_DEFAULT = '10=Trees,20=Shrubland,30=Grassland,40=Cropland,50=Built-up,' \
              '60=Bare/sparse,70=Snow/ice,80=Water,90=Wetland,95=Mangroves,100=Moss'

_MPL_DARK = {
    'figure.facecolor':  '#161616',
    'axes.facecolor':    '#1e1e1e',
    'axes.edgecolor':    '#555555',
    'axes.labelcolor':   '#cccccc',
    'text.color':        '#cccccc',
    'xtick.color':       '#aaaaaa',
    'ytick.color':       '#aaaaaa',
    'grid.color':        '#333333',
    'grid.linestyle':    '--',
    'grid.linewidth':    0.5,
}


def _parse_class_map(s: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for item in s.split(','):
        item = item.strip()
        if '=' in item:
            k, v = item.split('=', 1)
            try:
                out[int(k.strip())] = v.strip()
            except ValueError:
                pass
    return out


def _get_pixel_area_m2(geo: dict) -> float:
    """Return pixel area in m². Handles Affine objects and list transforms."""
    transform = geo.get('transform')
    if transform is None:
        return 400.0  # fallback: 20 m × 20 m
    try:
        rx = abs(float(transform[0]))
        ry = abs(float(transform[4]))
        if rx < 0.01:   # degrees — approximate conversion
            rx *= 111_319.0
            ry *= 111_319.0
        return rx * ry
    except (IndexError, TypeError):
        return 400.0


def _fig_to_bgr(fig, dpi: int = 100) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    buf.close()
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img if img is not None else np.zeros((200, 420, 3), dtype=np.uint8)


@vision_node(
    type_id='geo_class_stats',
    label='Class Area Statistics',
    category='geography',
    icon='PieChart',
    description=(
        "Compute per-class pixel count and area (ha) from a categorical raster "
        "(classified geo dict). Outputs a labeled DataFrame with columns "
        "[class_value, class_name, pixels, area_ha, fraction_pct] and a "
        "bar chart image. Connect area_ha or fraction_pct columns to ml_bar_chart "
        "for publication-quality area comparison figures."
    ),
    inputs=[
        {'id': 'classification', 'color': 'geotiff', 'label': 'Classified raster'},
    ],
    outputs=[
        {'id': 'table',    'color': 'data',   'label': 'Stats DataFrame'},
        {'id': 'chart',    'color': 'image',  'label': 'Area bar chart'},
        {'id': 'summary',  'color': 'text',   'label': 'Text summary'},
    ],
    params=[
        {'id': 'class_names', 'type': 'string', 'default': _WC_DEFAULT,
         'label': 'Class names (value=name, comma-sep)'},
        {'id': 'exclude_zeros', 'type': 'bool', 'default': True,
         'label': 'Exclude class 0 (nodata)'},
        {'id': 'sort_by', 'type': 'enum',
         'options': ['Area descending', 'Class value', 'Name A→Z'],
         'default': 0, 'label': 'Sort by'},
        {'id': 'colormap', 'type': 'enum',
         'options': ['tab10', 'Set2', 'viridis', 'plasma', 'RdYlGn'],
         'default': 0, 'label': 'Colormap'},
        {'id': 'node_note', 'type': 'string', 'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=280, min_height=180,
)
class GeoClassStatsNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        geo = inputs.get('classification')
        if not isinstance(geo, dict) or 'bands' not in geo:
            send_notification('Class Stats: waiting for classified raster', notif_id=_NOTIF)
            return {}

        if not self.ensure_packages(['pandas'], notif_id=_NOTIF):
            return {}
        import pandas as pd

        bands = geo['bands']
        if bands.ndim == 3:
            class_map = bands[0].astype(np.int32)
        else:
            class_map = bands.astype(np.int32)

        pixel_area_m2 = _get_pixel_area_m2(geo)
        pixel_area_ha = pixel_area_m2 / 10_000.0
        total_pixels  = class_map.size

        # Parse params
        name_str      = str(params.get('class_names', _WC_DEFAULT))
        class_map_d   = _parse_class_map(name_str)
        exclude_zeros = bool(params.get('exclude_zeros', True))
        sort_idx      = int(params.get('sort_by', 0))
        cmap_options  = ['tab10', 'Set2', 'viridis', 'plasma', 'RdYlGn']
        cmap_idx      = int(params.get('colormap', 0))
        cmap_name     = cmap_options[cmap_idx] if cmap_idx < len(cmap_options) else 'tab10'

        # Count pixels per class
        unique, counts = np.unique(class_map, return_counts=True)
        rows: list[dict] = []
        for cls_val, cnt in zip(unique, counts):
            cv = int(cls_val)
            if exclude_zeros and cv == 0:
                continue
            name = class_map_d.get(cv, str(cv))
            area = float(cnt) * pixel_area_ha
            frac = float(cnt) / total_pixels * 100.0
            rows.append({
                'class_value': cv,
                'class_name':  name,
                'pixels':      int(cnt),
                'area_ha':     round(area, 2),
                'fraction_pct': round(frac, 3),
            })

        if not rows:
            send_notification('Class Stats: no classes found', level='warning', notif_id=_NOTIF)
            return {}

        df = pd.DataFrame(rows)

        # Sort
        if sort_idx == 0:
            df = df.sort_values('area_ha', ascending=False)
        elif sort_idx == 1:
            df = df.sort_values('class_value')
        else:
            df = df.sort_values('class_name')

        df = df.reset_index(drop=True)

        # Text summary
        summary_lines = [f"Pixel area: {pixel_area_m2:.0f} m² ({pixel_area_ha:.4f} ha)"]
        for _, row in df.iterrows():
            summary_lines.append(
                f"  {row['class_name']:20s} {row['area_ha']:>10.1f} ha  "
                f"({row['fraction_pct']:.2f}%)"
            )
        summary = '\n'.join(summary_lines)

        # Bar chart
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            n = len(df)
            fig_h = max(3.5, n * 0.45)
            fig, ax = plt.subplots(figsize=(7, fig_h))

            cmap_fn = plt.cm.get_cmap(cmap_name)
            colors = [cmap_fn(i / max(n - 1, 1)) for i in range(n)]

            bars = ax.barh(
                range(n), df['area_ha'].values,
                color=colors, alpha=0.85, edgecolor='none', height=0.65,
            )
            ax.set_yticks(range(n))
            ax.set_yticklabels(df['class_name'].tolist(), fontsize=8)
            ax.set_xlabel('Area (ha)')
            ax.set_title('Class area statistics', fontsize=10, pad=6)
            ax.grid(True, axis='x', alpha=0.4)
            ax.spines[['top', 'right']].set_visible(False)

            for bar, (_, row) in zip(bars, df.iterrows()):
                w = bar.get_width()
                ax.text(w + max(df['area_ha'].values) * 0.01,
                        bar.get_y() + bar.get_height() / 2,
                        f"{row['area_ha']:,.0f} ha  ({row['fraction_pct']:.1f}%)",
                        va='center', ha='left', fontsize=7, color='#aaaaaa')

            with plt.rc_context(_MPL_DARK):
                fig.patch.set_facecolor('#161616')
                ax.set_facecolor('#1e1e1e')
            fig.tight_layout()
            chart_img = _fig_to_bgr(fig, 100)
            plt.close(fig)
        except Exception as e:
            send_notification(f'Class Stats: chart error: {e}', level='warning', notif_id=_NOTIF)
            chart_img = np.full((200, 420, 3), 22, dtype=np.uint8)

        send_notification(
            f'Class Stats: {len(df)} classes  ·  '
            f'pixel={pixel_area_m2:.0f}m²  ·  '
            f'total={sum(df["area_ha"]):.0f} ha',
            progress=1.0, notif_id=_NOTIF,
        )

        return {'table': df, 'chart': chart_img, 'summary': summary}
