"""
BPA Top-Down View — vue du dessus en coordonnées pièce (plan XY).

Repère pièce (Attinger) :
  X = profondeur (perpendiculaire à la cible, +X = loin du mur)
  Y = horizontal le long de la cible
  Z = vertical (non représenté dans cette vue)

Contenu du rendu :
  - Rectangle bleu = surface de la cible (vue de dessus = trait vertical)
  - Croix orange  = projections des taches sur le plan cible (à X = x_t)
  - Point rouge   = origine estimée
  - Point vert    = origine GT (si disponible)
  - Lignes grises = quelques rayons de stringing (sous-échantillonnés)
  - Annotations   : distance X, erreur, nombre de taches
"""
from registry import vision_node, NodeProcessor
import numpy as np
import io

_NULL = {'view': None}

_MPL_OK = None


def _check_mpl():
    global _MPL_OK
    if _MPL_OK is None:
        try:
            import matplotlib
            matplotlib.use('Agg')
            _MPL_OK = True
        except ImportError:
            _MPL_OK = False
    return _MPL_OK


def _render(stains, px_per_cm, img_h_px,
            x_t, y_t, z_t,
            est_x, est_y, est_z,
            gt_x,  gt_y,  gt_z,
            width_cm, height_cm,
            n_rays, fig_w, fig_h, dark_theme):

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import cv2

    bg   = '#1e2330' if dark_theme else '#f8f8f8'
    fg   = '#e0e0e0' if dark_theme else '#222222'
    grid = '#2e3550' if dark_theme else '#cccccc'

    fig, ax = plt.subplots(figsize=(fig_w / 100, fig_h / 100), dpi=100)
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)

    # World limits: origin side + target side
    all_x = [x_t]
    if est_x is not None: all_x.append(est_x)
    if gt_x  is not None: all_x.append(gt_x)
    x_min = min(all_x) - 20
    x_max = max(all_x) + 20

    # Y span = target board width + margins
    y_center = y_t + width_cm / 2 if width_cm else (est_y or y_t or 0)
    y_span   = max(width_cm * 1.3 if width_cm else 120, 80)
    y_min    = y_center - y_span / 2
    y_max    = y_center + y_span / 2

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)

    # Grid
    ax.grid(True, color=grid, linewidth=0.4, alpha=0.6)
    ax.set_facecolor(bg)
    for spine in ax.spines.values():
        spine.set_edgecolor(grid)
    ax.tick_params(colors=fg, labelsize=7)
    ax.set_xlabel('X — profondeur (cm)', color=fg, fontsize=8)
    ax.set_ylabel('Y — horizontal (cm)', color=fg, fontsize=8)
    ax.set_title('Vue du dessus — plan XY', color=fg, fontsize=9, pad=6)

    # Target board (vertical line at x = x_t)
    board_y0 = y_t
    board_y1 = y_t + (width_cm or 80)
    ax.plot([x_t, x_t], [board_y0, board_y1],
            color='#4a9eff', linewidth=3, label='Cible', zorder=5)
    ax.text(x_t + 1, (board_y0 + board_y1) / 2, 'CIBLE',
            color='#4a9eff', fontsize=6, va='center', rotation=90, alpha=0.8)

    # Stain projections on target plane
    if stains:
        height_cm = img_h_px / px_per_cm
        world_y = [y_t + s['cx'] / px_per_cm for s in stains]
        ax.scatter([x_t] * len(world_y), world_y,
                   c='#ff9f40', s=8, alpha=0.6, zorder=4,
                   label=f'Taches (n={len(stains)})')

        # Sub-sampled stringing rays
        step = max(1, len(stains) // n_rays)
        for s in stains[::step]:
            wy = y_t + s['cx'] / px_per_cm
            # Ray from target toward estimated/GT origin
            target_x = est_x if est_x is not None else (gt_x or x_t + 60)
            ax.plot([x_t, target_x], [wy, est_y if est_y is not None else wy],
                    color='#888888', linewidth=0.4, alpha=0.4, zorder=2)

    # Estimated origin
    if est_x is not None and est_y is not None:
        ax.scatter([est_x], [est_y], c='#ff4444', s=120, zorder=7,
                   marker='*', label=f'Origine estimée ({est_x:.0f}, {est_y:.0f})')
        ax.annotate(f'Est.\n({est_x:.0f}, {est_y:.0f})',
                    (est_x, est_y), textcoords='offset points', xytext=(8, 6),
                    color='#ff4444', fontsize=6.5)

    # GT origin
    if gt_x is not None and gt_y is not None:
        ax.scatter([gt_x], [gt_y], c='#44dd44', s=100, zorder=7,
                   marker='D', label=f'GT ({gt_x:.0f}, {gt_y:.0f})')
        ax.annotate(f'GT\n({gt_x:.0f}, {gt_y:.0f})',
                    (gt_x, gt_y), textcoords='offset points', xytext=(8, -14),
                    color='#44dd44', fontsize=6.5)

    # Error arrow between est and GT
    if None not in (est_x, est_y, gt_x, gt_y):
        err = np.sqrt((est_x - gt_x)**2 + (est_y - gt_y)**2)
        ax.annotate('', xy=(gt_x, gt_y), xytext=(est_x, est_y),
                    arrowprops=dict(arrowstyle='->', color='#ffdd44',
                                   lw=1.2, connectionstyle='arc3,rad=0.15'))
        mx, my = (est_x + gt_x) / 2, (est_y + gt_y) / 2
        ax.text(mx, my, f'  err={err:.1f} cm', color='#ffdd44', fontsize=6.5)

    ax.legend(loc='upper right', fontsize=6.5, facecolor=bg,
              edgecolor=grid, labelcolor=fg, framealpha=0.85)

    # Render to numpy array
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight',
                facecolor=bg, edgecolor='none', dpi=100)
    plt.close(fig)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img_bgr


