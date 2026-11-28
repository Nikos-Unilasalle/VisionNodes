"""Tests for packaged-binary runtime resource, path, SSL, stdio, and download helpers."""
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import registry  # noqa: E402


def test_configure_runtime_recovers_none_stdio(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "VN_HOME", str(tmp_path))
    monkeypatch.setattr(registry, "VN_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setattr(registry, "VN_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("TORCH_HOME", raising=False)
    monkeypatch.delenv("YOLO_CONFIG_DIR", raising=False)
    monkeypatch.delenv("EASYOCR_MODULE_PATH", raising=False)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    try:
        registry.configure_runtime_environment()
        assert sys.stdout is not None
        assert sys.stderr is not None
        print("hello-from-gui-mode")
        assert os.environ["HF_HOME"] == str(tmp_path / "cache" / "huggingface")
        assert os.environ["TORCH_HOME"] == str(tmp_path / "cache" / "torch")
        assert os.environ["YOLO_CONFIG_DIR"] == str(tmp_path / "cache" / "ultralytics")
        assert os.environ["EASYOCR_MODULE_PATH"] == str(tmp_path / "models" / "easyocr")
        assert os.path.isdir(tmp_path / "models")
        assert os.path.isdir(tmp_path / "cache")
    finally:
        for s in (sys.stdout, sys.stderr):
            if s is not None and s not in (sys.__stdout__, sys.__stderr__):
                try:
                    s.close()
                except Exception:
                    pass


def test_get_model_path_prefers_existing_else_writable_user_dir(tmp_path, monkeypatch):
    models_dir = tmp_path / "models"
    monkeypatch.setattr(registry, "VN_MODELS_DIR", str(models_dir))
    monkeypatch.setattr(registry, "VN_HOME", str(tmp_path))
    monkeypatch.setattr(registry, "_app_candidate_roots", lambda: [str(tmp_path / "empty")])

    target = registry.get_model_path("pose_landmarker.task")
    assert target == str(models_dir / "pose_landmarker.task")
    assert os.path.isdir(models_dir)

    # Bundled read-only model is discovered if present and non-empty
    bundled = tmp_path / "bundle" / "resources" / "face_landmarker.task"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"task-bytes")
    monkeypatch.setattr(registry, "_app_candidate_roots", lambda: [str(tmp_path / "bundle")])
    assert registry.get_model_path("face_landmarker.task") == str(bundled)


def test_get_cache_dir_avoids_bundle_dir_when_packaged(tmp_path, monkeypatch):
    cache_root = tmp_path / "user_cache"
    monkeypatch.setattr(registry, "VN_CACHE_DIR", str(cache_root))
    monkeypatch.setattr(registry, "_USE_USER_OVERLAY", True)

    fake_plugin = tmp_path / "readonly_bundle" / "plugins" / "geo_copernicus.py"
    fake_plugin.parent.mkdir(parents=True)
    fake_plugin.write_text("# plugin")

    resolved = registry.get_cache_dir("copernicus_cache", "copernicus_cache", anchor_file=str(fake_plugin))
    assert resolved == str(cache_root / "copernicus_cache")
    assert os.path.isdir(resolved)
    assert not (fake_plugin.parent / "copernicus_cache").exists()

    # Explicit absolute path is always respected
    explicit = tmp_path / "custom_abs"
    assert registry.get_cache_dir("copernicus_cache", str(explicit), anchor_file=str(fake_plugin)) == str(explicit)
    assert os.path.isdir(explicit)


def test_resolve_resource_path_finds_samples_next_to_macos_app(tmp_path, monkeypatch):
    # Simulate /tmp/.../Downloads/VNStudio.app/Contents/MacOS/vnstudio
    app_parent = tmp_path / "Downloads"
    macos_bin_dir = app_parent / "VNStudio.app" / "Contents" / "MacOS"
    macos_bin_dir.mkdir(parents=True)
    sample = app_parent / "samples" / "unique_bundled_sample.jpg"
    sample.parent.mkdir(parents=True)
    sample.write_bytes(b"jpg")

    unrelated_cwd = tmp_path / "unrelated"
    unrelated_cwd.mkdir()
    monkeypatch.chdir(unrelated_cwd)
    monkeypatch.setenv("VNSTUDIO_APP_DIR", str(macos_bin_dir))
    monkeypatch.setattr(registry, "VN_HOME", str(tmp_path / "vn_home"))

    assert registry.resolve_resource_path("samples/unique_bundled_sample.jpg") == str(sample)


def test_download_file_atomic_and_cleans_up_on_short_payload(tmp_path):
    payload = b"x" * 2048

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/ok":
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                self.send_response(200)
                self.send_header("Content-Length", "10")
                self.end_headers()
                self.wfile.write(b"tiny")

        def log_message(self, *args):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        port = srv.server_address[1]
        ok_dest = tmp_path / "models" / "ok.bin"
        out = registry.download_file(f"http://127.0.0.1:{port}/ok", str(ok_dest), min_bytes=1024, retries=1)
        assert out == str(ok_dest)
        assert ok_dest.read_bytes() == payload
        assert not list(ok_dest.parent.glob("*.part*"))

        bad_dest = tmp_path / "models" / "bad.bin"
        with pytest.raises(RuntimeError):
            registry.download_file(f"http://127.0.0.1:{port}/bad", str(bad_dest), min_bytes=1024, retries=1)
        assert not bad_dest.exists()
        assert not list(bad_dest.parent.glob("*.part*"))
    finally:
        srv.shutdown()
        srv.server_close()


def test_from_pretrained_cached_falls_back_to_local_files_only():
    calls = []

    def fake_loader(repo_id, **kwargs):
        calls.append((repo_id, dict(kwargs)))
        if not kwargs.get("local_files_only"):
            raise ConnectionError("offline")
        return "cached-model"

    assert registry.from_pretrained_cached(fake_loader, "org/model") == "cached-model"
    assert calls == [("org/model", {}), ("org/model", {"local_files_only": True})]


def test_gaze_estimator_autodownloads_missing_weights(tmp_path, monkeypatch):
    from plugins import analysis_gaze

    node = analysis_gaze.GazeEstimatorNode()
    missing_ckpt = tmp_path / "models" / "gaze_estimator.pth.tar"
    calls = []

    def fake_download(url, dest_path, **kwargs):
        calls.append((url, dest_path, kwargs))
        raise RuntimeError("offline-sentinel")

    monkeypatch.setattr(analysis_gaze, "download_file", fake_download)
    node._load_in_thread(str(missing_ckpt))

    assert len(calls) == 1
    assert calls[0][0] == analysis_gaze._GAZE_WEIGHTS_URL
    assert calls[0][0].endswith("/releases/download/models/gaze_estimator.pth.tar")
    assert calls[0][1] == str(missing_ckpt)
    assert calls[0][2]["min_bytes"] >= 100_000_000
    assert str(missing_ckpt) in node._failed
