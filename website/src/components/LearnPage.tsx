import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Download, BookOpen, X, ChevronLeft, ChevronRight, GraduationCap, Sparkles } from 'lucide-react';

const BASE = import.meta.env.BASE_URL;

// ─── Config ────────────────────────────────────────────────────────────────
// The book PDFs (~75 MB each) are too large for the gh-pages site, so they live
// on a dedicated `books` release that is never tied to an app version — the
// book evolves on its own cadence. Publishing a new edition is a single
// `gh release upload books <file> --clobber`; these URLs never move.
const BOOKS_TAG = 'books';
const BOOKS_BASE = `https://github.com/Nikos-Unilasalle/VisionNodes/releases/download/${BOOKS_TAG}`;
const BOOK_PDF_FR = `${BOOKS_BASE}/Le-monde-vu-par-les-nombres-FR.pdf`;
const BOOK_PDF_EN = `${BOOKS_BASE}/The-world-seen-through-numbers-EN.pdf`;

// ─── Content ───────────────────────────────────────────────────────────────

const BACK_COVER_FR = [
  `Une image, pour une machine, n'est qu'une grille de nombres. Là où votre œil reconnaît sans effort un visage, une route, une cellule au microscope, l'ordinateur ne dispose que de ce tableau. Lui faire dire quelque chose — ceci est un visage, ce contour passe ici, cet objet a bougé — voilà tout l'art de la vision par ordinateur, et c'est le voyage que ce livre vous propose.`,
  `Elle a ses gestes fondateurs, ceux qui ne vieillissent pas : décrire une forme, mesurer une ressemblance, lisser sans effacer, changer de regard pour qu'un problème se dénoue. Descripteurs, distances, filtres, transformées, morphologie, estimateurs — chacun est une façon de choisir ce qui compte dans une image, et d'accepter d'en perdre le reste. Et derrière chaque symbole, toujours, se cache une intuition qu'on peut dessiner du bout du doigt sur un coin de table.`,
  `C'est elle que ce livre poursuit, patiemment, formule après formule : non pas la recette, mais la raison de sa forme. Vous y trouverez le cheminement qui mène à chaque formule, l'exemple qu'on vérifie de tête, le piège tapi dans la pratique, le bout de code qui fait tourner la chose. Rien ici n'est sortilège, et rien ne vous est réservé : il n'est demandé ni d'être mathématicien, ni développeur, seulement d'avoir envie de comprendre pourquoi une formule prend la forme qu'elle a.`,
  `Car une intuition que la compréhension éclaire ne ressemble en rien à un réflexe appris par cœur : elle sait pourquoi elle a raison, et elle vous porte jusque dans les cas que vous n'aviez jamais rencontrés. Reste enfin ce qu'aucune table ne contient : le jugement, cette part de vous qui, devant une image réelle, choisira le bon cadre. Ce livre ne fera pas ce choix à votre place. Mais il arme la main qui le fera — et de tout ce qu'on apprend ici, c'est sans doute ce qui vous accompagnera le plus loin.`,
];

const BACK_COVER_EN = [
  `To a machine, an image is nothing but a grid of numbers. Where your eye effortlessly recognises a face, a road, a cell under the microscope, the computer has only that array of values. Making it say something — this is a face, this edge runs here, this object has moved — is the whole art of computer vision, and it is the journey this book invites you on.`,
  `It has its founding gestures, the ones that never age: describing a shape, measuring a resemblance, smoothing without erasing, shifting your point of view until a problem unravels. Descriptors, distances, filters, transforms, morphology, estimators — each is a way of choosing what matters in an image, and accepting to lose the rest. And behind every symbol, always, hides an intuition you could sketch with a fingertip on the corner of a table.`,
  `It is that intuition this book pursues, patiently, formula after formula: not the recipe, but the reason for its shape. You will find the path that leads to each formula, the example you can check in your head, the trap lurking in practice, the snippet of code that makes the thing run. Nothing here is sorcery, and nothing is reserved for an elite: you need be neither a mathematician nor a developer, only curious to understand why a formula takes the form it does.`,
  `For an intuition lit by understanding is nothing like a reflex learned by heart: it knows why it is right, and it carries you all the way into cases you had never met before. There remains, finally, what no table can contain: judgement — that part of you which, faced with a real image, will choose the right frame. This book will not make that choice for you. But it arms the hand that will — and of everything you learn here, that is probably what will stay with you the longest.`,
];

