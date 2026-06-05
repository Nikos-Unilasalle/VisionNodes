"""
Banc de test end-to-end du pipeline TD6 : reader → (PCA | U-Net) → compare → monitor.

Exécute les VRAIS plugins comme le fait l'engine, avec de vraies données SST.
Sauvegarde les previews PNG pour inspection visuelle et mesure le temps d'entraînement.

Usage:
    .venv/bin/python engine/tests/test_unet_pipeline.py
"""
import os
import sys
import time

# Permettre 'from registry import ...' dans les plugins
_HERE = os.path.dirname(os.path.abspath(__file__))
_ENGINE = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_ENGINE)
sys.path.insert(0, _ENGINE)
sys.path.insert(0, os.path.join(_ENGINE, 'plugins'))

import numpy as np
import cv2
import xarray as xr

import registry  # noqa: E402

OUT_DIR = os.path.join(_HERE, '_test_out')
os.makedirs(OUT_DIR, exist_ok=True)


def drain_notifications(tag=''):
    msgs = []
    while not registry._notification_queue.empty():
        try:
            m = registry._notification_queue.get_nowait()
            if not m.get('_wake_engine'):
                msgs.append(m)
        except Exception:
            break
    for m in msgs:
        lvl = m.get('level', 'info')
        print(f"   [notif/{lvl}] {m.get('message','')}")
    return msgs


def load_real_sst():
    """Charge le sample via le VRAI plugin geo_netcdf_reader (comme l'app)."""
    from geo_netcdf_reader import NetCDFGridReaderNode
    reader = NetCDFGridReaderNode()
    sample = os.path.join(_ROOT, 'samples', 'ocean_temperature.nc')
    out = reader.process({}, {'path': sample, 'variable': 'thetao',
                              'lat_range': '', 'lon_range': '', 'colormap': 0})
    grids = out.get('grids')
    meta  = out.get('meta')
    if grids is None:
        raise SystemExit(f"reader a renvoyé grids=None pour {sample}")
    return grids.astype(np.float32), meta


def save_preview(name, img):
    if img is None:
        print(f"   ⚠ preview '{name}' is None")
        return
    if img.ndim == 3 and img.shape[2] == 3:
        # plugins renvoient du RGB → cv2 attend BGR pour l'écriture
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    path = os.path.join(OUT_DIR, f'{name}.png')
    cv2.imwrite(path, img)
    print(f"   ✓ preview saved: {path}  shape={img.shape}")