@vision_node(
    type_id='bpa_topdown_view',
    label='BPA Top-Down View',
    category='forensics',
    icon='Map',
    description=(
        "Vue du dessus (plan XY) en coordonnées pièce. "
        "Affiche la cible, les projections des taches, l'origine estimée (rouge étoile), "
        "l'origine GT (vert diamant), la flèche d'erreur et des rayons de stringing sous-échantillonnés. "
        "Nécessite les scalaires px/cm, height_px, et les coordonnées de la cible."
    ),
    resizable=True,
    min_width=280,
    min_height=220,
    colorable=True,
    inputs=[
        {'id': 'stains',     'color': 'dict',   'label': 'Stains Data'},
        {'id': 'px_per_cm',  'color': 'scalar', 'label': 'px/cm'},
        {'id': 'height_px',  'color': 'scalar', 'label': 'Image Height (px)'},
        {'id': 'width_cm',   'color': 'scalar', 'label': 'Board Width (cm)'},
        {'id': 'x_t',        'color': 'scalar', 'label': 'Target X (cm)'},
        {'id': 'y_t',        'color': 'scalar', 'label': 'Target Y (cm)'},
        {'id': 'z_t',        'color': 'scalar', 'label': 'Target Z (cm)'},
        {'id': 'est_x',      'color': 'scalar', 'label': 'Est. X (cm)'},
        {'id': 'est_y',      'color': 'scalar', 'label': 'Est. Y (cm)'},
        {'id': 'est_z',      'color': 'scalar', 'label': 'Est. Z (cm)'},
        {'id': 'gt_x',       'color': 'scalar', 'label': 'GT X (cm)'},
        {'id': 'gt_y',       'color': 'scalar', 'label': 'GT Y (cm)'},
        {'id': 'gt_z',       'color': 'scalar', 'label': 'GT Z (cm)'},
    ],
    outputs=[
        {'id': 'view', 'color': 'image', 'label': 'Top-Down View'},
    ],
    params=[
        {'id': 'n_rays',    'label': 'Rays to Draw',  'type': 'int',
         'default': 30, 'min': 0, 'max': 200},
        {'id': 'fig_w',     'label': 'Width (px)',    'type': 'int',
         'default': 700, 'min': 300, 'max': 1400},
        {'id': 'fig_h',     'label': 'Height (px)',   'type': 'int',
         'default': 520, 'min': 200, 'max': 900},
        {'id': 'dark_theme','label': 'Dark Theme',    'type': 'bool', 'default': True},
    ],
)
class BPATopDownViewNode(NodeProcessor):
    def process(self, inputs, params):
        if not _check_mpl():
            return _NULL

        stains_data = inputs.get('stains')
        stains      = stains_data.get('stains', []) if stains_data else []
        px_per_cm   = float(inputs.get('px_per_cm') or 23.62)
        height_px   = float(inputs.get('height_px') or 0)

        x_t = inputs.get('x_t')
        y_t = inputs.get('y_t')
        z_t = inputs.get('z_t')
        if None in (x_t, y_t):
            return _NULL

        view = _render(
            stains=stains,
            px_per_cm=px_per_cm,
            img_h_px=height_px,
            x_t=float(x_t), y_t=float(y_t), z_t=float(z_t or 0),
            est_x=inputs.get('est_x'), est_y=inputs.get('est_y'), est_z=inputs.get('est_z'),
            gt_x=inputs.get('gt_x'),   gt_y=inputs.get('gt_y'),   gt_z=inputs.get('gt_z'),
            width_cm=float(inputs.get('width_cm') or 80),
            height_cm=height_px / px_per_cm if height_px and px_per_cm else 60,
            n_rays=int(params.get('n_rays', 30)),
            fig_w=int(params.get('fig_w', 700)),
            fig_h=int(params.get('fig_h', 520)),
            dark_theme=bool(params.get('dark_theme', True)),
        )
        return {'view': view}
