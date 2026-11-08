import cv2
import numpy as np
from skimage import measure
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='draw_root_publication',
    label='Root Publication Figure',
    category='draw',
    icon='Sparkles',
    description=(
        'Renders publication-grade anatomical root cross-section figures with '
        'calibrated color schemes, geometric completion of the metaxylem vessels '
        'as regular smooth ellipses/circles, cortical lacunae (aerenchyma) 45-degree diagonal '
        'hatching, and predictive accounting of missing cells in the central stele.'
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'labels', 'color': 'labels'},
        {'id': 'boundary', 'color': 'mask'},
        {'id': 'landmarks', 'color': 'mask'},
        {'id': 'pith_mask', 'color': 'mask'},
        {'id': 'vascular_mask', 'color': 'mask'},
        {'id': 'endodermis_mask', 'color': 'mask'},
        {'id': 'inner_cortex_mask', 'color': 'mask'},
        {'id': 'outer_cortex_mask', 'color': 'mask'},
        {'id': 'rhizodermis_mask', 'color': 'mask'},
        {'id': 'ellipse_report', 'color': 'dict'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image', 'label': 'Publication Figure'},
        {'id': 'figure_with_legend', 'color': 'image', 'label': 'Figure with Legend & Accounting'},
        {'id': 'predictive_report', 'color': 'dict', 'label': 'Predictive Accounting Report'},
    ],
    params=[
        {'id': 'canvas_mode', 'label': 'Canvas Background', 'type': 'choice',
         'choices': ['clean_white', 'light_canvas', 'blended_microscopy', 'black'], 'default': 'clean_white'},
        {'id': 'zone_opacity', 'label': 'Zone Opacity (Pastel Base)', 'type': 'float', 'default': 0.32, 'min': 0.0, 'max': 1.0, 'step': 0.02},
        {'id': 'cell_opacity', 'label': 'Cell Opacity (Vibrant Top)', 'type': 'float', 'default': 0.90, 'min': 0.0, 'max': 1.0, 'step': 0.02},
        {'id': 'pt_to_px', 'label': 'Point to Pixel Scale', 'type': 'float', 'default': 1.33, 'min': 0.8, 'max': 2.5, 'step': 0.05},
        {'id': 'complete_metaxylem', 'label': 'Geometrically Complete Metaxylem (Ellipses)', 'type': 'bool', 'default': True},
        {'id': 'complete_steles', 'label': 'Geometrically Complete Stele Boundary', 'type': 'bool', 'default': True},
        {'id': 'hatch_lacunae', 'label': 'Hatch Cortical Lacunae (45 deg)', 'type': 'bool', 'default': True},
        {'id': 'lacunae_min_area', 'label': 'Min Lacuna Area (px)', 'type': 'int', 'default': 25, 'min': 5, 'max': 500},
        {'id': 'use_robust_decoalescence', 'label': 'Robust Decoalescence & Unit Area Estimation', 'type': 'bool', 'default': False},
        {'id': 'decoal_threshold', 'label': 'Decoalescence Multiplier Threshold', 'type': 'float', 'default': 1.80, 'min': 1.2, 'max': 3.0, 'step': 0.05},
        {'id': 'use_antipodal_mirror', 'label': 'Antipodal Mirror Reflection Imputation', 'type': 'bool', 'default': True},
        {'id': 'draw_legend', 'label': 'Include Legend & Accounting Panel', 'type': 'bool', 'default': True},
        {'id': 'draw_scale_bar', 'label': 'Draw Scale Bar', 'type': 'bool', 'default': True},
        {'id': 'scale_bar_um', 'label': 'Scale Bar Length (um)', 'type': 'int', 'default': 200, 'min': 10, 'max': 2000},
        {'id': 'pixel_size_um', 'label': 'Pixel Size (um/px)', 'type': 'float', 'default': 0.50, 'min': 0.01, 'max': 10.0},
    ],
)
class RootPublicationFigureNode(NodeProcessor):
    @staticmethod
    def _robust_unit_area(cells, default=140.0):
        """
        Extrait la taille unitaire de la population dominante en écartant
        les extrêmes (débris de bruit et méga-composantes coalescentes)
        via un filtrage interquartile robuste (Tukey IQR).
        """
        if not cells:
            return default
        arr = np.array([p.area for p in cells], dtype=float)
        if len(arr) < 4:
            return float(np.median(arr))
        q25, q50, q75 = np.percentile(arr, [25, 50, 75])
        iqr = q75 - q25
        inliers = arr[(arr >= max(10.0, q25 - 1.5 * iqr)) & (arr <= q75 + 1.5 * iqr)]
        if len(inliers) >= 3:
            return float(np.mean(inliers))
        return float(q50)

    @staticmethod
    def _decoalesce_cells(cells, unit_area, threshold_factor=1.80):
        """
        Décompose les méga-composantes coalescentes (A >= threshold_factor * unit_area)
        en leur équivalent en cellules élémentaires.
        """
        if not cells or unit_area <= 0:
            return len(cells), 0
        total_cells = 0
        merged_blobs = 0
        for p in cells:
            a = p.area
            if a >= threshold_factor * unit_area:
                k = max(1, int(round(a / unit_area)))
                total_cells += k
                if k > 1:
                    merged_blobs += 1
            else:
                total_cells += 1
        return total_cells, merged_blobs

    @staticmethod
    def _antipodal_impute_zone(m_zone, labels, clean_mx_mask, cx, cy, unit_area_fallback, is_inner_cortex=False):
        """
        Impute missing cells in m_zone using antipodal point reflection:
        p_opp = 2*c - p
        Unilateral void (opposite side contains healthy observed cells) is recognized as a
        preparation tear/breach and imputed using the median cell size measured directly in front.
        Bilateral void (opposite side is also void) in inner cortex represents true physiological
        aerenchyma lacunae and is preserved (not imputed).
        """
        if m_zone is None or not np.any(m_zone):
            return 0, 0, 0
        h, w = labels.shape[:2]
        cell_occupied = (labels > 0)
        v_mask = m_zone & (~cell_occupied)
        if clean_mx_mask is not None and np.any(clean_mx_mask):
            v_mask = v_mask & (~clean_mx_mask)
            
        v_pixels = int(np.count_nonzero(v_mask))
        if v_pixels == 0:
            return 0, 0, 0
            
        y_idx, x_idx = np.where(v_mask)
        x_opp = np.clip(np.round(2 * cx - x_idx).astype(int), 0, w - 1)
        y_opp = np.clip(np.round(2 * cy - y_idx).astype(int), 0, h - 1)
        
        opp_labels = labels[y_opp, x_opp]
        sain_mask = (opp_labels > 0)
        unilateral_px = int(np.count_nonzero(sain_mask))
        bilateral_px = int(v_pixels - unilateral_px)
        
        opp_cids = np.unique(opp_labels[sain_mask])
        if len(opp_cids) > 0:
            opp_areas = [np.count_nonzero(labels == cid) for cid in opp_cids if cid > 0]
            if len(opp_areas) >= 4:
                q25, q50, q75 = np.percentile(opp_areas, [25, 50, 75])
                iqr = q75 - q25
                inliers = [a for a in opp_areas if (q25 - 1.5 * iqr) <= a <= (q75 + 1.5 * iqr)]
                med_opp_area = float(np.median(inliers)) if inliers else float(q50)
            else:
                med_opp_area = float(np.median(opp_areas))
        else:
            med_opp_area = float(unit_area_fallback)
            
        n_unilateral_pred = int(round(unilateral_px / max(1.0, med_opp_area)))
        
        if is_inner_cortex:
            # Bilateral void in inner cortex is genuine biological aerenchyma lacuna -> preserved!
            n_bilateral_pred = 0
        else:
            n_bilateral_pred = int(round(bilateral_px / max(1.0, unit_area_fallback)))
            
        n_missing_pred = n_unilateral_pred + n_bilateral_pred
        return n_missing_pred, unilateral_px, bilateral_px

    def process(self, inputs, params):
        labels = inputs.get('labels')
        if labels is None or not isinstance(labels, np.ndarray):
            img = inputs.get('image')
            return {'main': img, 'figure_with_legend': img, 'predictive_report': {}}

        h, w = labels.shape[:2]
        canvas_mode = params.get('canvas_mode', 'clean_white')
        zone_alpha  = float(params.get('zone_opacity', 0.32))
        cell_alpha  = float(params.get('cell_opacity', 0.90))
        pt_scale    = float(params.get('pt_to_px', 1.33))
        comp_mx     = bool(params.get('complete_metaxylem', True))
        comp_stele  = bool(params.get('complete_steles', True))
        hatch_lac   = bool(params.get('hatch_lacunae', True))
        min_lac_area = int(params.get('lacunae_min_area', 25))
        use_robust_decoal = bool(params.get('use_robust_decoalescence', False))
        decoal_th         = float(params.get('decoal_threshold', 1.80))
        use_antipodal_mirror = bool(params.get('use_antipodal_mirror', True))

        def _to_mask(m):
            if m is None:
                return np.zeros((h, w), dtype=bool)
            if isinstance(m, np.ndarray):
                if m.ndim == 3:
                    m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY)
                return m > 0
            return np.zeros((h, w), dtype=bool)

        section = _to_mask(inputs.get('boundary'))
        raw_mx_mask = _to_mask(inputs.get('landmarks'))
        m_pith  = _to_mask(inputs.get('pith_mask'))
        m_vasc  = _to_mask(inputs.get('vascular_mask'))
        m_endo  = _to_mask(inputs.get('endodermis_mask'))
        m_inner = _to_mask(inputs.get('inner_cortex_mask'))
        m_outer = _to_mask(inputs.get('outer_cortex_mask'))
        m_rhizo = _to_mask(inputs.get('rhizodermis_mask'))
        ep_rep  = inputs.get('ellipse_report', {})

        # Base canvas
        bg_in = inputs.get('image')
        if canvas_mode == 'clean_white':
            canvas = np.full((h, w, 3), 253, dtype=np.uint8)
        elif canvas_mode == 'light_canvas':
            canvas = np.full((h, w, 3), 245, dtype=np.uint8)
        elif canvas_mode == 'black':
            canvas = np.zeros((h, w, 3), dtype=np.uint8)
        elif canvas_mode == 'blended_microscopy' and bg_in is not None and isinstance(bg_in, np.ndarray):
            if bg_in.shape[:2] != (h, w):
                bg_in = cv2.resize(bg_in, (w, h))
            if bg_in.ndim == 2:
                bg_in = cv2.cvtColor(bg_in, cv2.COLOR_GRAY2BGR)
            canvas = cv2.addWeighted(bg_in, 0.40, np.full((h, w, 3), 255, dtype=np.uint8), 0.60, 0)
        else:
            canvas = np.full((h, w, 3), 253, dtype=np.uint8)

        # -------------------------------------------------------------
        # STEP 1: GEOMETRIC COMPLETION OF METAXYLEM (Regular Ellipses)
        # -------------------------------------------------------------
        # Fit smooth regular ellipses to each of the metaxylem vessels
        # to eliminate notches, bites, and irregular leaks.
        mx_completed_mask = np.zeros((h, w), dtype=bool)
        mx_ellipses = []
        raw_cnts, _ = cv2.findContours(raw_mx_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        for cnt in raw_cnts:
            if cv2.contourArea(cnt) >= 400 and len(cnt) >= 5:
                if comp_mx:
                    ell = cv2.fitEllipse(cnt)
                    mx_ellipses.append(ell)
                    m_temp = np.zeros((h, w), dtype=np.uint8)
                    cv2.ellipse(m_temp, ell, 255, -1)
                    mx_completed_mask |= (m_temp > 0)
                else:
                    m_temp = np.zeros((h, w), dtype=np.uint8)
                    cv2.drawContours(m_temp, [cnt], -1, 255, -1)
                    mx_completed_mask |= (m_temp > 0)

        # -------------------------------------------------------------
        # STEP 2: EXACT ANATOMICAL COLOR & LINE SPECIFICATIONS
        # -------------------------------------------------------------
        TISSUES = {
            'rhizodermis': {
                'mask': m_rhizo,
                'vibrant': (245, 220, 197),  # Bleu clair pastel BGR (#C5DCF5)
                'pastel':  (250, 238, 225),
                'wall_col':(56, 28, 10),     # Bleu nuit profond / Marine (#0A1C38)
                'th_pt':   0.75,             # 0.75 pt cloisons
                'th_ext_pt': 1.5,            # 1.5 pt externe
                'name':    'Rhizoderme / Assise subéreuse',
                'role':    'Couche externe protectrice',
                'order':   7,
            },
            'outer_cortex': {
                'mask': m_outer,
                'vibrant': (182, 214, 252),  # Orange abricot clair BGR (#FCD6B6)
                'pastel':  (218, 235, 254),
                'wall_col':(40, 75, 163),    # Brun-orangé soutenu / Terracotta (#A34B28)
                'th_pt':   0.75,
                'name':    'Cortex externe',
                'role':    'Grandes cellules de réserve',
                'order':   6,
            },
            'inner_cortex': {
                'mask': m_inner,
                'vibrant': (209, 232, 196),  # Vert menthe / sauge BGR (#C4E8D1)
                'pastel':  (232, 245, 225),
                'wall_col':(43, 77, 30),     # Vert forêt foncé (#1E4D2B)
                'th_pt':   0.75,
                'name':    'Cortex interne',
                'role':    'Parenchyme aérifère / de transition',
                'order':   5,
            },
            'endodermis': {
                'mask': m_endo,
                'vibrant': (168, 105, 158),  # Violet moyen / Prune BGR (#9E69A8)
                'pastel':  (212, 180, 207),
                'wall_col':(56, 13, 42),     # Aubergine très sombre / Indigo (#2A0D38)
                'th_pt':   0.60,             # 0.6 pt cellules
                'th_ring_pt': 1.20,          # 1.2 pt limite anneau de Caspary
                'name':    'Endoderme & Péricycle',
                'role':    'Barrière sélective (cadre de Caspary)',
                'order':   4,
            },
            'vascular': {
                'mask': m_vasc,
                'vibrant': (138, 220, 246),  # Jaune ocre doux BGR (#F6DC8A)
                'pastel':  (197, 238, 251),
                'wall_col':(33, 58, 92),     # Marron chaud / Terre d'ombre (#5C3A21)
                'th_pt':   0.40,             # 0.4 pt fin
                'name':    'Phloème primaire',
                'role':    'Transport de sève élaborée',
                'order':   3,
            },
            'metaxylem': {
                'mask': mx_completed_mask,
                'vibrant': (232, 243, 223),  # Vert très pâle / Céladon BGR (#DFF3E8)
                'pastel':  (244, 250, 240),
                'wall_col':(30, 59, 14),     # Vert sapin foncé (#0E3B1E)
                'th_pt':   1.20,             # 1.2 pt circulaire net
                'name':    'Métaxylème',
                'role':    'Vaisseaux de sève brute',
                'order':   1,
            },
            'pith': {
                'mask': m_pith,
                'vibrant': (255, 215, 231),  # Lilas / Lavande clair BGR (#E7D7FF)
                'pastel':  (255, 235, 243),
                'wall_col':(75, 21, 74),     # Violet foncé saturé (#4A154B)
                'th_pt':   0.50,             # 0.5 pt isodiamétrique fin
                'name':    'Moelle centrale (Pith)',
                'role':    'Cellules de soutien médullaires',
                'order':   2,
            },
        }

        # -------------------------------------------------------------
        # STEP 3: Continuous Tissue Territory Underlay
        # -------------------------------------------------------------
        root_roi = section if np.any(section) else np.ones((h, w), dtype=bool)

        for key, t in sorted(TISSUES.items(), key=lambda item: item[1]['order']):
            mask = t['mask'] & root_roi
            if np.any(mask):
                col_pas = np.array(t['pastel'], dtype=np.float32)
                canvas[mask] = ((1.0 - zone_alpha) * canvas[mask] + zone_alpha * col_pas).astype(np.uint8)

        # -------------------------------------------------------------
        # STEP 4: Individual Segmented Cell Interiors
        # -------------------------------------------------------------
        props = measure.regionprops(labels)
        cell_assignments = {}
        priority_keys = ['endodermis', 'rhizodermis', 'pith', 'inner_cortex', 'outer_cortex', 'vascular']

        for p in props:
            cid = p.label
            c_mask = (labels == cid)
            cy, cx = int(round(p.centroid[0])), int(round(p.centroid[1]))
            cy = min(h - 1, max(0, cy))
            cx = min(w - 1, max(0, cx))

            # A cell is metaxylem ONLY if its centroid falls inside a completed metaxylem ellipse
            if mx_completed_mask[cy, cx]:
                t_assigned = 'metaxylem'
            else:
                t_assigned = None
                for k in priority_keys:
                    if TISSUES[k]['mask'][cy, cx]:
                        t_assigned = k
                        break
                if t_assigned is None:
                    max_ov = 0
                    for k in priority_keys:
                        ov = np.count_nonzero(c_mask & TISSUES[k]['mask'])
                        if ov > max_ov:
                            max_ov = ov
                            t_assigned = k
                if t_assigned is None:
                    t_assigned = 'inner_cortex'

            cell_assignments[cid] = t_assigned
            col_vibrant = np.array(TISSUES[t_assigned]['vibrant'], dtype=np.float32)
            canvas[c_mask] = ((1.0 - cell_alpha) * canvas[c_mask] + cell_alpha * col_vibrant).astype(np.uint8)

        # -------------------------------------------------------------
        # STEP 5: Cortical Lacunae (Aérenchyme / Nécroses) with 45° Hatching
        # -------------------------------------------------------------
        lacunae_count = 0
        total_lacunae_area = 0
        if hatch_lac:
            cortex_area = (m_inner | m_outer) & root_roi
            cells_coverage = (labels > 0)
            cortex_gaps = cortex_area & (~cells_coverage)

            n_gaps, gap_labels, gap_stats, _ = cv2.connectedComponentsWithStats(cortex_gaps.astype(np.uint8))
            lacunae_mask = np.zeros((h, w), dtype=bool)
            for i in range(1, n_gaps):
                area_i = gap_stats[i, cv2.CC_STAT_AREA]
                if area_i >= min_lac_area:
                    lacunae_mask |= (gap_labels == i)
                    lacunae_count += 1
                    total_lacunae_area += area_i

            if np.any(lacunae_mask):
                canvas[lacunae_mask] = (255, 255, 255)
                yy, xx = np.indices((h, w))
                hatch_lines = ((xx + yy) % 7 == 0) & lacunae_mask
                canvas[hatch_lines] = (51, 51, 51)
                th_lac_px = max(1, int(round(0.35 * pt_scale)))
                lac_cnts, _ = cv2.findContours(lacunae_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
                if lac_cnts:
                    cv2.drawContours(canvas, lac_cnts, -1, (51, 51, 51), th_lac_px, cv2.LINE_AA)

        # -------------------------------------------------------------
        # STEP 6: Predictive Accounting of Central Stele & Missing Cells
        # -------------------------------------------------------------
        cx_s = float(ep_rep.get('center_x', w / 2.0))
        cy_s = float(ep_rep.get('center_y', h / 2.0))
        maj_s = float(ep_rep.get('major_axis', 160.0))
        min_s = float(ep_rep.get('minor_axis', 125.0))
        angle_s = float(ep_rep.get('tilt_angle_deg', 0.0))
        s_pith  = float(ep_rep.get('scale_pith', 0.65))
        s_endo  = float(ep_rep.get('scale_endodermis', 1.30))

        a_endo = maj_s * s_endo
        b_endo = min_s * s_endo
        area_stele_theo = np.pi * a_endo * b_endo
        h_param = ((a_endo - b_endo)**2) / ((a_endo + b_endo)**2 + 1e-6)
        perim_endo_theo = np.pi * (a_endo + b_endo) * (1.0 + (3.0 * h_param) / (10.0 + np.sqrt(4.0 - 3.0 * h_param + 1e-6)))

        a_pith = maj_s * s_pith
        b_pith = min_s * s_pith
        area_pith_theo = np.pi * a_pith * b_pith

        # Metaxylem total completed area
        area_mx_total = 0.0
        for ell in mx_ellipses:
            area_mx_total += np.pi * (ell[1][0] / 2.0) * (ell[1][1] / 2.0)

        cos_t = np.cos(np.radians(angle_s))
        sin_t = np.sin(np.radians(angle_s))
        pith_obs_cells = []
        endo_obs_cells = []
        vasc_obs_cells = []
        inner_obs_cells = []
        outer_obs_cells = []
        rhizo_obs_cells = []

        s_inner = float(ep_rep.get('scale_inner_cortex', s_endo * 1.42))
        s_outer = float(ep_rep.get('scale_outer_cortex', s_endo * 1.86))
        s_rhizo = float(ep_rep.get('scale_rhizodermis', s_endo * 2.12))

        for p in props:
            yc, xc = p.centroid
            dx, dy = xc - cx_s, yc - cy_s
            xr = cos_t * dx + sin_t * dy
            yr = -sin_t * dx + cos_t * dy
            r_norm = np.sqrt((xr / maj_s)**2 + (yr / min_s)**2)

            if mx_completed_mask[int(yc), int(xc)]:
                continue

            if r_norm <= s_pith:
                pith_obs_cells.append(p)
            elif s_pith < r_norm <= s_endo:
                if r_norm >= s_endo * 0.90:
                    endo_obs_cells.append(p)
                else:
                    vasc_obs_cells.append(p)
            elif s_endo < r_norm <= s_inner:
                inner_obs_cells.append(p)
            elif s_inner < r_norm <= s_outer:
                outer_obs_cells.append(p)
            elif s_outer < r_norm <= s_rhizo:
                rhizo_obs_cells.append(p)

        # 1. Pith
        n_pith_obs = len(pith_obs_cells)
        area_pith_obs = sum(p.area for p in pith_obs_cells)
        if use_robust_decoal:
            unit_pith_area = self._robust_unit_area(pith_obs_cells, default=140.0)
            n_pith_eff, _ = self._decoalesce_cells(pith_obs_cells, unit_pith_area, decoal_th)
        else:
            unit_pith_area = float(np.mean([p.area for p in pith_obs_cells])) if pith_obs_cells else 140.0
            n_pith_eff = n_pith_obs

        if use_antipodal_mirror:
            n_pith_missing_pred, _, _ = self._antipodal_impute_zone(
                m_pith, labels, mx_completed_mask, cx_s, cy_s, unit_pith_area, is_inner_cortex=False
            )
        else:
            void_pith_area = max(0.0, area_pith_theo - area_pith_obs)
            n_pith_missing_pred = int(round(void_pith_area / max(1.0, unit_pith_area)))
        n_pith_total_pred   = n_pith_eff + n_pith_missing_pred
        pith_completeness   = min(100.0, (area_pith_obs / max(1.0, area_pith_theo)) * 100.0)

        # 2. Central vascular (subtracting completed metaxylem vessels)
        area_vasc_theo = max(0.0, area_stele_theo - area_pith_theo - area_mx_total)
        area_vasc_obs = sum(p.area for p in vasc_obs_cells)
        if use_robust_decoal:
            unit_vasc_area = self._robust_unit_area(vasc_obs_cells, default=125.0)
            n_vasc_eff, _ = self._decoalesce_cells(vasc_obs_cells, unit_vasc_area, decoal_th)
        else:
            unit_vasc_area = float(np.mean([p.area for p in vasc_obs_cells])) if vasc_obs_cells else 125.0
            n_vasc_eff = len(vasc_obs_cells)

        if use_antipodal_mirror:
            n_vasc_missing_pred, _, _ = self._antipodal_impute_zone(
                m_vasc, labels, mx_completed_mask, cx_s, cy_s, unit_vasc_area, is_inner_cortex=False
            )
        else:
            void_vasc_area = max(0.0, area_vasc_theo - area_vasc_obs)
            n_vasc_missing_pred = int(round(void_vasc_area / max(1.0, unit_vasc_area)))
        n_vasc_total_pred   = n_vasc_eff + n_vasc_missing_pred

        # 3. Endodermis (length dynamically measured from observed endodermal cells)
        n_endo_obs = len(endo_obs_cells)
        if n_endo_obs >= 3:
            def _cell_len(p):
                if hasattr(p, 'axis_major_length'):
                    return max(p.axis_major_length, p.axis_minor_length)
                return max(getattr(p, 'major_axis_length', 16.0), getattr(p, 'minor_axis_length', 16.0))
            lens = [_cell_len(p) for p in endo_obs_cells]
            if use_robust_decoal and len(lens) >= 4:
                q25, q50, q75 = np.percentile(lens, [25, 50, 75])
                iqr = q75 - q25
                inlier_lens = [l for l in lens if (q25 - 1.5 * iqr) <= l <= (q75 + 1.5 * iqr)]
                med_endo_len = float(np.median(inlier_lens)) if inlier_lens else float(q50)
            else:
                med_endo_len = float(np.median(lens))
        else:
            med_endo_len = 16.0
        med_endo_len = float(np.clip(med_endo_len, 10.0, 25.0))
        n_endo_pred  = int(round(perim_endo_theo / max(1.0, med_endo_len)))
        n_endo_missing = max(0, n_endo_pred - n_endo_obs)

        # 4. Inner Cortex (subtracting cortical lacunae intersecting inner cortex)
        a_base = maj_s
        b_base = min_s
        area_inner_theo = max(0.0, np.pi * a_base * b_base * (s_inner**2 - s_endo**2))
        area_inner_obs = sum(p.area for p in inner_obs_cells)
        if use_robust_decoal:
            unit_inner_area = self._robust_unit_area(inner_obs_cells, default=320.0)
            n_inner_eff, _ = self._decoalesce_cells(inner_obs_cells, unit_inner_area, decoal_th)
        else:
            unit_inner_area = float(np.mean([p.area for p in inner_obs_cells])) if inner_obs_cells else 320.0
            n_inner_eff = len(inner_obs_cells)

        if use_antipodal_mirror:
            n_inner_missing_pred, _, _ = self._antipodal_impute_zone(
                m_inner, labels, mx_completed_mask, cx_s, cy_s, unit_inner_area, is_inner_cortex=True
            )
        else:
            lac_inner_area = float(np.count_nonzero(lacunae_mask & m_inner)) if np.any(lacunae_mask) else 0.0
            void_inner_area = max(0.0, area_inner_theo - area_inner_obs - lac_inner_area)
            n_inner_missing_pred = int(round(void_inner_area / max(1.0, unit_inner_area)))
        n_inner_total_pred = n_inner_eff + n_inner_missing_pred

        # 5. Outer Cortex (subtracting cortical lacunae intersecting outer cortex)
        area_outer_theo = max(0.0, np.pi * a_base * b_base * (s_outer**2 - s_inner**2))
        area_outer_obs = sum(p.area for p in outer_obs_cells)
        if use_robust_decoal:
            unit_outer_area = self._robust_unit_area(outer_obs_cells, default=350.0)
            n_outer_eff, _ = self._decoalesce_cells(outer_obs_cells, unit_outer_area, decoal_th)
        else:
            unit_outer_area = float(np.mean([p.area for p in outer_obs_cells])) if outer_obs_cells else 350.0
            n_outer_eff = len(outer_obs_cells)

        if use_antipodal_mirror:
            n_outer_missing_pred, _, _ = self._antipodal_impute_zone(
                m_outer, labels, mx_completed_mask, cx_s, cy_s, unit_outer_area, is_inner_cortex=False
            )
        else:
            lac_outer_area = float(np.count_nonzero(lacunae_mask & m_outer)) if np.any(lacunae_mask) else 0.0
            void_outer_area = max(0.0, area_outer_theo - area_outer_obs - lac_outer_area)
            n_outer_missing_pred = int(round(void_outer_area / max(1.0, unit_outer_area)))
        n_outer_total_pred = n_outer_eff + n_outer_missing_pred

        # 6. Rhizodermis
        n_rhizo_obs = len(rhizo_obs_cells)
        area_rhizo_theo = max(0.0, np.pi * a_base * b_base * (s_rhizo**2 - s_outer**2))
        area_rhizo_obs = sum(p.area for p in rhizo_obs_cells)
        if use_robust_decoal:
            unit_rhizo_area = self._robust_unit_area(rhizo_obs_cells, default=300.0)
            n_rhizo_eff, _ = self._decoalesce_cells(rhizo_obs_cells, unit_rhizo_area, decoal_th)
        else:
            unit_rhizo_area = float(np.mean([p.area for p in rhizo_obs_cells])) if rhizo_obs_cells else 300.0
            n_rhizo_eff = n_rhizo_obs

        if use_antipodal_mirror:
            n_rhizo_missing_pred, _, _ = self._antipodal_impute_zone(
                m_rhizo, labels, mx_completed_mask, cx_s, cy_s, unit_rhizo_area, is_inner_cortex=False
            )
        else:
            void_rhizo_area = max(0.0, area_rhizo_theo - area_rhizo_obs)
            n_rhizo_missing_pred = int(round(void_rhizo_area / max(1.0, unit_rhizo_area)))
        n_rhizo_total_pred = n_rhizo_eff + n_rhizo_missing_pred

        # Raw watershed metaxylem area vs regularized
        area_mx_raw = float(raw_mx_mask.sum())

        pred_report = {
            'stele_center': [float(cx_s), float(cy_s)],
            'stele_tilt_deg': float(angle_s),
            'stele_area_theo_px': round(float(area_stele_theo), 1),
            'stele_perim_theo_px': round(float(perim_endo_theo), 1),
            'metaxylem_vessels_completed': len(mx_ellipses),
            'metaxylem_raw_area_px': round(float(area_mx_raw), 1),
            'metaxylem_total_area_px': round(float(area_mx_total), 1),
            'pith_area_theo_px': round(float(area_pith_theo), 1),
            'pith_unit_area_px': round(float(unit_pith_area), 1),
            'pith_cells_observed': int(n_pith_obs),
            'pith_cells_decoalesced': int(n_pith_eff),
            'pith_cells_missing_pred': int(n_pith_missing_pred),
            'pith_cells_total_pred': int(n_pith_total_pred),
            'pith_completeness_pct': round(float(pith_completeness), 1),
            'vascular_unit_area_px': round(float(unit_vasc_area), 1),
            'vascular_cells_observed': int(len(vasc_obs_cells)),
            'vascular_cells_decoalesced': int(n_vasc_eff),
            'vascular_cells_missing_pred': int(n_vasc_missing_pred),
            'vascular_cells_total_pred': int(n_vasc_total_pred),
            'endo_cells_observed': int(n_endo_obs),
            'endo_cell_length_measured': round(float(med_endo_len), 2),
            'endo_cells_missing_pred': int(n_endo_missing),
            'endo_cells_total_pred': int(n_endo_pred),
            'inner_cortex_unit_area_px': round(float(unit_inner_area), 1),
            'inner_cortex_observed': int(len(inner_obs_cells)),
            'inner_cortex_decoalesced': int(n_inner_eff),
            'inner_cortex_missing_pred': int(n_inner_missing_pred),
            'inner_cortex_total_pred': int(n_inner_total_pred),
            'outer_cortex_unit_area_px': round(float(unit_outer_area), 1),
            'outer_cortex_observed': int(len(outer_obs_cells)),
            'outer_cortex_decoalesced': int(n_outer_eff),
            'outer_cortex_missing_pred': int(n_outer_missing_pred),
            'outer_cortex_total_pred': int(n_outer_total_pred),
            'rhizodermis_unit_area_px': round(float(unit_rhizo_area), 1),
            'rhizodermis_observed': int(n_rhizo_obs),
            'rhizodermis_decoalesced': int(n_rhizo_eff),
            'rhizodermis_missing_pred': int(n_rhizo_missing_pred),
            'rhizodermis_total_pred': int(n_rhizo_total_pred),
            'lacunae_count': int(lacunae_count),
            'lacunae_total_area_px': int(total_lacunae_area),
        }

        # -------------------------------------------------------------
        # STEP 7: Vector Wall Rendering (Anti-aliased 2x Super-Sampling)
        # -------------------------------------------------------------
        wall_2x_bgr = np.zeros((h * 2, w * 2, 3), dtype=np.uint8)
        wall_2x_alpha = np.zeros((h * 2, w * 2), dtype=np.float32)

        # Contours of regular parenchyma, cortical and vascular cells
        tier_contours = {k: [] for k in TISSUES if k != 'metaxylem'}
        for p in props:
            cid = p.label
            t_key = cell_assignments[cid]
            if t_key == 'metaxylem':
                continue

            r0, c0, r1, c1 = p.bbox
            r0_p = max(0, r0 - 1)
            c0_p = max(0, c0 - 1)
            r1_p = min(h, r1 + 1)
            c1_p = min(w, c1 + 1)

            sub = (labels[r0_p:r1_p, c0_p:c1_p] == cid).astype(np.uint8)
            cnts, _ = cv2.findContours(sub, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            for cnt in cnts:
                c2 = cnt.copy()
                c2[:, :, 0] = (c2[:, :, 0] + c0_p) * 2
                c2[:, :, 1] = (c2[:, :, 1] + r0_p) * 2
                tier_contours[t_key].append(c2)

        for t_key in sorted(tier_contours.keys(), key=lambda k: TISSUES[k]['th_pt']):
            cnts = tier_contours[t_key]
            if not cnts:
                continue
            t_data = TISSUES[t_key]
            th_px_2x = max(1, int(round(t_data['th_pt'] * pt_scale * 2.0)))
            w_col = t_data['wall_col']

            mask_tier = np.zeros((h * 2, w * 2), dtype=np.uint8)
            cv2.drawContours(mask_tier, cnts, -1, 255, th_px_2x, cv2.LINE_AA)
            idx = (mask_tier > 0)
            wall_2x_bgr[idx] = w_col
            wall_2x_alpha[idx] = np.maximum(wall_2x_alpha[idx], mask_tier[idx] / 255.0)

        # Outer root boundary (Rhizoderme externe: 1.5 pt)
        if np.any(section):
            sec_2x = cv2.resize(section.astype(np.uint8), (w * 2, h * 2), interpolation=cv2.INTER_NEAREST)
            cnts_sec, _ = cv2.findContours(sec_2x, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            if cnts_sec:
                th_ext_2x = max(2, int(round(TISSUES['rhizodermis']['th_ext_pt'] * pt_scale * 2.0)))
                mask_sec = np.zeros((h * 2, w * 2), dtype=np.uint8)
                cv2.drawContours(mask_sec, cnts_sec, -1, 255, th_ext_2x, cv2.LINE_AA)
                idx_s = (mask_sec > 0)
                wall_2x_bgr[idx_s] = TISSUES['rhizodermis']['wall_col']
                wall_2x_alpha[idx_s] = np.maximum(wall_2x_alpha[idx_s], mask_sec[idx_s] / 255.0)

        # Endodermis continuous outer ring (1.2 pt)
        if comp_stele and ep_rep:
            th_endo_2x = max(2, int(round(TISSUES['endodermis']['th_ring_pt'] * pt_scale * 2.0)))
            box_endo_2x = (
                (cx_s * 2.0, cy_s * 2.0),
                (maj_s * s_endo * 2.0, min_s * s_endo * 2.0),
                angle_s
            )
            mask_e = np.zeros((h * 2, w * 2), dtype=np.uint8)
            cv2.ellipse(mask_e, box_endo_2x, 255, th_endo_2x, cv2.LINE_AA)
            # Mask out metaxylem so endodermis line never slices into a vessel
            mx_2x_u8 = cv2.resize(mx_completed_mask.astype(np.uint8), (w * 2, h * 2), interpolation=cv2.INTER_NEAREST)
            mask_e[mx_2x_u8 > 0] = 0
            idx_e = (mask_e > 0)
            wall_2x_bgr[idx_e] = TISSUES['endodermis']['wall_col']
            wall_2x_alpha[idx_e] = np.maximum(wall_2x_alpha[idx_e], mask_e[idx_e] / 255.0)

        # -------------------------------------------------------------
        # STEP 8: RENDER COMPLETED METAXYLEM ON TOP (Clean Smooth Ellipses)
        # -------------------------------------------------------------
        # Downsample vector walls to 1x and blend onto canvas
        wall_1x_bgr = cv2.resize(wall_2x_bgr, (w, h), interpolation=cv2.INTER_AREA)
        wall_1x_alpha = cv2.resize(wall_2x_alpha, (w, h), interpolation=cv2.INTER_AREA)
        alpha_3ch = np.dstack([wall_1x_alpha, wall_1x_alpha, wall_1x_alpha])
        pub_figure = ((1.0 - alpha_3ch) * canvas + alpha_3ch * wall_1x_bgr).astype(np.uint8)

        # Now paint completed regular metaxylem vessels on top:
        # 1. Fill lumen with Vert très pâle / Céladon
        col_mx_fill = np.array(TISSUES['metaxylem']['vibrant'], dtype=np.uint8)
        col_mx_wall = TISSUES['metaxylem']['wall_col']
        th_mx_wall_px = max(2, int(round(TISSUES['metaxylem']['th_pt'] * pt_scale)))

        for ell in mx_ellipses:
            # Filled lumen
            cv2.ellipse(pub_figure, ell, tuple(map(int, col_mx_fill)), -1)
            # Smooth regular contour
            cv2.ellipse(pub_figure, ell, col_mx_wall, th_mx_wall_px, cv2.LINE_AA)

        # -------------------------------------------------------------
        # STEP 9: Publication Legend & Accounting Side Panel
        # -------------------------------------------------------------
        draw_legend = bool(params.get('draw_legend', True))
        draw_scale  = bool(params.get('draw_scale_bar', True))

        if draw_legend or draw_scale:
            panel_w = 390
            comp = np.full((h, w + panel_w, 3), 255, dtype=np.uint8)
            comp[:, :w] = pub_figure
            cv2.line(comp, (w, 0), (w, h), (220, 220, 225), 1, cv2.LINE_AA)

            px_y = 36
            cv2.putText(comp, 'HISTOLOGIE RACINAIRE', (w + 20, px_y), cv2.FONT_HERSHEY_DUPLEX, 0.68, (20, 20, 30), 2, cv2.LINE_AA)
            px_y += 22
            cv2.putText(comp, 'Zonage & Reconstitution Metaxylemes', (w + 20, px_y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (100, 100, 115), 1, cv2.LINE_AA)
            px_y += 14
            cv2.line(comp, (w + 20, px_y), (w + panel_w - 20, px_y), (230, 230, 235), 1, cv2.LINE_AA)
            px_y += 24

            cv2.putText(comp, 'NOMENCLATURE ANATOMIQUE & STYLES', (w + 20, px_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (120, 120, 130), 1, cv2.LINE_AA)
            px_y += 20

            LEGEND_ITEMS = [
                ('Rhizoderme / Assise sub.', '1.5 / 0.75 pt', TISSUES['rhizodermis']['vibrant'], TISSUES['rhizodermis']['wall_col'], False),
                ('Cortex externe (reserve)',   '0.75 pt',       TISSUES['outer_cortex']['vibrant'], TISSUES['outer_cortex']['wall_col'], False),
                ('Cortex interne (aerifere)',  '0.75 pt',       TISSUES['inner_cortex']['vibrant'], TISSUES['inner_cortex']['wall_col'], False),
                ('Lacunes (Aerenchyme)',       '0.35 pt 45 deg', (255, 255, 255),                  (51, 51, 51),                        True),
                ('Endoderme (Caspary)',        '1.2 / 0.6 pt',  TISSUES['endodermis']['vibrant'],   TISSUES['endodermis']['wall_col'],   False),
                ('Phloeme primaire',           '0.4 pt',        TISSUES['vascular']['vibrant'],     TISSUES['vascular']['wall_col'],     False),
                ('Metaxyleme (Ellipses reg.)', '1.2 pt net',    TISSUES['metaxylem']['vibrant'],    TISSUES['metaxylem']['wall_col'],    False),
                ('Moelle centrale (Pith)',     '0.5 pt',        TISSUES['pith']['vibrant'],         TISSUES['pith']['wall_col'],         False),
            ]

            for name, th_badge, vib_col, w_col, is_hatch in LEGEND_ITEMS:
                cv2.rectangle(comp, (w + 20, px_y - 12), (w + 55, px_y + 8), vib_col, -1)
                if is_hatch:
                    cv2.line(comp, (w + 22, px_y + 6), (w + 53, px_y - 10), (51, 51, 51), 1, cv2.LINE_AA)
                cv2.rectangle(comp, (w + 20, px_y - 12), (w + 55, px_y + 8), w_col, 1, cv2.LINE_AA)
                cv2.putText(comp, name, (w + 64, px_y + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (30, 30, 40), 1, cv2.LINE_AA)
                cv2.putText(comp, th_badge, (w + panel_w - 95, px_y + 1), cv2.FONT_HERSHEY_DUPLEX, 0.35, (80, 50, 140), 1, cv2.LINE_AA)
                px_y += 28

            px_y += 10
            cv2.line(comp, (w + 20, px_y), (w + panel_w - 20, px_y), (230, 230, 235), 1, cv2.LINE_AA)
            px_y += 24

            cv2.putText(comp, 'COMPTABILITE PREDICTIVE STELE & MOELLE', (w + 20, px_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (120, 120, 130), 1, cv2.LINE_AA)
            px_y += 20

            ACC_STATS = [
                ('Metaxylemes completes (ellipses)', f'{len(mx_ellipses)} vaisseaux reguliers ({area_mx_total:.0f} px^2)'),
                ('Moelle centrale observee', f'{n_pith_obs} cellules ({pith_completeness:.1f}% couverte)'),
                ('Cellules moelle manquantes (pred.)', f'+{n_pith_missing_pred} cellules inferees'),
                ('Population moelle predite totale', f'{n_pith_total_pred} cellules isodiametriques'),
                ('Phloeme & parenchyme vasc. (pred.)', f'{len(vasc_obs_cells)} obs. / {n_vasc_total_pred} pred. (+{n_vasc_missing_pred})'),
                ('Monocouche endodermique (anneau)', f'{n_endo_obs} obs. / {n_endo_pred} cellules pred. (+{n_endo_missing})'),
                ('Lacunes corticales detectees', f'{lacunae_count} cavites | {total_lacunae_area} px^2'),
            ]

            for label_s, val_s in ACC_STATS:
                cv2.putText(comp, label_s, (w + 20, px_y), cv2.FONT_HERSHEY_SIMPLEX, 0.37, (90, 40, 130), 1, cv2.LINE_AA)
                px_y += 16
                cv2.putText(comp, val_s, (w + 30, px_y), cv2.FONT_HERSHEY_DUPLEX, 0.37, (30, 30, 40), 1, cv2.LINE_AA)
                px_y += 22

            if draw_scale:
                bar_um = int(params.get('scale_bar_um', 200))
                px_um = float(params.get('pixel_size_um', 0.50))
                bar_px = int(round(bar_um / px_um))

                sb_x1, sb_y1 = w - bar_px - 40, h - 35
                sb_x2, sb_y2 = w - 40, sb_y1
                cv2.line(pub_figure, (sb_x1, sb_y1), (sb_x2, sb_y2), (20, 20, 30), 4, cv2.LINE_AA)
                cv2.putText(pub_figure, f'{bar_um} um', (sb_x1 + 10, sb_y1 - 10), cv2.FONT_HERSHEY_DUPLEX, 0.46, (20, 20, 30), 1, cv2.LINE_AA)

                comp[:, :w] = pub_figure
                py_sb = h - 55
                cv2.putText(comp, 'ECHELLE', (w + 20, py_sb), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (120, 120, 130), 1, cv2.LINE_AA)
                cv2.line(comp, (w + 20, py_sb + 16), (w + 20 + min(120, bar_px), py_sb + 16), (20, 20, 30), 4, cv2.LINE_AA)
                cv2.putText(comp, f'{bar_um} um ({bar_px} px @ {px_um} um/px)', (w + 20, py_sb + 34), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (80, 80, 90), 1, cv2.LINE_AA)

            figure_with_legend = comp
        else:
            figure_with_legend = pub_figure

        return {
            'main': pub_figure,
            'figure_with_legend': figure_with_legend,
            'predictive_report': pred_report,
        }