const HIGHLIGHTS = [
  { icon: <BookOpen size={20} />, title: '17 chapters', text: 'From shape descriptors and image moments to optical flow, deep learning and robust statistics.' },
  { icon: <GraduationCap size={20} />, title: 'Intuition first', text: 'Every formula is built up from the why, with a worked example you can check by hand.' },
  { icon: <Sparkles size={20} />, title: 'Built with VisionNodes', text: 'Concepts are illustrated as visual node pipelines you can reproduce live in the Studio.' },
];

const SAMPLE_PAGES_FR = [1, 2, 3, 4, 5, 6].map(n => `${BASE}book/page${n}.jpg`);
const SAMPLE_PAGES_EN = [1, 2, 3, 4, 5, 6].map(n => `${BASE}book/page${n}en.jpg`);

// ─── Lightbox ──────────────────────────────────────────────────────────────

interface LightboxProps {
  pages: string[];
  index: number;
  onClose: () => void;
  onNav: (next: number) => void;
}

const Lightbox = ({ pages, index, onClose, onNav }: LightboxProps) => (
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    onClick={onClose}
    className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-black/80 backdrop-blur-sm"
  >
    <button
      onClick={(e) => { e.stopPropagation(); onNav((index - 1 + pages.length) % pages.length); }}
      className="absolute left-4 md:left-8 text-white/70 hover:text-white p-2"
      aria-label="Previous page"
    >
      <ChevronLeft size={32} />
    </button>

    <motion.img
      key={index}
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      src={pages[index]}
      alt={`Sample page ${index + 1}`}
      onClick={(e) => e.stopPropagation()}
      className="max-h-[88vh] max-w-[90vw] rounded-lg shadow-2xl object-contain"
    />

    <button
      onClick={(e) => { e.stopPropagation(); onNav((index + 1) % pages.length); }}
      className="absolute right-4 md:right-8 text-white/70 hover:text-white p-2"
      aria-label="Next page"
    >
      <ChevronRight size={32} />
    </button>

    <button
      onClick={onClose}
      className="absolute top-5 right-5 text-white/70 hover:text-white p-2"
      aria-label="Close"
    >
      <X size={26} />
    </button>
  </motion.div>
);

// ─── Page ──────────────────────────────────────────────────────────────────

