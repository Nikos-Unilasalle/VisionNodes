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
  <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="max-w-3xl pb-20">
    <button onClick={onBack} className="flex items-center gap-2 text-[13px] text-[var(--text-dim)] hover:text-[var(--text-main)] mb-8 transition-colors">
      <ArrowLeft size={14} /> Back to Tutorials
    </button>

    <div className="flex items-center gap-3 mb-4">
      <div className="w-12 h-12 rounded-2xl bg-[var(--accent)]/10 flex items-center justify-center text-[var(--accent)]">
        <Code2 size={24} strokeWidth={1.5} />
      </div>
      <div>
        <h1 className="text-[36px] text-[var(--text-main)] leading-none">Create Your Own Node</h1>
        <p className="text-[14px] text-[var(--accent)] font-medium mt-1">Python Plugin API — Version 2.0</p>
      </div>
    </div>

    <p className="text-[16px] text-[var(--text-dim)] mb-10 leading-relaxed">
      VisionNodes is designed for extreme extensibility. Any Python class can become a production-grade node by using our
      <code className="bg-[var(--bg-alt)] px-1.5 py-0.5 rounded text-[var(--accent)] text-[14px] mx-1">@vision_node</code> decorator.
      Drop a <code className="bg-[var(--bg-alt)] px-1.5 py-0.5 rounded text-[var(--accent)] text-[14px] mx-1">.py</code> file in 
      <code className="bg-[var(--bg-alt)] px-1.5 py-0.5 rounded text-[var(--accent)] text-[14px] mx-1">engine/plugins/</code> and the app hot-reloads instantly.
    </p>

    {/* Section 1: Standard Structure */}
    <div className="mb-12">
      <h3 className="text-[18px] text-[var(--text-main)] mb-4 flex items-center gap-2">
        <CheckCircle2 size={18} className="text-[var(--accent)]" /> 1. Standard Node Structure
      </h3>
      <div className="vn-card p-6">
        <p className="text-[14px] text-[var(--text-dim)] mb-4 leading-relaxed">
          The basic template for any node. The <code className="text-[var(--accent)]">process</code> method receives two dictionaries: 
          <code className="text-[var(--text-main)] ml-1">inputs</code> (connected data) and <code className="text-[var(--text-main)] ml-1">params</code> (user-defined settings).
        </p>
        <div className="code-block text-[12px] leading-6">
          <span className="tok-kw">from</span> registry <span className="tok-kw">import</span> vision_node, NodeProcessor{'\n'}
          <span className="tok-kw">import</span> cv2, numpy <span className="tok-kw">as</span> np{'\n'}{'\n'}
          <span className="tok-dec">@vision_node</span>({'\n'}
          {'  '}type_id=<span className="tok-str">"my_custom_node"</span>,{'\n'}
          {'  '}label=<span className="tok-str">"My Custom Node"</span>,{'\n'}
          {'  '}icon=<span className="tok-str">"Zap"</span>,{' '}
          <span className="tok-comment"># Lucide-react icon name</span>{'\n'}
          {'  '}category=[<span className="tok-str">"util"</span>],{'\n'}
          {'  '}inputs=[{'{'}<span className="tok-str">"id"</span>:<span className="tok-str">"image"</span>, <span className="tok-str">"color"</span>:<span className="tok-str">"image"</span>{'}'}],{'\n'}
          {'  '}outputs=[{'{'}<span className="tok-str">"id"</span>:<span className="tok-str">"main"</span>, <span className="tok-str">"color"</span>:<span className="tok-str">"image"</span>{'}'}],{'\n'}
          {'  '}params=[{'{'}<span className="tok-str">"id"</span>:<span className="tok-str">"gain"</span>, <span className="tok-str">"type"</span>:<span className="tok-str">"float"</span>, <span className="tok-str">"default"</span>:<span className="tok-num">1.0</span>{'}'}]{'\n'}
          ){'\n'}
          <span className="tok-kw">class</span> <span className="tok-def">MyNode</span>(NodeProcessor):{'\n'}
          {'  '}<span className="tok-kw">def</span> <span className="tok-def">process</span>(<span className="tok-num">self</span>, inputs, params):{'\n'}
          {'    '}img = inputs.get(<span className="tok-str">'image'</span>){'\n'}
          {'    '}<span className="tok-kw">if</span> img <span className="tok-kw">is</span> <span className="tok-kw">None</span>: <span className="tok-kw">return</span> {'{'}<span className="tok-str">'main'</span>: <span className="tok-kw">None</span>{'}'}{'\n'}
          {'    '}gain = <span className="tok-num">float</span>(params.get(<span className="tok-str">'gain'</span>, <span className="tok-num">1.0</span>)){'\n'}
          {'    '}<span className="tok-kw">return</span> {'{'}<span className="tok-str">'main'</span>: (img * gain).astype(np.uint8){'}'}
        </div>
      </div>
    </div>

    {/* Section 2: Scientific Best Practices */}
    <div className="mb-12">
      <h3 className="text-[18px] text-[var(--text-main)] mb-4 flex items-center gap-2">
        <Sparkles size={18} className="text-[var(--accent)]" /> 2. Scientific Best Practices
      </h3>
      <div className="grid md:grid-cols-2 gap-5">
        <div className="vn-card p-5">
          <h4 className="text-[14px] font-bold text-[var(--text-main)] mb-2 uppercase tracking-wide">Multi-Channel Precision</h4>
          <p className="text-[13px] text-[var(--text-dim)] leading-relaxed mb-4">
            Process BGR channels independently to avoid artifacts. Convert to <code className="text-[var(--accent)]">float64</code> for complex math (FFT, Filtering) before clipping back to uint8.
          </p>
          <div className="code-block text-[11px] leading-5">
            <span className="tok-comment"># Process channels separately</span>{'\n'}
            channels = [img[:,:,i] <span className="tok-kw">for</span> i <span className="tok-kw">in</span> <span className="tok-num">range</span>(<span className="tok-num">3</span>)]{'\n'}
            results = [my_func(ch) <span className="tok-kw">for</span> ch <span className="tok-kw">in</span> channels]{'\n'}
            final = np.stack(results, axis=<span className="tok-num">2</span>)
          </div>
        </div>
        <div className="vn-card p-5">
          <h4 className="text-[14px] font-bold text-[var(--text-main)] mb-2 uppercase tracking-wide">High-Precision Data Ports</h4>
          <p className="text-[13px] text-[var(--text-dim)] leading-relaxed mb-4">
            Use the <code className="text-[var(--accent)]">data</code> port type (orange) to pass raw numpy arrays or complex dictionaries between nodes without precision loss from image normalization.
          </p>
          <div className="code-block text-[11px] leading-5">
            <span className="tok-comment"># Return raw data for downstream</span>{'\n'}
            <span className="tok-kw">return</span> {'{'}{'\n'}
            {'  '}<span className="tok-str">'main'</span>: vis_img,{' '}
            <span className="tok-comment"># UI Preview</span>{'\n'}
            {'  '}<span className="tok-str">'raw_data'</span>: {'{'}
            <span className="tok-str">'mag'</span>: mag_float
            {'}'}{'\n'}
            {'}'}
          </div>
        </div>
      </div>
    </div>

    {/* Section 3: Input Fallbacks */}
    <div className="mb-12">
      <h3 className="text-[18px] text-[var(--text-main)] mb-4 flex items-center gap-2">
        <Zap size={18} className="text-[var(--accent)]" /> 3. Robust Input Fallbacks
      </h3>
      <div className="vn-card p-6">
        <p className="text-[14px] text-[var(--text-dim)] mb-4 leading-relaxed">
          Ensure your node stays functional even if graph connections change. If your primary input ID isn't found, try to auto-detect any compatible data in the <code className="text-[var(--accent)]">inputs</code> dict.
        </p>
        <div className="code-block text-[12px] leading-6">
          <span className="tok-kw">def</span> <span className="tok-def">process</span>(<span className="tok-num">self</span>, inputs, params):{'\n'}
          {'  '}data = inputs.get(<span className="tok-str">'scalar'</span>){'\n'}
          {'  '}<span className="tok-kw">if</span> data <span className="tok-kw">is</span> <span className="tok-kw">None</span>:{'\n'}
          {'    '}<span className="tok-comment"># Fallback: grab any numeric input available</span>{'\n'}
          {'    '}numeric = [v <span className="tok-kw">for</span> k, v <span className="tok-kw">in</span> inputs.items() <span className="tok-kw">if</span> <span className="tok-num">isinstance</span>(v, (<span className="tok-num">int</span>, <span className="tok-num">float</span>))]{'\n'}
          {'    '}data = numeric[<span className="tok-num">0</span>] <span className="tok-kw">if</span> numeric <span className="tok-kw">else</span> <span className="tok-kw">None</span>
        </div>
      </div>
    </div>

    <div className="vn-card-flat p-6 bg-[var(--accent)]/[0.04] border-[var(--accent)]/20 flex items-start gap-4">
      <CheckCircle2 size={18} className="text-[var(--accent)] shrink-0 mt-0.5" strokeWidth={1.5} />
      <div className="text-[13px] text-[var(--text-dim)] leading-relaxed">
        <p className="font-bold text-[var(--text-main)] mb-1">Standard Output Convention</p>
        Always name your primary data output <code className="text-[var(--accent)] font-bold">main</code>. This ensures automatic compatibility with the Inspector, the Global Graph, and the export utilities.
      </div>
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
