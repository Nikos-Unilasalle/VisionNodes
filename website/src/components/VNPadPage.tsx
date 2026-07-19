import React from 'react';
import { motion } from 'framer-motion';
import {
  Download, Github, ExternalLink, Smartphone, QrCode, Wifi,
  LayoutGrid, Maximize2, Sparkles, ShieldCheck, MoveHorizontal,
} from 'lucide-react';

// Release tag the direct-download asset is pinned to. `VNPad.apk` is published
// under a stable filename by the release workflow, so only this constant moves.
const VERSION = '0.1.0';
const REPO = 'https://github.com/Nikos-Unilasalle/VNPad';
const APK_URL = `${REPO}/releases/download/v${VERSION}/VNPad.apk`;

interface Feature {
  icon: React.ReactNode;
  title: string;
  body: string;
}

const FEATURES: Feature[] = [
  {
    icon: <LayoutGrid size={22} strokeWidth={1.5} />,
    title: 'Programmable pads',
    body: 'Each pad drops a specific node onto the canvas. Pick the node by name, set its default parameters, colour and icon — no code, no node IDs to memorise.',
  },
  {
    icon: <MoveHorizontal size={22} strokeWidth={1.5} />,
    title: 'Pages you swipe',
    body: 'Group pads into boards — one for filters, one for analysis, one per lecture. Swipe between them mid-session without touching the desktop.',
  },
  {
    icon: <Sparkles size={22} strokeWidth={1.5} />,
    title: 'Backlit keys',
    body: 'Photoreal, colour-lit pads that glow and flash on press, with a haptic tick and a soft click. Individual sizes, so the pads you use most can be twice as big.',
  },
  {
    icon: <Maximize2 size={22} strokeWidth={1.5} />,
    title: 'Fullscreen sessions',
    body: 'Once the board is set, hide every bit of chrome — including the Android system bars — and turn the tablet into a dedicated control surface.',
  },
];

const STEPS = [
  {
    icon: <Wifi size={20} strokeWidth={1.5} />,
    title: 'Same Wi-Fi',
    body: 'Put the phone or tablet on the same local network as the machine running VNStudio.',
  },
  {
    icon: <QrCode size={20} strokeWidth={1.5} />,
    title: 'Scan the QR',
    body: 'Click VNPad in VNStudio\'s toolbar. A QR appears carrying the address and a one-session pairing code. Scan it.',
  },
  {
    icon: <Smartphone size={20} strokeWidth={1.5} />,
    title: 'Tap to build',
    body: 'Every tap sends the node straight onto the canvas. Edit pads any time from the phone.',
  },
];

