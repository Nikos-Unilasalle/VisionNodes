import React from 'react';
import logo from '../../assets/logo.svg';

interface AboutModalProps {
  showAbout: boolean;
  setShowAbout: (v: boolean) => void;
}

const AboutModal: React.FC<AboutModalProps> = ({ showAbout, setShowAbout }) => {
  if (!showAbout) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[9999] flex items-center justify-center" onClick={() => setShowAbout(false)}>
      <div className="bg-[#2c333f] border border-[#4f5b6b] rounded-2xl shadow-2xl w-[340px] overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="bg-[#3d4452] px-5 py-3 flex items-center justify-between border-b border-[#4f5b6b]">
          <div className="flex items-center gap-3">
            <img src={logo} className="h-5 w-5" alt="Logo" />
            <span className="text-[11px] font-black tracking-[0.2em] text-white uppercase">VNStudio</span>
          </div>
          <button onClick={() => setShowAbout(false)} className="text-gray-400 hover:text-white transition-colors">
            ×
          </button>
        </div>
        <div className="p-6 flex flex-col items-center gap-3">
          <div className="text-[18px] font-black text-white tracking-wider">VNStudio</div>
          <div className="text-[10px] font-bold text-accent uppercase tracking-widest">Alpha 0.8</div>
          <div className="text-[11px] text-gray-400 font-medium">Apex — UniLaSalle</div>
          <div className="h-px w-16 bg-[#4f5b6b] my-2" />
          <a
            href="https://nikos-unilasalle.github.io/VisionNodes"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] text-accent hover:text-accent/80 underline underline-offset-2 transition-colors"
          >
            https://nikos-unilasalle.github.io/VisionNodes
          </a>
        </div>
      </div>
    </div>
  );
};

export default AboutModal;
