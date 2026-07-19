import { useCallback, useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Smartphone, X } from 'lucide-react';

interface Pairing {
  ip: string;
  port: number;
  token: string;
  qr_svg: string;
}

/**
 * VNPad pairing panel: a phone-shaped trigger button that opens a modal with a
 * QR code the mobile pad scans to connect over the LAN. Self-contained — drop
 * `<VNPadPairing />` anywhere; it owns its open state and data fetch.
 */
export function VNPadPairing() {
  const [isOpen, setIsOpen] = useState(false);
  const [pairing, setPairing] = useState<Pairing | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadPairing = useCallback(async () => {
    setError(null);
    try {
      const result = await invoke<Pairing>('vnpad_pairing');
      setPairing(result);
    } catch (e: unknown) {
      setError(typeof e === 'string' ? e : 'Could not reach the VNPad server.');
    }
  }, []);

  useEffect(() => {
    if (isOpen) loadPairing();
  }, [isOpen, loadPairing]);

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        title="Connect a VNPad (phone / tablet)"
        className="bg-[#1e2530]/90 hover:bg-[#2a3340] backdrop-blur border border-accent/30 text-gray-200 p-2 px-4 rounded-full shadow-lg transition-all font-black text-[10px] tracking-widest uppercase flex items-center gap-2 self-start"
      >
        <Smartphone size={14} /> VNPad
      </button>

      {isOpen && (
        <div
          className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setIsOpen(false)}
        >
          <div
            className="relative w-[340px] rounded-2xl border border-accent/30 bg-[#141922] p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setIsOpen(false)}
              className="absolute right-4 top-4 text-gray-500 hover:text-white transition-colors"
              title="Close"
            >
              <X size={18} />
            </button>

            <div className="mb-4 flex items-center gap-2 text-white">
              <Smartphone size={18} className="text-accent" />
              <h2 className="text-sm font-black uppercase tracking-widest">Connect a VNPad</h2>
            </div>

            {error && (
              <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2 text-xs text-red-300">
                {error}
              </div>
            )}

            {!error && !pairing && (
              <div className="py-10 text-center text-xs text-gray-500">Starting server…</div>
            )}

            {pairing && (
              <div className="flex flex-col items-center gap-4">
                <div
                  className="rounded-xl bg-white p-3"
                  // QR SVG is generated locally by the Rust server, not user content.
                  dangerouslySetInnerHTML={{ __html: pairing.qr_svg }}
                />
                <p className="text-center text-[11px] leading-relaxed text-gray-400">
                  Open the <span className="font-bold text-gray-200">VNPad</span> app on your phone
                  and scan this code. Both devices must share the same Wi-Fi.
                </p>
                <div className="w-full rounded-lg bg-[#0d1017] px-3 py-2 font-mono text-[11px] text-gray-300">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Address</span>
                    <span>{pairing.ip}:{pairing.port}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Code</span>
                    <span className="tracking-widest text-accent">{pairing.token}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
