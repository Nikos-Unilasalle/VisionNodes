import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Play, ChevronRight, ArrowLeft, Terminal, Sparkles, Code2, CheckCircle2, Zap, Eye, BarChart2, Users } from 'lucide-react';

// ─── Tutorial data ───────────────────────────────────────────────────────────

const TUTORIALS = [
  {
    id: 'object-tracking',
    level: 'Advanced',
    title: 'Real-Time Multi-Object Tracking',
    summary: 'Combine YOLOv8 detection with the SORT algorithm to track objects with persistent IDs and motion trails.',
    icon: <Eye size={20} strokeWidth={1.5} />,
    accent: '#60a5fa',
    steps: [
      { title: 'Set up the video source', content: 'Add a Webcam or Video File node. Connect its main output to a Display node to verify the stream is running before adding processing.' },
      { title: 'Add YOLOv8 detection', content: 'Place a YOLO v8 Detector node. Connect the image output from your source. In the inspector, select your model (yolov8n.pt for speed, yolov8m.pt for accuracy) and set a confidence threshold of 0.4.' },
      { title: 'Add the SORT Tracker', content: 'Connect the Detections output of YOLO to the SORT Tracker node. The tracker will assign persistent numeric IDs to objects across frames using a Kalman filter and Hungarian assignment algorithm.' },
      { title: 'Visualize tracks', content: 'Connect the Tracks output to a Tracker Visualizer node. Configure trail length (30–60 frames) and enable the ID labels. Connect the result to your Display node.' },
    ],
  },
  {
    id: 'smile-detector',
    level: 'Intermediate',
    title: 'Smile Detector & Data Logger',
    summary: 'Use MediaPipe face landmarks to measure the mouth aperture ratio and log smile events to a CSV file.',
    icon: <BarChart2 size={20} strokeWidth={1.5} />,
    accent: '#34d399',
    steps: [
      { title: 'Configure the face tracker', content: 'Place a MediaPipe Face Tracker node. Connect your Webcam output to it. The node outputs 468 facial landmarks as a structured dictionary.' },
      { title: 'Extract mouth metrics', content: 'Add a Geometry → Point Distance node. Extract landmarks 13 (upper lip) and 14 (lower lip) from the face mesh dictionary using a Data → Dict Get node, then feed them into Point Distance to get the vertical mouth aperture.' },
      { title: 'Threshold for smile detection', content: 'Add a Logic → Threshold node. Set the threshold value to 0.05 (relative to face size). When the mouth aperture exceeds this, the boolean output fires True — a smile is detected.' },
      { title: 'Log events to CSV', content: 'Connect the boolean output to a CSV Export node (via a Gate node for edge-triggered logging). Configure the CSV path and column labels. Each smile event writes one timestamped row.' },
    ],
  },
  {
    id: 'ocr-scanner',
    level: 'Intermediate',
    title: 'OCR Document Scanner',
    summary: 'Detect text regions with the EAST detector, deskew with homography, then read content with EasyOCR.',
    icon: <Terminal size={20} strokeWidth={1.5} />,
    accent: '#c084fc',
    steps: [
      { title: 'Detect text regions', content: 'Add an EAST Text Detector node and connect your image source. It outputs rotated bounding boxes around text regions. Adjust the score threshold (0.5) and NMS threshold (0.4) for your document type.' },
      { title: 'Apply perspective correction', content: 'Connect the region boxes to a Region Selector node, then pipe the selected region into a Perspective Warp node. This deskews and crops the text area for optimal OCR accuracy.' },
      { title: 'Run EasyOCR', content: 'Connect the warped region to an EasyOCR Scanner node. Select your target languages. The node returns the raw text string, confidence scores, and bounding boxes for each word.' },
      { title: 'Display overlay', content: 'Use a Draw Text node to overlay the recognized text back onto the original image at the detected position, then connect to Display.' },
    ],
  },
  {
    id: 'industrial-counter',
    level: 'Advanced',
    title: 'Industrial Part Counter',
    summary: 'Apply watershed segmentation to count and measure touching objects in dense industrial scenes.',
    icon: <Zap size={20} strokeWidth={1.5} />,
    accent: '#f87171',
    steps: [
      { title: 'Preprocessing pipeline', content: 'Convert your image to grayscale, then apply a Gaussian Filter (σ=2) to suppress sensor noise. Feed the result through an Adaptive Threshold node to obtain a clean binary mask.' },
      { title: 'Distance transform', content: 'Apply a Distance Transform node to the binary mask. This produces a map where each pixel value equals its distance to the nearest background pixel — peaks correspond to object centers.' },
      { title: 'Marker extraction', content: 'Threshold the distance map at 60–70% of its maximum value, then label connected components with a Connected Components node. These become the "seeds" for watershed.' },
      { title: 'Watershed and count', content: 'Feed the markers and the original mask into the Watershed Analysis node. It segments touching objects along their boundaries. The Marker Analysis node then counts regions and measures area, centroid, and perimeter for each.' },
    ],
  },
  {
    id: 'finger-paint',
    level: 'Intermediate',
    title: 'Interactive Finger Painting',
    summary: 'Use the Hand Tracker to turn your index finger into a virtual brush with color and thickness controls.',
    icon: <Users size={20} strokeWidth={1.5} />,
    accent: '#f472b6',
    steps: [
      { title: 'Detect hand landmarks', content: 'Place a MediaPipe Hand Tracker node connected to your Webcam. It outputs 21 hand landmarks. Extract landmark 8 (index fingertip) using Dict Get.' },
      { title: 'Accumulate trajectory', content: 'Connect the fingertip position to a Trail Accumulator (or use the Python Script node to maintain a deque of the last N positions). This builds the brush stroke path.' },
      { title: 'Draw strokes', content: 'Feed the trajectory to a Draw Polyline node. Configure stroke color (use a Color Picker parameter node) and thickness. Layer strokes onto a blank canvas using an Alpha Blend node.' },
      { title: 'Gesture controls', content: 'Add pinch detection: measure the distance between landmarks 4 (thumb) and 8 (index). When distance < 40px, pause drawing — lifting the pen. Connect to a Gate node to control the trail accumulator.' },
    ],
  },
  {
    id: 'custom-node',
    level: 'Developer',
    title: 'Create Your Own Node',
    summary: 'Write a custom VisionNodes node in Python using the @vision_node decorator. No restart required.',
    icon: <Code2 size={20} strokeWidth={1.5} />,
    accent: '#83b817',
    isCustomNode: true,
  },
];

