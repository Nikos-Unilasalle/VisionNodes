/* Pyodide module worker: loads the Python runtime and the VNStudio engine bundle, runs analyses. */
const PYODIDE_VERSION = '314.0.7';
const PYODIDE_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
const PACKAGES = ['numpy', 'scipy', 'scikit-image', 'matplotlib', 'pillow', 'opencv-python', 'typing-extensions'];

let pyodide = null;

function post(type, payload = {}) {
  self.postMessage({ type, ...payload });
}

/* Called from Python (`from js import report_progress`). */
self.report_progress = (stage, fraction) => post('progress', { stage, fraction });

async function init() {
  post('boot', { message: 'Downloading the Python runtime…', fraction: 0.05 });
  const { loadPyodide } = await import(`${PYODIDE_URL}pyodide.mjs`);
  pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
  post('boot', { message: 'Loading scientific packages (first visit only: ~40 MB)…', fraction: 0.2 });
  let loaded = 0;
  await pyodide.loadPackage(PACKAGES, {
    messageCallback: (msg) => {
      if (msg.startsWith('Loaded')) {
        loaded += 1;
        post('boot', { message: msg, fraction: 0.2 + 0.65 * Math.min(loaded / 20, 1) });
      }
    },
    errorCallback: (msg) => post('boot', { message: msg, fraction: 0.5 }),
  });
  post('boot', { message: 'Starting the VNStudio engine (importing OpenCV and scikit-image)…', fraction: 0.9 });
  const resp = await fetch('engine.zip', { cache: 'no-cache' });
  if (!resp.ok) throw new Error(`engine.zip: HTTP ${resp.status}`);
  pyodide.FS.mkdirTree('/app');
  pyodide.unpackArchive(new Uint8Array(await resp.arrayBuffer()), 'zip', { extractDir: '/app' });
  pyodide.runPython(`
import sys, base64, json
sys.path.insert(0, '/app/scripts')
import root_web_runner as W
from js import report_progress

def _b64(data):
    return base64.b64encode(data).decode('ascii')

def run_analysis(path, pixel_size, n_boot, walled_lacunae):
    res = W.analyze(path, pixel_size or None, n_boot=int(n_boot), progress=report_progress,
                    walled_lacunae=bool(walled_lacunae))
    payload = {
        'images': [{**{k: v for k, v in it.items() if k != 'png'}, 'png': _b64(it['png'])} for it in res['images']],
        'charts': [{**{k: v for k, v in it.items() if k != 'png'}, 'png': _b64(it['png'])} for it in res['charts']],
        'tables': res['tables'],
        'summary': res['summary'],
        'zip': _b64(W.bundle_zip(res)),
    }
    return json.dumps(payload, default=float)
`);
  post('ready');
}

async function analyze({ bytes, name, pixelSize, nBoot, walledLacunae }) {
  const ext = (name.match(/\.[a-z0-9]+$/i) || ['.png'])[0].toLowerCase();
  const path = `/tmp/upload${ext}`;
  pyodide.FS.writeFile(path, new Uint8Array(bytes));
  const runAnalysis = pyodide.globals.get('run_analysis');
  try {
    const json = runAnalysis(path, pixelSize || 0, nBoot, Boolean(walledLacunae));
    post('result', { result: JSON.parse(json) });
  } catch (err) {
    const msg = String(err.message || err);
    const userLine = msg.match(/AnalysisError: (.*)/);
    post('error', { message: userLine ? userLine[1] : 'The analysis failed. Details: ' + msg.split('\n').slice(-3).join(' ') });
  } finally {
    runAnalysis.destroy();
  }
}

const ready = init().catch((err) => post('fatal', { message: String(err.message || err) }));

self.onmessage = async (event) => {
  await ready;
  if (event.data.type === 'analyze') await analyze(event.data);
};
