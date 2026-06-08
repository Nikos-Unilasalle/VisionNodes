import { useEffect, useRef, useCallback } from 'react';
import { writeTextFile, readTextFile, mkdir, exists } from '@tauri-apps/plugin-fs';
import { BaseDirectory } from '@tauri-apps/api/path';
import type { Canvas } from '../data/canvases';

const AUTOSAVE_DIR = '.vnstudio/autosave';
const AUTOSAVE_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

/** One autosave file per canvas, e.g. .vnstudio/autosave/c1.vn */
function autosavePath(canvasId: string): string {
  return `${AUTOSAVE_DIR}/${canvasId}.vn`;
}

interface AutosavePayload {
  name: string;
  filePath: string | null;
  savedAt: number;
  nodes: Canvas['nodes'];
  edges: Canvas['edges'];
}

export interface AutosaveRecovery {
  canvasId: string;
  name: string;
  filePath: string | null;
  savedAt: number;
  nodes: Canvas['nodes'];
  edges: Canvas['edges'];
}

interface UseAutosaveArgs {
  /** Live ref to the current canvases array (avoids stale closures / interval resets). */
  canvasesRef: React.MutableRefObject<Canvas[]>;
  /** Notify the user (info/error). Kept quiet on the happy path. */
  pushNotification: (msg: string, level?: 'info' | 'error' | 'warning') => void;
  /** Whether the engine/app is ready — gates autosave start. */
  enabled?: boolean;
}

/**
 * Periodic crash-protection autosave. Writes each non-empty canvas to
 * ~/.vnstudio/autosave/<canvasId>.vn every 5 minutes (and on tab-hide / unload).
 * Exposes `recoverAll()` for startup recovery.
 */
export function useAutosave({ canvasesRef, pushNotification, enabled = true }: UseAutosaveArgs) {
  // Hash of last-written content per canvas — skip identical writes.
  const lastHashRef = useRef<Record<string, string>>({});
  const writingRef = useRef(false);

  const ensureDir = useCallback(async () => {
    try {
      const dirExists = await exists(AUTOSAVE_DIR, { baseDir: BaseDirectory.Home });
      if (!dirExists) {
        await mkdir(AUTOSAVE_DIR, { baseDir: BaseDirectory.Home, recursive: true });
      }
    } catch (err) {
      console.error('[autosave] mkdir failed:', err);
      throw err;
    }
  }, []);

  const writeAll = useCallback(async () => {
    if (writingRef.current) return;
    writingRef.current = true;
    try {
      const canvases = canvasesRef.current;
      const hasContent = canvases.some(c => c.nodes.length > 0);
      if (!hasContent) return;

      await ensureDir();

      let written = 0;
      for (const c of canvases) {
        if (c.nodes.length === 0) continue;
        const payload: AutosavePayload = {
          name: c.name,
          filePath: c.filePath,
          savedAt: Date.now(),
          nodes: c.nodes,
          edges: c.edges,
        };
        const body = JSON.stringify(payload);
        // Skip if unchanged since last autosave (cheap length+content hash).
        const hash = `${body.length}:${c.nodes.length}:${c.edges.length}`;
        if (lastHashRef.current[c.id] === hash) continue;
        await writeTextFile(autosavePath(c.id), body, { baseDir: BaseDirectory.Home });
        lastHashRef.current[c.id] = hash;
        written++;
      }
      if (written > 0) console.log(`[autosave] wrote ${written} canvas(es)`);
    } catch (err) {
      console.error('[autosave] write failed:', err);
    } finally {
      writingRef.current = false;
    }
  }, [canvasesRef, ensureDir]);

  // Periodic timer + best-effort flush on tab-hide / unload.
  useEffect(() => {
    if (!enabled) return;
    const timer = setInterval(writeAll, AUTOSAVE_INTERVAL_MS);
    const onHide = () => { if (document.visibilityState === 'hidden') void writeAll(); };
    document.addEventListener('visibilitychange', onHide);
    window.addEventListener('beforeunload', writeAll);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onHide);
      window.removeEventListener('beforeunload', writeAll);
    };
  }, [enabled, writeAll]);

  /** Read all autosave files that contain content. Used for startup recovery. */
  const recoverAll = useCallback(async (canvasIds: string[]): Promise<AutosaveRecovery[]> => {
    const out: AutosaveRecovery[] = [];
    for (const id of canvasIds) {
      try {
        const path = autosavePath(id);
        if (!(await exists(path, { baseDir: BaseDirectory.Home }))) continue;
        const raw = await readTextFile(path, { baseDir: BaseDirectory.Home });
        const data = JSON.parse(raw) as AutosavePayload;
        if (!data.nodes || data.nodes.length === 0) continue;
        out.push({
          canvasId: id,
          name: data.name,
          filePath: data.filePath ?? null,
          savedAt: data.savedAt ?? 0,
          nodes: data.nodes,
          edges: data.edges ?? [],
        });
      } catch (err) {
        console.error(`[autosave] recover ${id} failed:`, err);
      }
    }
    return out;
  }, []);

  /** Force an immediate autosave (e.g. exposed to a manual trigger). */
  const flush = useCallback(() => writeAll(), [writeAll]);

  return { recoverAll, flush };
}