def main():
    from ml_unet_grid import MLUNetGridNode
    from ml_grid_pca import SpatialGridPCANode

    print("=" * 70)
    print("BANC DE TEST — Pipeline TD6 U-Net")
    print("=" * 70)

    grids, meta = load_real_sst()
    print(f"\n[1] Données SST chargées : shape={grids.shape}  "
          f"NaN={np.isnan(grids).mean():.1%}  "
          f"range={np.nanmin(grids):.2f}→{np.nanmax(grids):.2f}°C")

    # ── PCA (référence) ──────────────────────────────────────────────────
    print("\n[2] PCA spatiale (EOF)...")
    pca = SpatialGridPCANode()
    pca_out = pca.process({'grids': grids, 'meta': meta},
                          {'n_components': 10, 'standardize': True,
                           'detrend': 1, 'cos_lat': False, 'solver': 0, 'colormap': 0})
    drain_notifications()
    pca_recon = pca_out.get('reconstructed')
    print(f"   PCA reconstructed: {None if pca_recon is None else pca_recon.shape}, "
          f"MSE={pca_out.get('mse')}")
    save_preview('pca_preview', pca_out.get('preview'))

    # ── U-Net ────────────────────────────────────────────────────────────
    print("\n[3] U-Net — lancement entraînement (trigger)...")
    unet = MLUNetGridNode()
    params = {'n_latent': 16, 'n_levels': 3, 'n_epochs': 30, 'batch_size': 8,
              'learning_rate': 0.001, 'val_split': 0.2, 'colormap': 0, 'train': 1}

    # 1er appel = trigger rising edge → démarre le thread
    out = unet.process({'grids': grids, 'meta': meta}, params)
    drain_notifications()
    print(f"   retour initial keys: {list(out.keys())}  "
          f"loss_history={out.get('loss_history')}")

    # Simuler la boucle engine (~30fps) : train désormais = 0 (pas de re-trigger)
    params_poll = {**params, 'train': 0}
    t0 = time.time()
    last_epoch = -1
    final_out = None
    for i in range(600):  # max 60s
        time.sleep(0.1)
        out = unet.process({'grids': grids, 'meta': meta}, params_poll)
        with unet._lock:
            state = unet._state
            epoch = unet._current_epoch
            total = unet._total_epochs
        if epoch != last_epoch:
            lh = out.get('loss_history', {})
            tl = lh.get('train_loss', [])
            vl = lh.get('val_loss', [])
            tls = f"{tl[-1]:.5f}" if tl else "—"
            vls = f"{vl[-1]:.5f}" if vl else "—"
            print(f"   epoch {epoch}/{total}  state={state}  train={tls} val={vls}  "
                  f"hist_len={len(tl)}")
            last_epoch = epoch
        drain_notifications()
        if state in ('done', 'error'):
            final_out = out
            break
    elapsed = time.time() - t0
    print(f"   ⏱ entraînement terminé en {elapsed:.1f}s  état={state}")

    if state == 'error':
        print("   ❌ ERREUR pendant l'entraînement")
        return 1

    # Vérifs sur le retour final
    recon = final_out.get('reconstructed')
    lh = final_out.get('loss_history', {})
    print(f"\n[4] Vérifications retour final U-Net:")
    print(f"   reconstructed: {None if recon is None else recon.shape}")
    print(f"   mse: {final_out.get('mse')}")
    print(f"   loss_history train: {len(lh.get('train_loss', []))} pts, "
          f"val: {len(lh.get('val_loss', []))} pts")
    print(f"   model_bundle keys: {list((final_out.get('model_bundle') or {}).keys())}")
    save_preview('unet_preview', final_out.get('preview'))

    assert recon is not None, "reconstructed est None !"
    assert recon.shape == grids.shape, f"shape mismatch {recon.shape} vs {grids.shape}"
    assert len(lh.get('train_loss', [])) == 30, "loss_history train incomplet"
    assert len(lh.get('val_loss', [])) == 30, "loss_history val incomplet"
    # La loss doit décroître
    tl = lh['train_loss']
    assert tl[-1] < tl[0], f"la loss ne décroît pas ! {tl[0]:.4f} → {tl[-1]:.4f}"
    print(f"   ✓ loss décroît : {tl[0]:.5f} → {tl[-1]:.5f}")

    # ── Training Monitor ─────────────────────────────────────────────────
    print("\n[5] Training Monitor...")
    from ml_training_monitor import MLTrainingMonitorNode
    mon = MLTrainingMonitorNode()
    mon_out = mon.process({'loss_history': lh},
                          {'log_scale': False, 'show_best': True, 'smooth': 3})
    drain_notifications()
    print(f"   best_epoch={mon_out.get('best_epoch')}  "
          f"final_train={mon_out.get('final_train_loss'):.5f}  "
          f"final_val={mon_out.get('final_val_loss'):.5f}")
    save_preview('monitor_preview', mon_out.get('preview'))

    # ── Model save/load ──────────────────────────────────────────────────
    print("\n[6] Model Saver / Loader...")
    from ml_model_saver import MLModelSaverNode
    from ml_model_loader import MLModelLoaderNode
    save_path = os.path.join(OUT_DIR, 'test_unet.pt')
    saver = MLModelSaverNode()
    saver.process({'model_bundle': final_out['model_bundle']},
                  {'path': save_path, 'save': 1})
    drain_notifications()
    exists = os.path.exists(save_path)
    print(f"   sauvegarde existe: {exists}  "
          f"({os.path.getsize(save_path)//1024 if exists else 0} KB)")
    assert exists, "le modèle n'a pas été sauvegardé !"

    loader = MLModelLoaderNode()
    load_out = loader.process({'grids': grids}, {'path': save_path, 'load': 1})
    drain_notifications()
    lrec = load_out.get('reconstructed')
    print(f"   rechargé → reconstructed: {None if lrec is None else lrec.shape}  "
          f"mse={load_out.get('mse')}")
    assert lrec is not None, "le loader n'a pas reconstruit !"

    print("\n" + "=" * 70)
    print("✅ PIPELINE COMPLET FONCTIONNEL")
    print(f"   Previews dans : {OUT_DIR}")
    print("=" * 70)
    return 0


if __name__ == '__main__':
    sys.exit(main())
