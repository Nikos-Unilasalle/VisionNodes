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
  <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="max-w-3xl">
    <button onClick={onBack} className="flex items-center gap-2 text-[13px] text-[var(--text-dim)] hover:text-[var(--text-main)] mb-8 transition-colors">
      <ArrowLeft size={14} /> Back to Tutorials
    </button>

    <h1 className="text-[36px] text-[var(--text-main)] mb-3">Create Your Own Node</h1>
    <p className="text-[16px] text-[var(--text-dim)] mb-10 leading-relaxed">
      VisionNodes nodes are standard Python classes decorated with <code className="bg-[var(--bg-alt)] px-1.5 py-0.5 rounded text-[var(--accent)] text-[14px]">@vision_node</code>.
      Drop a new <code className="bg-[var(--bg-alt)] px-1.5 py-0.5 rounded text-[var(--accent)] text-[14px]">.py</code> file in the{' '}
      <code className="bg-[var(--bg-alt)] px-1.5 py-0.5 rounded text-[var(--accent)] text-[14px]">engine/plugins/</code> directory — the app hot-reloads without a restart.
    </p>

    {/* Method A */}
    <div className="mb-8">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-9 h-9 rounded-xl bg-[var(--accent)]/10 flex items-center justify-center text-[var(--accent)]">
          <Sparkles size={18} strokeWidth={1.5} />
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-[var(--accent)]">Method A — AI-Assisted</p>
          <h3 className="text-[18px] text-[var(--text-main)]">Generate with an AI agent</h3>
        </div>
      </div>
      <div className="vn-card p-6 space-y-3 text-[14px] text-[var(--text-dim)] leading-relaxed">
        <p>1. Open your AI assistant (Claude, Gemini, GPT…) and paste this prompt:</p>
        <div className="code-block text-[12px] border border-[var(--accent)]/20">
          <span className="tok-comment"># Prompt template</span>{'\n'}
          Create a VisionNodes Studio node that [describe what it does].{'\n'}
          It must use the @vision_node decorator with icon, category, inputs, outputs and params.{'\n'}
          Follow the plugin API from engine/plugins/object_detection_yolo.py as a reference.
        </div>
        <p>2. Save the generated file to <code className="text-[var(--accent)]">engine/plugins/my_node.py</code>.</p>
        <p>3. The app detects the new file automatically. The node appears in the menu.</p>
      </div>
    </div>

    {/* Method B */}
    <div className="mb-8">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-9 h-9 rounded-xl bg-[var(--bg-alt)] flex items-center justify-center text-[var(--text-dim)]">
          <Terminal size={18} strokeWidth={1.5} />
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-[var(--text-xdim)]">Method B — Manual</p>
          <h3 className="text-[18px] text-[var(--text-main)]">Write it from scratch</h3>
        </div>
      </div>
      <div className="vn-card p-6 space-y-5">

        <div>
          <p className="text-[13px] font-semibold text-[var(--text-main)] mb-2">1. File structure</p>
          <div className="code-block text-[12px]">
            <span className="tok-comment"># engine/plugins/my_node.py</span>{'\n'}
            <span className="tok-kw">from</span> engine.node_base <span className="tok-kw">import</span> vision_node, NodeBase{'\n'}
            <span className="tok-kw">import</span> numpy <span className="tok-kw">as</span> np
          </div>
        </div>

        <div>
          <p className="text-[13px] font-semibold text-[var(--text-main)] mb-2">2. Decorator definition</p>
          <div className="code-block text-[12px]">
            <span className="tok-dec">@vision_node</span>({'\n'}
            {'  '}<span className="tok-str">label</span>=<span className="tok-str">"My Node"</span>,{'\n'}
            {'  '}<span className="tok-str">icon</span>=<span className="tok-str">"Zap"</span>,{' '}
            <span className="tok-comment"># Any Lucide icon name</span>{'\n'}
            {'  '}<span className="tok-str">category</span>=<span className="tok-str">"util"</span>,{'\n'}
            {'  '}<span className="tok-str">inputs</span>=[{'{'}
            <span className="tok-str">"id"</span>:<span className="tok-str">"main"</span>,
            <span className="tok-str">"color"</span>:<span className="tok-str">"image"</span>
            {'}'}],{'\n'}
            {'  '}<span className="tok-str">outputs</span>=[{'{'}
            <span className="tok-str">"id"</span>:<span className="tok-str">"result"</span>,
            <span className="tok-str">"color"</span>:<span className="tok-str">"image"</span>
            {'}'}],{'\n'}
            {'  '}<span className="tok-str">params</span>=[{'{'}
            <span className="tok-str">"id"</span>:<span className="tok-str">"strength"</span>,
            <span className="tok-str">"label"</span>:<span className="tok-str">"Strength"</span>,
            <span className="tok-str">"type"</span>:<span className="tok-str">"float"</span>,
            <span className="tok-str">"default"</span>:<span className="tok-num">0.5</span>
            {'}'}]{'\n'}
            ){'\n'}
            <span className="tok-kw">class</span> <span className="tok-def">MyNode</span>(NodeBase):{'\n'}
            {'  '}<span className="tok-kw">def</span> <span className="tok-def">process</span>(<span className="tok-num">self</span>, main, strength):{'\n'}
            {'    '}<span className="tok-kw">return</span> {'{'}
            <span className="tok-str">"result"</span>: main * strength
            {'}'}
          </div>
        </div>

        <div>
          <p className="text-[13px] font-semibold text-[var(--text-main)] mb-2">3. Port color types</p>
          <div className="flex flex-wrap gap-2">
            {[['image','#a3d154'],['scalar','#f87171'],['vector','#60a5fa'],['boolean','#facc15'],['string','#c084fc'],['dict','#fb923c'],['any','#9ca3af']].map(([t,c]) => (
              <span key={t} className="flex items-center gap-1.5 text-[12px] font-mono px-2 py-1 rounded"
                    style={{ backgroundColor: c + '22', color: c }}>
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: c }} />{t}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>

    <div className="vn-card-flat p-5 bg-[var(--accent)]/[0.04] border-[var(--accent)]/20 flex items-start gap-4">
      <CheckCircle2 size={18} className="text-[var(--accent)] shrink-0 mt-0.5" strokeWidth={1.5} />
      <p className="text-[13px] text-[var(--text-dim)] leading-relaxed">
        Once your node works, share it with the community via the{' '}
        <a href="#" className="text-[var(--accent)] font-semibold hover:underline">Share page</a>.
        Submissions are reviewed as GitHub Issues and can be merged into the core library.
      </p>
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
