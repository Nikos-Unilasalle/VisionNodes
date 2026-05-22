def enable_hf_ui_progress(notif_id, prefix_msg="Downloading"):
    try:
        from huggingface_hub import utils as hf_utils
        import tqdm

        class UI_Tqdm(tqdm.tqdm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._notif_id = notif_id
                self._prefix_msg = prefix_msg
                self._last_notif = 0

            def update(self, n=1):
                super().update(n)
                if getattr(self, 'total', None):
                    pct = self.n / self.total
                    if pct - self._last_notif > 0.05 or pct == 1.0:  # Send update every 5%
                        desc = getattr(self, 'desc', '')
                        msg = f"{self._prefix_msg} {desc}: {int(pct*100)}%"
                        print(f"send_notification: {msg} progress={pct}")
                        self._last_notif = pct

        hf_utils.tqdm = UI_Tqdm
        print("Patched hf_utils.tqdm")
    except ImportError:
        print("huggingface_hub not available")

enable_hf_ui_progress("my_notif")