const VNPadPage = () => (
  <motion.div key="vnpad" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
    {/* Hero */}
    <section className="section-full section-alt" style={{ paddingTop: '5rem', paddingBottom: '3.5rem' }}>
      <div className="container-md text-center">
        <p className="text-[11px] font-bold uppercase tracking-widest text-[var(--accent)] mb-4">
          Android Companion
        </p>
        <h1 className="text-[44px] md:text-[56px] text-[var(--text-main)] mb-6 leading-tight">
          VNPad
        </h1>
        <p className="text-[18px] text-[var(--text-dim)] leading-relaxed max-w-2xl mx-auto mb-8">
          Turn any Android phone or tablet into a physical control surface for VisionNodes Studio.
          A grid of backlit, programmable keys — tap one, the node lands on your canvas.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <a href={APK_URL} target="_blank" rel="noreferrer" className="btn-primary no-underline">
            <Download size={15} /> Download APK
          </a>
          <a href={REPO} target="_blank" rel="noreferrer" className="btn-secondary no-underline">
            <Github size={15} /> Source <ExternalLink size={12} />
          </a>
        </div>
        <p className="text-[12.5px] text-[var(--text-dim)] mt-4">
          Android 8.0+ · free and open source · v{VERSION}
        </p>
      </div>
    </section>

    {/* Features */}
    <section className="section-full" style={{ paddingTop: '3rem' }}>
      <div className="container-lg">
        <div className="grid md:grid-cols-2 gap-5">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              className="vn-card p-8"
            >
              <div className="w-11 h-11 rounded-xl flex items-center justify-center mb-5 bg-[var(--accent)]/10 text-[var(--accent)]">
                {f.icon}
              </div>
              <h3 className="text-[19px] text-[var(--text-main)] mb-2">{f.title}</h3>
              <p className="text-[14px] text-[var(--text-dim)] leading-relaxed">{f.body}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>

    {/* Pairing */}
    <section className="section-full section-alt" style={{ paddingTop: '3.5rem', paddingBottom: '3.5rem' }}>
      <div className="container-lg">
        <h2 className="text-[30px] text-[var(--text-main)] text-center mb-3">Paired in three steps</h2>
        <p className="text-[15px] text-[var(--text-dim)] text-center max-w-xl mx-auto mb-10">
          No account, no cloud, no cable. Everything stays on your local network.
        </p>
        <div className="grid md:grid-cols-3 gap-5">
          {STEPS.map((s, i) => (
            <div key={s.title} className="vn-card p-7">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-[var(--accent)]/10 text-[var(--accent)] shrink-0">
                  {s.icon}
                </div>
                <span className="text-[11px] font-bold uppercase tracking-widest text-[var(--text-dim)]">
                  Step {i + 1}
                </span>
              </div>
              <h3 className="text-[17px] text-[var(--text-main)] mb-1.5">{s.title}</h3>
              <p className="text-[13.5px] text-[var(--text-dim)] leading-relaxed">{s.body}</p>
            </div>
          ))}
        </div>

        <div className="vn-card-flat max-w-3xl mx-auto mt-8 p-6 rounded-2xl">
          <div className="flex items-start gap-3">
            <ShieldCheck size={20} strokeWidth={1.5} className="mt-0.5 shrink-0 text-[var(--accent)]" />
            <div>
              <h4 className="text-[15px] font-semibold text-[var(--text-main)] mb-1">
                Local network only
              </h4>
              <p className="text-[13px] text-[var(--text-dim)] leading-relaxed">
                VNPad talks to VNStudio over a plain WebSocket on your LAN, guarded by a pairing
                code regenerated every session. The Python engine stays bound to localhost and is
                never exposed to the network. Nothing is sent to any server.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>

    {/* Install */}
    <section className="section-full" style={{ paddingTop: '3rem' }}>
      <div className="container-lg">
        <div className="vn-card-flat p-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 mb-5">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 bg-[var(--accent)]/10 text-[var(--accent)]">
              <Download size={20} strokeWidth={1.5} />
            </div>
            <div>
              <h3 className="text-[18px] text-[var(--text-main)] mb-1">Install the APK</h3>
              <p className="text-[14px] text-[var(--text-dim)] leading-relaxed">
                VNPad is distributed outside the Play Store, so Android will ask you to allow
                installs from your browser the first time. Open the downloaded file and confirm.
              </p>
            </div>
          </div>
          <a href={APK_URL} target="_blank" rel="noreferrer" className="btn-primary shrink-0 no-underline">
            <Download size={15} /> VNPad.apk
          </a>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div className="vn-card p-6">
            <h4 className="text-[15px] text-[var(--text-main)] mb-3">Requirements</h4>
            <ul className="space-y-1.5 text-[13px] text-[var(--text-dim)]">
              <li>• Android 8.0 (API 26) or newer</li>
              <li>• Phone or tablet on the same Wi-Fi as VNStudio</li>
              <li>• Camera, to scan the pairing QR (optional — the address can be typed)</li>
              <li>• VNStudio 0.1.2+ on the desktop</li>
            </ul>
          </div>
          <div className="vn-card p-6">
            <h4 className="text-[15px] text-[var(--text-main)] mb-3">Build from source</h4>
            <p className="text-[13px] text-[var(--text-dim)] leading-relaxed mb-3">
              Kotlin and Jetpack Compose, single Gradle module. Requires JDK 21.
            </p>
            <a href={REPO} target="_blank" rel="noreferrer" className="btn-secondary no-underline">
              <Github size={15} /> GitHub Repository <ExternalLink size={12} />
            </a>
          </div>
        </div>
      </div>
    </section>
  </motion.div>
);

export default VNPadPage;
