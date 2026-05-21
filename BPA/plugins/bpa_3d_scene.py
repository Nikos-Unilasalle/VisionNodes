"""
BPA 3D Scene — rendu matplotlib 3D de la scène forensique.

Contenu :
  - Plan cible (rectangle bleu semi-transparent)
  - Taches sur le plan cible (scatter orange, position Y/Z réelle)
  - Rayons de stringing 3D (lignes grises, sous-échantillonnés)
  - Origine estimée (étoile rouge)
  - Origine GT (diamant vert)
  - Flèche d'erreur (jaune)
  - Axes en cm, repère pièce Attinger (X=profondeur, Y=horizontal, Z=vertical)

Vue interactive possible si affiché dans le viewer.
"""
from registry import vision_node, NodeProcessor
import numpy as np
import io

_NULL = {'scene': None}

_MPL_OK = None


def _check_mpl():
    global _MPL_OK
    if _MPL_OK is None:
        try:
            import matplotlib
            matplotlib.use('Agg')
            from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
            _MPL_OK = True
        except ImportError:
            _MPL_OK = False
    return _MPL_OK


def _render_3d(stains, px_per_cm, img_h_px, img_w_px,
               x_t, y_t, z_t,
               est_x, est_y, est_z,
               gt_x,  gt_y,  gt_z,
               n_rays, elev, azim, fig_w, fig_h, dark_theme):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import cv2

    bg = '#1a1e2e' if dark_theme else '#f5f5f5'
    fg = '#dddddd' if dark_theme else '#222222'

    fig = plt.figure(figsize=(fig_w / 100, fig_h / 100), dpi=100)
    fig.patch.set_facecolor(bg)
    ax = fig.add_subplot(111, projection='3d')
    ax.set_facecolor(bg)

    # Board dimensions in cm
    board_w = img_w_px / px_per_cm if img_w_px and px_per_cm else 80.0
    board_h = img_h_px / px_per_cm if img_h_px and px_per_cm else 60.0
    y0, y1 = float(y_t), float(y_t) + board_w
    z0, z1 = float(z_t), float(z_t) + board_h

    # Target board face (semi-transparent blue rectangle at x=x_t)
    verts = [[(x_t, y0, z0), (x_t, y1, z0), (x_t, y1, z1), (x_t, y0, z1)]]
    board = Poly3DCollection(verts, alpha=0.15, facecolor='#4a9eff', edgecolor='#4a9eff')
    ax.add_collection3d(board)
    # Board outline
    bx = [x_t, x_t, x_t, x_t, x_t]
    by = [y0,  y1,  y1,  y0,  y0]
    bz = [z0,  z0,  z1,  z1,  z0]
    ax.plot(bx, by, bz, color='#4a9eff', linewidth=1.2, alpha=0.8)

    # Stain positions on target board
    if stains:
        height_cm = img_h_px / px_per_cm
        sy = [y_t + s['cx'] / px_per_cm for s in stains]
        sz = [z_t + (height_cm - s['cy'] / px_per_cm) for s in stains]
        sx = [x_t] * len(stains)
        ax.scatter(sx, sy, sz, c='#ff9f40', s=10, alpha=0.6,
                   zorder=4, label=f'Taches (n={len(stains)})')

        # Sub-sampled 3D rays from stains toward estimated origin
        if n_rays > 0:
            step = max(1, len(stains) // n_rays)
            ox = est_x if est_x is not None else (gt_x or x_t + 60)
            oy = est_y if est_y is not None else (y_t + board_w / 2)
            oz = est_z if est_z is not None else (z_t + board_h / 2)
            for s in stains[::step]:
                wy = y_t + s['cx'] / px_per_cm
                wz = z_t + (height_cm - s['cy'] / px_per_cm)
                ax.plot([x_t, ox], [wy, oy], [wz, oz],
                        color='#667799', linewidth=0.5, alpha=0.35)

    # Estimated origin
    if None not in (est_x, est_y, est_z):
        ax.scatter([est_x], [est_y], [est_z], c='#ff3333', s=200,
                   marker='*', zorder=7, label=f'Est. ({est_x:.0f}, {est_y:.0f}, {est_z:.0f})')
        ax.text(float(est_x), float(est_y), float(est_z) + 3,
                f'Est.\n({est_x:.0f},{est_y:.0f},{est_z:.0f})',
                color='#ff5555', fontsize=6, ha='center')

    # GT origin
    if None not in (gt_x, gt_y, gt_z):
        ax.scatter([gt_x], [gt_y], [gt_z], c='#44dd44', s=150,
                   marker='D', zorder=7, label=f'GT ({gt_x:.0f}, {gt_y:.0f}, {gt_z:.0f})')
        ax.text(float(gt_x), float(gt_y), float(gt_z) - 6,
                f'GT\n({gt_x:.0f},{gt_y:.0f},{gt_z:.0f})',
                color='#55ff55', fontsize=6, ha='center')

    # Error arrow est → GT
    if None not in (est_x, est_y, est_z, gt_x, gt_y, gt_z):
        err = np.sqrt((est_x - gt_x)**2 + (est_y - gt_y)**2 + (est_z - gt_z)**2)
        ax.quiver(float(est_x), float(est_y), float(est_z),
                  float(gt_x - est_x), float(gt_y - est_y), float(gt_z - est_z),
                  color='#ffdd33', linewidth=1.5, arrow_length_ratio=0.12,
                  label=f'Erreur: {err:.1f} cm')

    # Axes labels & style
    ax.set_xlabel('X (cm)', color=fg, fontsize=7, labelpad=4)
    ax.set_ylabel('Y (cm)', color=fg, fontsize=7, labelpad=4)
    ax.set_zlabel('Z (cm)', color=fg, fontsize=7, labelpad=4)
    ax.tick_params(colors=fg, labelsize=6)
    for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
        pane.fill = False
        pane.set_edgecolor('#334455' if dark_theme else '#cccccc')
    ax.set_title('Scène 3D BPA — repère pièce', color=fg, fontsize=9, pad=8)

    ax.view_init(elev=elev, azim=azim)

    leg = ax.legend(loc='upper left', fontsize=6, facecolor=bg,
                    edgecolor='#334455', labelcolor=fg, framealpha=0.85)

    # Render
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight',
                facecolor=bg, edgecolor='none', dpi=100)
    plt.close(fig)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img_bgr


