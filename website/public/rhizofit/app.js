/* RhizoFit — UI. The analysis itself runs in worker.js (Pyodide). */
(() => {
  'use strict';

  const STAGES = ['Segmenting the section', 'Measuring tissue boundaries', 'Counting cells', 'Drawing figures'];
  const SAMPLES = {
    micrograph: { url: 'samples/micrograph.jpg', name: 'micrograph.jpg', pixelSize: 0.5 },
    drawing: { url: 'samples/expert_drawing.png', name: 'expert_drawing.png', pixelSize: 0.321 },
  };
  const ZONE_SWATCH = {
    'Pith': '#b39ddb', 'Vascular cylinder': '#ffd54f', 'Endodermis': '#ba68c8',
    'Inner cortex': '#81c784', 'Outer cortex': '#ffb74d', 'Rhizodermis': '#64b5f6',
  };
  const MAX_UPLOAD_BYTES = 40 * 1024 * 1024;
  const MAX_ZOOM = 16;

  const $ = (sel) => document.querySelector(sel);
  const el = (tag, props = {}, children = []) => {
    const node = Object.assign(document.createElement(tag), props);
    children.forEach((c) => node.append(c));
    return node;
  };

  const state = {
    ready: false,
    busy: false,
    file: null,           // { bytes: ArrayBuffer, name: string }
    stem: 'root',
    result: null,
    gallery: [],          // [{title, caption, url, filename}] for the lightbox
    objectUrls: [],
  };

  /* ------------------------------------------------------------------ worker */
  const worker = new Worker('worker.js', { type: 'module' });
  worker.onmessage = ({ data }) => {
    switch (data.type) {
      case 'boot': return setStatus(data.message, data.fraction);
      case 'ready':
        state.ready = true;
        setStatus('Ready. Choose an image and press Analyze.', 1);
        renderSteps(-1);
        return updateRunButton();
      case 'progress': return onProgress(data.stage, data.fraction);
      case 'result': return onResult(data.result);
      case 'error': return onError(data.message);
      case 'fatal': return setStatus(`The Python runtime could not start: ${data.message}`, 0, true);
      default: return undefined;
    }
  };
  worker.onerror = (e) => setStatus(`Worker error: ${e.message}`, 0, true);

  /* ------------------------------------------------------------------ status */
  function setStatus(message, fraction, isError = false) {
    const text = $('#status-text');
    text.textContent = message;
    text.classList.toggle('error', isError);
    if (fraction !== undefined) $('#bar-fill').style.width = `${Math.round(100 * fraction)}%`;
  }

  function renderSteps(activeIndex) {
    const list = $('#steps');
    list.replaceChildren(...STAGES.map((s, i) => el('li', {
      textContent: s,
      className: i < activeIndex ? 'done' : (i === activeIndex ? 'active' : ''),
    })));
  }

  function onProgress(stage, fraction) {
    const i = STAGES.indexOf(stage);
    renderSteps(fraction >= 1 && i === STAGES.length - 1 ? STAGES.length : i);
    const overall = (Math.max(i, 0) + Math.min(fraction, 1)) / STAGES.length;
    setStatus(`${stage}…`, overall);
  }

  function updateRunButton() {
    $('#run').disabled = !(state.ready && state.file && !state.busy);
    $('#run').textContent = state.busy ? 'Analyzing…' : 'Analyze';
  }

  /* ------------------------------------------------------------------ input */
  async function setFile(blob, name, pixelSize) {
    if (!blob.type.startsWith('image/') && !/\.(tiff?|webp|png|jpe?g|bmp)$/i.test(name)) {
      setStatus('This file is not an image.', undefined, true);
      return;
    }
    if (blob.size > MAX_UPLOAD_BYTES) {
      setStatus('This image is larger than 40 MB; please downscale it.', undefined, true);
      return;
    }
    state.file = { bytes: await blob.arrayBuffer(), name };
    state.stem = name.replace(/\.[^.]+$/, '').replace(/[^\w-]+/g, '_') || 'root';
    const thumb = $('#thumb');
    if (thumb.src) URL.revokeObjectURL(thumb.src);
    thumb.src = URL.createObjectURL(blob);
    thumb.hidden = false;
    $('#dropzone').classList.add('has-image');
    $('#dropzone-text strong').textContent = name;
    if (pixelSize !== undefined) $('#pixel-size').value = pixelSize;
    if (state.ready) setStatus('Ready. Press Analyze.', 1);
    updateRunButton();
  }

  const dz = $('#dropzone');
  $('#file-input').addEventListener('change', (e) => {
    const f = e.target.files[0];
    if (f) setFile(f, f.name);
  });
  ['dragenter', 'dragover'].forEach((t) => dz.addEventListener(t, (e) => { e.preventDefault(); dz.classList.add('drag'); }));
  ['dragleave', 'drop'].forEach((t) => dz.addEventListener(t, (e) => { e.preventDefault(); dz.classList.remove('drag'); }));
  dz.addEventListener('drop', (e) => {
    const f = e.dataTransfer.files[0];
    if (f) setFile(f, f.name);
  });
  dz.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') $('#file-input').click(); });

  document.querySelectorAll('[data-sample]').forEach((btn) => btn.addEventListener('click', async () => {
    const s = SAMPLES[btn.dataset.sample];
    try {
      const resp = await fetch(s.url);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      await setFile(await resp.blob(), s.name, s.pixelSize);
    } catch (err) {
      setStatus(`The sample could not be loaded (${err.message}).`, undefined, true);
    }
  }));

  $('#run').addEventListener('click', () => {
    if (!state.file || state.busy) return;
    const raw = $('#pixel-size').value.trim();
    const pixelSize = raw === '' ? 0 : Number(raw);
    if (raw !== '' && !(pixelSize > 0 && pixelSize < 1000)) {
      setStatus('The pixel size must be a positive number of µm per pixel.', undefined, true);
      return;
    }
    state.busy = true;
    updateRunButton();
    renderSteps(0);
    setStatus(`${STAGES[0]}…`, 0);
    worker.postMessage({
      type: 'analyze', bytes: state.file.bytes.slice(0), name: state.file.name,
      pixelSize, nBoot: Number($('#n-boot').value),
    });
  });

  function onError(message) {
    state.busy = false;
    updateRunButton();
    renderSteps(-1);
    setStatus(message, 0, true);
  }

  /* ------------------------------------------------------------------ results */
  function b64ToBlob(b64, type) {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
    return new Blob([bytes], { type });
  }

  function objectUrl(blob) {
    const url = URL.createObjectURL(blob);
    state.objectUrls.push(url);
    return url;
  }

  function download(url, filename) {
    const a = el('a', { href: url, download: filename });
    document.body.append(a);
    a.click();
    a.remove();
  }

  function onResult(result) {
    state.objectUrls.forEach(URL.revokeObjectURL);
    state.objectUrls = [];
    state.result = result;
    state.busy = false;
    updateRunButton();
    renderSteps(STAGES.length);
    const s = result.summary;
    setStatus(`Done: ${s.cells_observed.toLocaleString('en-US')} cells observed, ` +
      `${s.cells_estimated.toLocaleString('en-US')} estimated.`, 1);
    state.gallery = [];
    renderImages(result.images);
    renderCharts(result.charts);
    renderTables(result.tables);
    const zipUrl = objectUrl(b64ToBlob(result.zip, 'application/zip'));
    const btn = $('#download-all');
    btn.disabled = false;
    btn.onclick = () => download(zipUrl, `${state.stem}_rhizofit.zip`);
    $('#empty-state').hidden = true;
  }

  function card(item, kind) {
    const url = objectUrl(b64ToBlob(item.png, 'image/png'));
    const filename = `${state.stem}_${item.id}.png`;
    const index = state.gallery.push({ title: item.title, caption: item.caption, url, filename }) - 1;
    const img = el('img', { src: url, alt: item.title, loading: 'lazy' });
    const media = el('div', { className: 'card-media', title: 'Click to zoom' }, [img]);
    media.addEventListener('click', () => openLightbox(index));
    const zoomBtn = el('button', { className: 'icon', textContent: 'Zoom' });
    zoomBtn.addEventListener('click', () => openLightbox(index));
    const dlBtn = el('button', { className: 'icon', textContent: 'PNG' });
    dlBtn.addEventListener('click', () => download(url, filename));
    const title = el('div', { className: 'card-title' }, [
      el('strong', { textContent: item.title }),
      el('div', { className: 'card-actions' }, [zoomBtn, dlBtn]),
    ]);
    return el('article', { className: `card ${kind}` }, [
      media, el('div', { className: 'card-body' }, [title, el('p', { textContent: item.caption })]),
    ]);
  }

  function renderImages(images) {
    const groups = [];
    images.forEach((it) => {
      let g = groups.find((x) => x.name === it.group);
      if (!g) groups.push(g = { name: it.group, items: [] });
      g.items.push(it);
    });
    $('#image-groups').replaceChildren(...groups.map((g) => el('section', { className: 'group' }, [
      el('h3', { textContent: g.name }),
      el('div', { className: 'grid' }, g.items.map((it) => card(it, 'image'))),
    ])));
  }

  function renderCharts(charts) {
    $('#chart-grid').replaceChildren(...charts.map((c) => card(c, 'chart')));
  }

  /* ------------------------------------------------------------------ tables */
  const NUMBER = new Intl.NumberFormat('en-US', { maximumFractionDigits: 3 });

  function formatCell(v) {
    if (v === null || v === undefined || v === '') return '—';
    return typeof v === 'number' ? NUMBER.format(v) : String(v);
  }

  function toCsv(table) {
    const esc = (v) => {
      const s = v === null || v === undefined ? '' : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    return [table.columns, ...table.rows].map((r) => r.map(esc).join(',')).join('\n');
  }

  function renderTables(tables) {
    $('#tables').replaceChildren(...tables.map((t) => {
      const numericCol = t.columns.map((_, j) => t.rows.some((r) => typeof r[j] === 'number'));
      const wideCol = t.columns.map((c) => /detail|how it is measured/i.test(c));
      const head = el('tr', {}, t.columns.map((c, j) => el('th', { textContent: c, className: numericCol[j] ? 'num' : '' })));
      const body = t.rows.map((r) => {
        const tr = el('tr', { className: r[0] === 'Total' ? 'total' : '' }, r.map((v, j) => {
          const td = el('td', { className: numericCol[j] ? 'num' : (wideCol[j] ? 'text-wide' : '') });
          if (j === 0 && ZONE_SWATCH[v]) td.append(el('span', { className: 'swatch', style: `background:${ZONE_SWATCH[v]}` }));
          td.append(formatCell(v));
          return td;
        }));
        return tr;
      });
      const csvBtn = el('button', { className: 'icon', textContent: 'CSV' });
      csvBtn.addEventListener('click', () => download(objectUrl(new Blob([toCsv(t)], { type: 'text/csv' })),
        `${state.stem}_${t.id}.csv`));
      const copyBtn = el('button', { className: 'icon', textContent: 'Copy' });
      copyBtn.addEventListener('click', async () => {
        const tsv = [t.columns, ...t.rows].map((r) => r.map((v) => (v ?? '')).join('\t')).join('\n');
        try {
          await navigator.clipboard.writeText(tsv);
          copyBtn.textContent = 'Copied';
        } catch {
          copyBtn.textContent = 'Copy failed';
        }
        setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1500);
      });
      const parts = [
        el('div', { className: 'table-head' }, [el('h3', { textContent: t.title }),
          el('div', { className: 'card-actions' }, [copyBtn, csvBtn])]),
        el('div', { className: 'table-wrap' }, [el('table', {}, [el('thead', {}, [head]), el('tbody', {}, body)])]),
      ];
      if (t.note) parts.push(el('p', { className: 'table-note', textContent: t.note }));
      return el('section', { className: 'table-card' }, parts);
    }));
  }

  /* ------------------------------------------------------------------ tabs */
  function showTab(name) {
    document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
    document.querySelectorAll('.tab-panel').forEach((p) => p.classList.toggle('active', p.id === `tab-${name}`));
  }
  document.querySelectorAll('.tab').forEach((t) => t.addEventListener('click', () => showTab(t.dataset.tab)));
  document.querySelectorAll('[data-tab-link]').forEach((a) => a.addEventListener('click', (e) => {
    e.preventDefault();
    showTab(a.dataset.tabLink);
  }));

  /* ------------------------------------------------------------------ lightbox (zoom + pan) */
  const lb = { index: 0, scale: 1, x: 0, y: 0, drag: null, fit: 1 };
  const stage = $('#lightbox-stage');
  const lbImg = $('#lightbox-img');

  function applyTransform() {
    lbImg.style.transform = `translate(${lb.x}px, ${lb.y}px) scale(${lb.scale})`;
    $('#zoom-level').textContent = `${Math.round(lb.scale * 100)} %`;
    stage.classList.toggle('pixelated', lb.scale > 2.5);
  }

  function fitImage() {
    const w = stage.clientWidth;
    const h = stage.clientHeight;
    lb.fit = Math.min(w / lbImg.naturalWidth, h / lbImg.naturalHeight, 1);
    lb.scale = lb.fit;
    lb.x = (w - lbImg.naturalWidth * lb.scale) / 2;
    lb.y = (h - lbImg.naturalHeight * lb.scale) / 2;
    applyTransform();
  }

  function openLightbox(index) {
    lb.index = (index + state.gallery.length) % state.gallery.length;
    const item = state.gallery[lb.index];
    $('#lightbox-title').textContent = item.title;
    $('#lightbox-caption').textContent = item.caption;
    $('#lightbox').hidden = false;
    lbImg.onload = fitImage;
    lbImg.src = item.url;
    if (lbImg.complete && lbImg.naturalWidth) fitImage();
  }

  function closeLightbox() { $('#lightbox').hidden = true; }

  function zoomAt(factor, cx, cy) {
    const next = Math.min(Math.max(lb.scale * factor, lb.fit * 0.5), MAX_ZOOM);
    const k = next / lb.scale;
    lb.x = cx - (cx - lb.x) * k;
    lb.y = cy - (cy - lb.y) * k;
    lb.scale = next;
    applyTransform();
  }

  stage.addEventListener('wheel', (e) => {
    e.preventDefault();
    const r = stage.getBoundingClientRect();
    zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });
  stage.addEventListener('pointerdown', (e) => {
    lb.drag = { x: e.clientX - lb.x, y: e.clientY - lb.y };
    stage.setPointerCapture(e.pointerId);
    stage.classList.add('dragging');
  });
  stage.addEventListener('pointermove', (e) => {
    if (!lb.drag) return;
    lb.x = e.clientX - lb.drag.x;
    lb.y = e.clientY - lb.drag.y;
    applyTransform();
  });
  stage.addEventListener('pointerup', () => { lb.drag = null; stage.classList.remove('dragging'); });
  stage.addEventListener('dblclick', (e) => {
    const r = stage.getBoundingClientRect();
    if (lb.scale > lb.fit * 1.05) fitImage();
    else zoomAt(2.5, e.clientX - r.left, e.clientY - r.top);
  });
  $('#lb-fit').addEventListener('click', fitImage);
  $('#lb-close').addEventListener('click', closeLightbox);
  $('#lb-prev').addEventListener('click', () => openLightbox(lb.index - 1));
  $('#lb-next').addEventListener('click', () => openLightbox(lb.index + 1));
  $('#lb-download').addEventListener('click', () => {
    const item = state.gallery[lb.index];
    download(item.url, item.filename);
  });
  window.addEventListener('keydown', (e) => {
    if ($('#lightbox').hidden) return;
    if (e.key === 'Escape') closeLightbox();
    if (e.key === 'ArrowLeft') openLightbox(lb.index - 1);
    if (e.key === 'ArrowRight') openLightbox(lb.index + 1);
    if (e.key === '+' || e.key === '=') zoomAt(1.25, stage.clientWidth / 2, stage.clientHeight / 2);
    if (e.key === '-') zoomAt(0.8, stage.clientWidth / 2, stage.clientHeight / 2);
  });
  window.addEventListener('resize', () => { if (!$('#lightbox').hidden) fitImage(); });

  renderSteps(-1);
})();