// ─── Tutorial Card ────────────────────────────────────────────────────────────

const TutorialCard = ({ tut, onClick }: { tut: typeof TUTORIALS[0]; onClick: () => void }) => (
  <motion.div
    initial={{ opacity: 0, y: 16 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    className="vn-card p-6 cursor-pointer group"
    onClick={onClick}
  >
    <div className="flex items-start justify-between gap-3 mb-4">
      <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: tut.accent + '22', color: tut.accent }}>
        {tut.icon}
      </div>
      <span className="text-[11px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full"
            style={{ backgroundColor: tut.accent + '18', color: tut.accent }}>
        {tut.level}
      </span>
    </div>
    <h3 className="text-[17px] text-[var(--text-main)] mb-2 leading-tight">{tut.title}</h3>
    <p className="text-[13px] text-[var(--text-dim)] leading-relaxed mb-5">{tut.summary}</p>
    <div className="flex items-center gap-1 text-[13px] font-semibold" style={{ color: tut.accent }}>
      Read guide <ChevronRight size={14} className="group-hover:translate-x-1 transition-transform" />
    </div>
  </motion.div>
);

// ─── Tutorial Detail ──────────────────────────────────────────────────────────

const TutorialDetail = ({ tut, onBack }: { tut: typeof TUTORIALS[0]; onBack: () => void }) => {
  if (tut.isCustomNode) return <CustomNodeGuide onBack={onBack} />;

  return (
    <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
      <button onClick={onBack} className="flex items-center gap-2 text-[13px] text-[var(--text-dim)] hover:text-[var(--text-main)] mb-8 transition-colors">
        <ArrowLeft size={14} /> Back to Tutorials
      </button>

      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: tut.accent + '22', color: tut.accent }}>
          {tut.icon}
        </div>
        <span className="text-[11px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full"
              style={{ backgroundColor: tut.accent + '18', color: tut.accent }}>
          {tut.level}
        </span>
      </div>

      <h1 className="text-[36px] text-[var(--text-main)] mb-3">{tut.title}</h1>
      <p className="text-[16px] text-[var(--text-dim)] mb-12 max-w-2xl leading-relaxed">{tut.summary}</p>

      <div className="space-y-6 max-w-2xl">
        {tut.steps?.map((step, i) => (
          <div key={i} className="vn-card p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-[12px] font-bold text-white"
                   style={{ backgroundColor: tut.accent }}>
                {i + 1}
              </div>
              <h3 className="text-[16px] text-[var(--text-main)]">{step.title}</h3>
            </div>
            <p className="text-[14px] text-[var(--text-dim)] leading-relaxed pl-10">{step.content}</p>
          </div>
        ))}
      </div>
    </motion.div>
  );
};