@vision_node(
    type_id='bpa_3d_scene',
    label='BPA 3D Scene',
    category='forensics',
    icon='Box',
    description=(
        "Rendu 3D de la scène forensique en coordonnées pièce (matplotlib). "
        "Affiche : plan cible semi-transparent, taches projetées, rayons de stringing 3D, "
        "origine estimée (étoile rouge), GT (diamant vert), flèche d'erreur. "
        "Axes : X=profondeur, Y=horizontal, Z=vertical (repère Attinger)."
    ),
    resizable=True,
    min_width=280,
    min_height=220,
    colorable=True,
    inputs=[
        {'id': 'stains',    'color': 'dict',   'label': 'Stains Data'},
        {'id': 'px_per_cm', 'color': 'scalar', 'label': 'px/cm'},
        {'id': 'height_px', 'color': 'scalar', 'label': 'Image Height (px)'},
        {'id': 'width_px',  'color': 'scalar', 'label': 'Image Width (px)'},
        {'id': 'x_t',       'color': 'scalar', 'label': 'Target X (cm)'},
        {'id': 'y_t',       'color': 'scalar', 'label': 'Target Y (cm)'},
        {'id': 'z_t',       'color': 'scalar', 'label': 'Target Z (cm)'},
        {'id': 'est_x',     'color': 'scalar', 'label': 'Est. X (cm)'},
        {'id': 'est_y',     'color': 'scalar', 'label': 'Est. Y (cm)'},
        {'id': 'est_z',     'color': 'scalar', 'label': 'Est. Z (cm)'},
        {'id': 'gt_x',      'color': 'scalar', 'label': 'GT X (cm)'},
        {'id': 'gt_y',      'color': 'scalar', 'label': 'GT Y (cm)'},
        {'id': 'gt_z',      'color': 'scalar', 'label': 'GT Z (cm)'},
    ],
    outputs=[
        {'id': 'scene', 'color': 'image', 'label': '3D Scene'},
    ],
    params=[
        {'id': 'n_rays',    'label': 'Rays to Draw', 'type': 'int',
         'default': 40, 'min': 0, 'max': 300},
        {'id': 'elev',      'label': 'Elevation (°)', 'type': 'int',
         'default': 25, 'min': -90, 'max': 90},
        {'id': 'azim',      'label': 'Azimuth (°)',   'type': 'int',
         'default': -60, 'min': -180, 'max': 180},
        {'id': 'fig_w',     'label': 'Width (px)',    'type': 'int',
         'default': 700, 'min': 300, 'max': 1400},
        {'id': 'fig_h',     'label': 'Height (px)',   'type': 'int',
         'default': 560, 'min': 200, 'max': 900},
        {'id': 'dark_theme','label': 'Dark Theme',    'type': 'bool', 'default': True},
    ],
)
class BPA3DSceneNode(NodeProcessor):
    def process(self, inputs, params):
        if not _check_mpl():
            return _NULL

        stains_data = inputs.get('stains')
        stains      = stains_data.get('stains', []) if stains_data else []
        px_per_cm   = float(inputs.get('px_per_cm') or 23.62)
        height_px   = float(inputs.get('height_px') or 0)
        width_px    = float(inputs.get('width_px')  or 0)
        x_t = inputs.get('x_t')
        y_t = inputs.get('y_t')
        z_t = inputs.get('z_t')
        if None in (x_t, y_t):
            return _NULL

        scene = _render_3d(
            stains=stains,
            px_per_cm=px_per_cm,
            img_h_px=height_px,
            img_w_px=width_px,
            x_t=float(x_t), y_t=float(y_t), z_t=float(z_t or 0),
            est_x=inputs.get('est_x'), est_y=inputs.get('est_y'), est_z=inputs.get('est_z'),
            gt_x=inputs.get('gt_x'),   gt_y=inputs.get('gt_y'),   gt_z=inputs.get('gt_z'),
            n_rays=int(params.get('n_rays', 40)),
            elev=int(params.get('elev', 25)),
            azim=int(params.get('azim', -60)),
            fig_w=int(params.get('fig_w', 700)),
            fig_h=int(params.get('fig_h', 560)),
            dark_theme=bool(params.get('dark_theme', True)),
        )
        return {'scene': scene}