const LearnPage = () => {
  const [lang, setLang] = useState<'fr' | 'en'>('fr');
  const [lightbox, setLightbox] = useState<number | null>(null);

  const coverSrc = lang === 'fr' ? `${BASE}book/cover_fr.jpg` : `${BASE}book/cover_en.jpg`;
  const backCover = lang === 'fr' ? BACK_COVER_FR : BACK_COVER_EN;
  const samplePages = lang === 'fr' ? SAMPLE_PAGES_FR : SAMPLE_PAGES_EN;

  return (
    <motion.div key="learn" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      {/* ── Hero ── */}
      <section className="section-full section-alt" style={{ paddingTop: '4rem', paddingBottom: '3.5rem' }}>
        <div className="container-lg">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Cover */}
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="flex justify-center"
            >
              <img
                src={coverSrc}
                alt="Le monde vu par les nombres — book cover"
                className="w-full max-w-[360px] rounded-xl shadow-2xl"
                style={{ boxShadow: '0 30px 60px -20px rgba(0,0,0,0.45)' }}
              />
            </motion.div>

            {/* Text */}
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
            >
              <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent)]/10 border border-[var(--accent)]/20 text-[var(--accent)] text-[11px] font-bold uppercase tracking-widest mb-5">
                <BookOpen size={13} /> Learn Computer Vision
              </span>
              <h1 className="text-[40px] md:text-[52px] leading-tight text-[var(--text-main)] mb-3">
                Le monde vu par les nombres
              </h1>
              <p className="text-[18px] text-[var(--text-dim)] mb-6">
                A formulary of Computer Vision — the intuition behind every formula.
                <br />
                <span className="text-[14px] text-[var(--text-xdim)]">by Nicolas Priniotakis · Apex — UniLaSalle</span>
              </p>

              <p className="text-[15px] text-[var(--text-dim)] leading-relaxed mb-8">
                {backCover[0]}
              </p>

              {/* Language toggle */}
              <div className="inline-flex items-center gap-1 p-1 rounded-xl bg-[var(--border)] mb-6">
                {(['fr', 'en'] as const).map(l => (
                  <button
                    key={l}
                    onClick={() => setLang(l)}
                    className={`px-4 py-1.5 rounded-lg text-[13px] font-semibold transition-all ${
                      lang === l ? 'bg-[var(--accent)] text-white' : 'text-[var(--text-dim)] hover:text-[var(--text-main)]'
                    }`}
                  >
                    {l === 'fr' ? 'Français' : 'English'}
                  </button>
                ))}
              </div>

              {/* Downloads */}
              <div className="flex flex-wrap gap-4">
                <a href={BOOK_PDF_FR} target="_blank" rel="noreferrer" className="btn-primary text-[15px]">
                  <Download size={16} /> Télécharger (FR)
                </a>
                <a href={BOOK_PDF_EN} target="_blank" rel="noreferrer" className="btn-secondary text-[15px]">
                  <Download size={16} /> Download (EN)
                </a>
              </div>
              <p className="text-[12px] text-[var(--text-xdim)] mt-3">Free PDF · ~74 MB · 402 pages</p>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ── Highlights ── */}
      <section className="section-full">
        <div className="container-lg grid md:grid-cols-3 gap-6">
          {HIGHLIGHTS.map((h, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="vn-card p-7"
            >
              <div className="w-10 h-10 rounded-xl bg-[var(--accent)]/10 flex items-center justify-center text-[var(--accent)] mb-4">
                {h.icon}
              </div>
              <h3 className="text-[17px] text-[var(--text-main)] mb-2">{h.title}</h3>
              <p className="text-[14px] text-[var(--text-dim)] leading-relaxed">{h.text}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ── Mockup photos ── */}
      <section className="section-full section-alt">
        <div className="container-lg">
          <div className="grid sm:grid-cols-2 gap-6">
            {['mockup1.jpg', 'mockup2.jpg'].map((m, i) => (
              <motion.div
                key={m}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                className="rounded-2xl overflow-hidden shadow-xl"
              >
                <img src={`${BASE}book/${m}`} alt="Book in context" className="w-full h-full object-cover" />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Flip through ── */}
      <section className="section-full">
        <div className="container-lg">
          <div className="text-center mb-10">
            <h2 className="text-[32px] md:text-[40px] text-[var(--text-main)] mb-3">Flip through the book</h2>
            <p className="text-[15px] text-[var(--text-dim)] max-w-xl mx-auto">
              A few pages from inside — click any page to take a closer look.
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-5">
            {samplePages.map((src, i) => (
              <motion.button
                key={i}
                onClick={() => setLightbox(i)}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.06 }}
                className="group rounded-lg overflow-hidden border border-[var(--border)] bg-white shadow-sm hover:shadow-xl transition-all"
              >
                <img
                  src={src}
                  alt={`Sample page ${i + 1}`}
                  className="w-full object-contain transition-transform group-hover:scale-[1.03]"
                />
              </motion.button>
            ))}
          </div>
        </div>
      </section>

      {/* ── Full back cover text ── */}
      <section className="section-full section-alt">
        <div className="container-md">
          <div className="vn-card p-8 md:p-12">
            <p className="text-[11px] font-bold uppercase tracking-widest text-[var(--accent)] mb-5">
              {lang === 'fr' ? 'Quatrième de couverture' : 'From the back cover'}
            </p>
            <div className="space-y-4 text-[16px] text-[var(--text-dim)] leading-relaxed text-justify">
              {backCover.map((p, i) => <p key={i}>{p}</p>)}
            </div>
          </div>
        </div>
      </section>

      {/* ── Download CTA ── */}
      <section className="section-full">
        <div className="container-md text-center">
          <h2 className="text-[30px] md:text-[38px] text-[var(--text-main)] mb-3">Get your free copy</h2>
          <p className="text-[15px] text-[var(--text-dim)] max-w-lg mx-auto mb-8">
            The full book is available as a free PDF, in French and in English.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <a href={BOOK_PDF_FR} target="_blank" rel="noreferrer" className="btn-primary text-[15px]">
              <Download size={16} /> Version Française
            </a>
            <a href={BOOK_PDF_EN} target="_blank" rel="noreferrer" className="btn-secondary text-[15px]">
              <Download size={16} /> English Version
            </a>
          </div>
        </div>
      </section>

      {/* ── Lightbox ── */}
      <AnimatePresence>
        {lightbox !== null && (
          <Lightbox pages={samplePages} index={lightbox} onClose={() => setLightbox(null)} onNav={setLightbox} />
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default LearnPage;