// ─── Custom Node Guide ────────────────────────────────────────────────────────

const CustomNodeGuide = ({ onBack }: { onBack: () => void }) => (
  <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="max-w-4xl pb-32">
    <button onClick={onBack} className="flex items-center gap-2 text-[13px] text-[var(--text-dim)] hover:text-[var(--text-main)] mb-10 transition-colors">
      <ArrowLeft size={14} /> Back to Tutorials
    </button>

    <div className="flex items-center gap-4 mb-12">
      <div className="w-14 h-14 rounded-2xl bg-[var(--accent)]/10 flex items-center justify-center text-[var(--accent)]">
        <Code2 size={28} strokeWidth={1.5} />
      </div>
      <div>
        <h1 className="text-[40px] text-[var(--text-main)] leading-none tracking-tight">Node Development Masterclass</h1>
        <p className="text-[15px] text-[var(--accent)] font-medium mt-2">From "Hello World" to Scientific Grade Plugins</p>
      </div>
    </div>

    {/* PHASE 1: SIMPLE */}
    <section className="mb-20">
      <div className="flex items-center gap-3 mb-6">
        <span className="text-[11px] font-bold bg-[var(--text-dim)]/10 text-[var(--text-dim)] px-2 py-1 rounded">PHASE 01</span>
        <h2 className="text-[22px] text-[var(--text-main)]">The Fundamentals</h2>
      </div>
      <div className="vn-card p-8">
        <p className="text-[15px] text-[var(--text-dim)] mb-6 leading-relaxed">
          Every node starts with a <code className="text-[var(--accent)]">.py</code> file in <code className="text-[var(--text-main)]">engine/plugins/</code>. 
          The engine uses hot-reloading: your changes appear in the UI the moment you save.
        </p>
        <div className="code-block text-[13px] leading-6 mb-6">
          <span className="tok-kw">from</span> registry <span className="tok-kw">import</span> vision_node, NodeProcessor{'\n'}
          <span className="tok-kw">import</span> cv2{'\n'}{'\n'}
          <span className="tok-dec">@vision_node</span>({'\n'}
          {'  '}type_id=<span className="tok-str">"simple_invert"</span>,{'\n'}
          {'  '}label=<span className="tok-str">"Invert Colors"</span>,{'\n'}
          {'  '}icon=<span className="tok-str">"RefreshCw"</span>,{'\n'}
          {'  '}category=[<span className="tok-str">"util"</span>],{'\n'}
          {'  '}inputs=[{'{'}<span className="tok-str">"id"</span>:<span className="tok-str">"image"</span>, <span className="tok-str">"color"</span>:<span className="tok-str">"image"</span>{'}'}],{'\n'}
          {'  '}outputs=[{'{'}<span className="tok-str">"id"</span>:<span className="tok-str">"main"</span>, <span className="tok-str">"color"</span>:<span className="tok-str">"image"</span>{'}'}]{'\n'}
          ){'\n'}
          <span className="tok-kw">class</span> <span className="tok-def">InvertNode</span>(NodeProcessor):{'\n'}
          {'  '}<span className="tok-kw">def</span> <span className="tok-def">process</span>(<span className="tok-num">self</span>, inputs, params):{'\n'}
          {'    '}img = inputs.get(<span className="tok-str">'image'</span>){'\n'}
          {'    '}<span className="tok-kw">if</span> img <span className="tok-kw">is</span> <span className="tok-kw">None</span>: <span className="tok-kw">return</span> {'{'}<span className="tok-str">'main'</span>: <span className="tok-kw">None</span>{'}'}{'\n'}
          {'    '}<span className="tok-kw">return</span> {'{'}<span className="tok-str">'main'</span>: <span className="tok-num">255</span> - img{'}'}
        </div>
        <div className="flex items-start gap-3 text-[13px] text-[var(--text-dim)] bg-[var(--bg-alt)]/50 p-4 rounded-lg border border-[var(--border-main)]">
          <Terminal size={16} className="mt-0.5 text-[var(--accent)]" />
          <p>The <code className="text-[var(--text-main)]">inputs</code> dict contains numpy arrays for image ports and raw values for others. Always return a dict mapping output IDs to data.</p>
        </div>
      </div>
    </section>

    {/* PHASE 2: COMPLEX */}
    <section className="mb-20">
      <div className="flex items-center gap-3 mb-6">
        <span className="text-[11px] font-bold bg-[var(--accent)]/10 text-[var(--accent)] px-2 py-1 rounded">PHASE 02</span>
        <h2 className="text-[22px] text-[var(--text-main)]">Scientific Complexity</h2>
      </div>
      <div className="grid lg:grid-cols-2 gap-6 mb-8">
        <div className="vn-card p-6">
          <h4 className="text-[14px] font-bold text-[var(--text-main)] mb-3 uppercase tracking-wider flex items-center gap-2">
            <Sparkles size={16} className="text-[var(--accent)]" /> Multi-Channel Logic
          </h4>
          <p className="text-[13px] text-[var(--text-dim)] leading-relaxed mb-4">
            For advanced signal processing (like FFT or custom filters), avoid artifacts by splitting BGR channels, 
            converting to <code className="text-[var(--accent)]">float64</code>, and stacking them back.
          </p>
          <div className="code-block text-[11px] leading-5">
            <span className="tok-comment"># The "Scientific" Pattern</span>{'\n'}
            channels = [img[:,:,i].astype(np.float64) <span className="tok-kw">for</span> i <span className="tok-kw">in</span> <span className="tok-num">range</span>(<span className="tok-num">3</span>)]{'\n'}
            processed = [apply_filter(ch) <span className="tok-kw">for</span> ch <span className="tok-kw">in</span> channels]{'\n'}
            out = np.stack(processed, axis=<span className="tok-num">2</span>).clip(<span className="tok-num">0</span>, <span className="tok-num">255</span>)
          </div>
        </div>
        <div className="vn-card p-6">
          <h4 className="text-[14px] font-bold text-[var(--text-main)] mb-3 uppercase tracking-wider flex items-center gap-2">
            <Eye size={16} className="text-[var(--accent)]" /> Visualization vs. Data
          </h4>
          <p className="text-[13px] text-[var(--text-dim)] leading-relaxed mb-4">
            Nodes can have dual outputs: a <code className="text-[var(--accent)]">uint8</code> image for UI preview and a 
            <code className="text-[var(--accent)]">data</code> port (orange) for high-precision downstream calculations.
          </p>
          <div className="code-block text-[11px] leading-5">
            <span className="tok-str">outputs</span>=[{'\n'}
            {'  '}{'{'}<span className="tok-str">"id"</span>:<span className="tok-str">"preview"</span>, <span className="tok-str">"color"</span>:<span className="tok-str">"image"</span>{'}'},{'\n'}
            {'  '}{'{'}<span className="tok-str">"id"</span>:<span className="tok-str">"raw_data"</span>, <span className="tok-str">"color"</span>:<span className="tok-str">"data"</span>{'}'}{'\n'}
            ]
          </div>
        </div>
      </div>
    </section>

    {/* PHASE 3: ROBUSTNESS */}
    <section className="mb-20">
      <div className="flex items-center gap-3 mb-6">
        <span className="text-[11px] font-bold bg-[var(--accent)] text-white px-2 py-1 rounded">PHASE 03</span>
        <h2 className="text-[22px] text-[var(--text-main)]">Production Robustness</h2>
      </div>
      <div className="vn-card p-8 border-l-4 border-[var(--accent)]">
        <h3 className="text-[18px] text-[var(--text-main)] mb-4">The "Smart Input" Pattern</h3>
        <p className="text-[14px] text-[var(--text-dim)] mb-6 leading-relaxed">
          Professional nodes shouldn't break when ports are renamed. Use this fallback logic to make your 
          nodes work even with partial or varied connections.
        </p>
        <div className="code-block text-[12px] leading-6 mb-6">
          <span className="tok-kw">def</span> <span className="tok-def">process</span>(<span className="tok-num">self</span>, inputs, params):{'\n'}
          {'  '}<span className="tok-comment"># 1. Try primary ID</span>{'\n'}
          {'  '}val = inputs.get(<span className="tok-str">'scalar'</span>){'\n'}{'\n'}
          {'  '}<span className="tok-kw">if</span> val <span className="tok-kw">is</span> <span className="tok-kw">None</span>:{'\n'}
          {'    '}<span className="tok-comment"># 2. Fallback: find ANY numeric data in inputs</span>{'\n'}
          {'    '}numeric = [v <span className="tok-kw">for</span> k, v <span className="tok-kw">in</span> inputs.items() <span className="tok-kw">if</span> <span className="tok-num">isinstance</span>(v, (<span className="tok-num">int</span>, <span className="tok-num">float</span>))]{'\n'}
          {'    '}val = numeric[<span className="tok-num">0</span>] <span className="tok-kw">if</span> numeric <span className="tok-kw">else</span> <span className="tok-kw">None</span>{'\n'}{'\n'}
          {'  '}<span className="tok-kw">if</span> val <span className="tok-kw">is</span> <span className="tok-kw">None</span>: <span className="tok-kw">return</span> {'{'}<span className="tok-str">'main'</span>: <span className="tok-kw">None</span>{'}'}
        </div>

        <div className="grid md:grid-cols-2 gap-8 mt-10 border-t border-[var(--border-main)] pt-8">
          <div>
            <h4 className="text-[13px] font-bold text-[var(--text-main)] mb-3 uppercase">Port Color Standards</h4>
            <div className="space-y-2">
              {[
                { t: 'image', c: '#a3d154', d: 'Standard 8-bit visual stream' },
                { t: 'data', c: '#fb923c', d: 'High-precision float/dict arrays' },
                { t: 'scalar', c: '#f87171', d: 'Numeric values (int/float)' },
                { t: 'boolean', c: '#facc15', d: 'True/False triggers' },
              ].map(p => (
                <div key={p.t} className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.c }} />
                  <span className="text-[11px] font-mono text-[var(--text-main)] w-16">{p.t}</span>
                  <span className="text-[11px] text-[var(--text-dim)]">{p.d}</span>
                </div>
              ))}
            </div>
          </div>
          <div>
            <h4 className="text-[13px] font-bold text-[var(--text-main)] mb-3 uppercase">The "Main" Rule</h4>
            <p className="text-[12px] text-[var(--text-dim)] leading-relaxed">
              Always name your primary output <code className="text-[var(--accent)] font-bold">main</code>. 
              The VisionNodes engine uses this ID to automatically populate the Global Graph, 
              the Inspector preview, and the telemetry dashboard.
            </p>
          </div>
        </div>
      </div>
    </section>

    <div className="flex justify-center mt-12">
       <button onClick={onBack} className="vn-button-primary px-8 py-3 rounded-full text-[14px]">
          I'm ready to build my first node
       </button>
    </div>
  </motion.div>
);

// ─── Tutorials Page ───────────────────────────────────────────────────────────

const TutorialsPage = () => {
  const [selected, setSelected] = useState<string | null>(null);
  const selectedTut = TUTORIALS.find(t => t.id === selected);

  return (
    <motion.div key="tutorials" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <section className="section-full" style={{ paddingTop: '4rem' }}>
        <div className="container-lg">
          {selectedTut ? (
            <TutorialDetail tut={selectedTut} onBack={() => setSelected(null)} />
          ) : (
            <>
              <div className="mb-10">
                <h1 className="text-[44px] md:text-[56px] text-[var(--text-main)] mb-4">Tutorials</h1>
                <p className="text-[17px] text-[var(--text-dim)] max-w-2xl">
                  Step-by-step guides based on real VisionNodes pipelines. From introductory examples
                  to production-grade processing chains.
                </p>
              </div>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {TUTORIALS.map(t => (
                  <TutorialCard key={t.id} tut={t} onClick={() => setSelected(t.id)} />
                ))}
              </div>
            </>
          )}
        </div>
      </section>
    </motion.div>
  );
};

export default TutorialsPage;
