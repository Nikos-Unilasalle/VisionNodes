import React from 'react';
import { motion } from 'framer-motion';
import { Microscope, Zap, Users, GraduationCap, Code2, Globe } from 'lucide-react';

const AboutPage = () => (
  <motion.div key="about" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
    {/* Hero Section */}
    <section className="section-full section-alt" style={{ paddingTop: '6rem', paddingBottom: '4rem' }}>
      <div className="container-md text-center">
        <p className="text-[11px] font-bold uppercase tracking-widest text-[var(--accent)] mb-4">Scientific Background</p>
        <h1 className="text-[44px] md:text-[56px] text-[var(--text-main)] mb-6 leading-tight">
          Hypothesis-to-Discovery Loop <br className="hidden md:block" /> Made Faster and Easier
        </h1>
        <p className="text-[18px] text-[var(--text-dim)] leading-relaxed italic">
          "Bridging the gap between algorithmic complexity and real-time scientific intuition."
        </p>
      </div>
    </section>

    {/* Article Content */}
    <section className="section-full">
      <div className="container-md">
        <div className="prose-like space-y-12">
          
          {/* Introduction */}
          <div className="space-y-4">
            <h2 className="text-[28px] text-[var(--text-main)]">Introduction</h2>
            <p className="text-[16px] text-[var(--text-dim)] leading-relaxed text-justify">
              In the contemporary landscape of computer vision (CV) and artificial intelligence (AI), the transition from theoretical model to functional pipeline often encounters significant friction. VisionNodes Studio emerges as a response to this challenge, developed at the <strong className="text-[var(--text-main)]">UniLaSalle Polytechnic Institute</strong> by the <strong className="text-[var(--text-main)]">Apex research team</strong>. It is designed not as a replacement for traditional coding, but as a high-level orchestration layer that empowers researchers to manifest complex algorithms through a deterministic, node-based visual paradigm.
            </p>
          </div>

          {/* Core Mechanism */}
          <div className="vn-card-flat p-10 bg-[var(--bg-alt)]/30">
            <div className="flex items-center gap-3 mb-6">
              <Code2 className="text-[var(--accent)]" size={28} />
              <h2 className="text-[26px] text-[var(--text-main)]">The Mechanism: Stateful Graph Execution</h2>
            </div>
            <p className="text-[15px] text-[var(--text-dim)] leading-relaxed mb-6 text-justify">
              At its core, VisionNodes Studio utilizes a <strong className="text-[var(--text-main)]">Directed Acyclic Graph (DAG)</strong> execution engine. Each "node" represents an atomic computational unit—ranging from fundamental morphological operations (OpenCV-based) to state-of-the-art deep learning inference (PyTorch, ONNX). Unlike traditional scripts where state management is often implicit and error-prone, VisionNodes makes the flow of data explicit. 
            </p>
            <p className="text-[15px] text-[var(--text-dim)] leading-relaxed text-justify">
              The engine operates on a real-time reactive model: any parameter modification triggers a targeted re-propagation through the affected branches of the graph. This "Hot-Swapping" of logic and data ensures that the researcher remains in a state of continuous observation, allowing for the immediate visual validation of hyperspectral thresholds, spatial filters, or detection confidence scores.
            </p>
          </div>

          {/* Advantages for Researchers */}
          <div className="space-y-6">
            <div className="flex items-center gap-3 mb-2">
              <Microscope className="text-[var(--accent)]" size={28} />
              <h2 className="text-[28px] text-[var(--text-main)]">Research Advantages</h2>
            </div>
            <div className="grid md:grid-cols-2 gap-8">
              <div className="space-y-3">
                <h4 className="text-[17px] font-bold text-[var(--text-main)]">Rapid Prototyping & Iteration</h4>
                <p className="text-[14px] text-[var(--text-dim)] leading-relaxed">
                  Traditional development cycles require lengthy compile-run-debug loops. VisionNodes collapses this cycle into milliseconds. Researchers can test competitive hypotheses across different filter sets or neural architectures by simply swapping a node, preserving the surrounding pipeline integrity.
                </p>
              </div>
              <div className="space-y-3">
                <h4 className="text-[17px] font-bold text-[var(--text-main)]">Deterministic Reproducibility</h4>
                <p className="text-[14px] text-[var(--text-dim)] leading-relaxed">
                  By utilizing a structured <code className="text-xs">.vn</code> file format that encapsulates both architecture and parameters, experiments become inherently shareable and reproducible. This standardization is critical for the peer-review process and cross-laboratory collaboration.
                </p>
              </div>
            </div>
          </div>

          {/* Multi-modal Use Cases */}
          <div className="space-y-8">
            <h3 className="text-[22px] text-[var(--text-main)] border-l-4 border-[var(--accent)] pl-4">Beyond the Laboratory: Multi-modal Applications</h3>
            
            <div className="grid gap-6">
              <div className="flex gap-5 p-6 vn-card">
                <Users className="shrink-0 text-[var(--accent)]" />
                <div>
                  <h4 className="font-bold mb-1">International Conferences & Workshops</h4>
                  <p className="text-[14px] text-[var(--text-dim)]">Instead of static slides, VisionNodes allows presenters to run live, interactive demonstrations. Audience members can suggest parameter changes, and the results are visualized instantly, transforming a passive talk into a collaborative colloquium.</p>
                </div>
              </div>
              <div className="flex gap-5 p-6 vn-card">
                <GraduationCap className="shrink-0 text-[var(--accent)]" />
                <div>
                  <h4 className="font-bold mb-1">Education and Teaching</h4>
                  <p className="text-[14px] text-[var(--text-dim)]">For students of Computer Vision, the abstraction of boilerplate code allows them to focus on the mathematical and logic-driven heart of the science. Visualizing how a Watershed algorithm behaves on touching cells or how Optical Flow responds to velocity changes provides an unmatched pedagogical intuition.</p>
                </div>
              </div>
            </div>
          </div>

          {/* Open Science & Community */}
          <div className="pt-10 border-t border-[var(--border)]">
            <div className="flex items-center gap-3 mb-6">
              <Globe className="text-[var(--accent)]" size={28} />
              <h2 className="text-[26px] text-[var(--text-main)]">Open Science & The Participatory Paradigm</h2>
            </div>
            <p className="text-[16px] text-[var(--text-dim)] leading-relaxed mb-6 text-justify">
              In an era of increasingly "black-box" AI, <strong className="text-[var(--text-main)]">Open Source is not a choice, but a scientific necessity</strong>. VisionNodes Studio is released under the MIT license to ensure transparency and trust. Every node's implementation is open for inspection, ensuring that research results are not artifacts of hidden implementation details but solid, verifiable facts.
            </p>
            <div className="bg-[var(--accent)]/5 border border-[var(--accent)]/10 p-8 rounded-2xl">
              <p className="text-[15px] text-[var(--text-main)] font-semibold mb-3 flex items-center gap-2">
                <Zap size={18} /> A Community-Driven Core
              </p>
              <p className="text-[14px] text-[var(--text-dim)] leading-relaxed">
                The software is designed to grow through community contributions. By providing a streamlined "Plugin API", we invite the global scientific community to contribute their unique nodes—be it for specialized satellite imagery analysis, agricultural phenotyping, or medical diagnostic tools. This participatory model ensures that VisionNodes Studio remains at the bleeding edge of multidisciplinary research.
              </p>
            </div>
          </div>

          {/* Conclusion */}
          <div className="pt-8 text-center max-w-xl mx-auto">
            <p className="text-[14px] text-[var(--text-xdim)] uppercase tracking-widest font-bold mb-4">Conclusion</p>
            <p className="text-[17px] text-[var(--text-dim)] leading-relaxed italic">
              Ultimately, VisionNodes Studio is a testament to the power of visual abstraction in high-stakes research. It enables a dialogue between the researcher and the data, where the software acts not as a barrier, but as a transparent medium for discovery.
            </p>
          </div>

        </div>
      </div>
    </section>
  </motion.div>
);

export default AboutPage;
