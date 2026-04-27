import React from 'react';
import { motion } from 'framer-motion';
import { Shield, Eye, Lock, Server } from 'lucide-react';

const PrivacyPage = () => (
  <motion.div key="privacy" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
    <section className="section-full section-alt" style={{ paddingTop: '6rem', paddingBottom: '3rem' }}>
      <div className="container-md text-center">
        <h1 className="text-[44px] md:text-[56px] text-[var(--text-main)] mb-4">Privacy Policy</h1>
        <p className="text-[17px] text-[var(--text-dim)]">
          Last Updated: April 27, 2026
        </p>
      </div>
    </section>

    <section className="section-full">
      <div className="container-md">
        <div className="vn-card p-8 md:p-12 space-y-10">
          <div>
            <div className="flex items-center gap-3 mb-4 text-[var(--accent)]">
              <Shield size={24} />
              <h2 className="text-[24px] text-[var(--text-main)]">Commitment to Privacy</h2>
            </div>
            <p className="text-[15px] text-[var(--text-dim)] leading-relaxed">
              VisionNodes Studio is built with a "Privacy by Design" philosophy. As a tool designed for 
              scientific research and industrial prototyping, we understand the sensitivity of your data 
              and algorithms.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 gap-8">
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-[var(--text-main)] font-semibold">
                <Eye size={18} className="text-[var(--accent)]" />
                No Data Collection
              </div>
              <p className="text-[14px] text-[var(--text-dim)] leading-relaxed">
                The VisionNodes Studio application does not collect, store, or transmit your images, 
                videos, or processing pipelines to any external servers. Everything stays on your machine.
              </p>
            </div>
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-[var(--text-main)] font-semibold">
                <Lock size={18} className="text-[var(--accent)]" />
                Local Execution
              </div>
              <p className="text-[14px] text-[var(--text-dim)] leading-relaxed">
                All computer vision and AI models run locally on your hardware. No cloud processing 
                is required or used by default.
              </p>
            </div>
          </div>

          <div className="border-t border-[var(--border)] pt-10">
            <h3 className="text-[18px] text-[var(--text-main)] mb-4">Website & Analytics</h3>
            <p className="text-[14px] text-[var(--text-dim)] leading-relaxed mb-4">
              This website is hosted via GitHub Pages. We do not use third-party tracking cookies or 
              analytics scripts (like Google Analytics). We value a clean, anonymous browsing experience.
            </p>
            <div className="bg-[var(--bg-alt)] p-4 rounded-xl flex items-start gap-3">
              <Server size={18} className="text-[var(--text-xdim)] mt-1" />
              <p className="text-[12px] text-[var(--text-dim)]">
                Standard server logs may be kept by the hosting provider (GitHub) for security and 
                performance monitoring, which may include your IP address and browser type.
              </p>
            </div>
          </div>

          <div className="border-t border-[var(--border)] pt-10">
            <h3 className="text-[18px] text-[var(--text-main)] mb-4">Contact</h3>
            <p className="text-[14px] text-[var(--text-dim)] leading-relaxed">
              If you have questions about privacy or security, please contact the Apex team at 
              UniLaSalle Polytechnic Institute or open a discussion on our GitHub repository.
            </p>
          </div>
        </div>
      </div>
    </section>
  </motion.div>
);

export default PrivacyPage;
