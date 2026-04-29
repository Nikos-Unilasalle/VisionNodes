import { useState, useEffect, useCallback, useRef } from 'react';

export type EngineNotification = {
  id: string;
  message: string;
  progress: number | null;
  level: 'info' | 'warning' | 'error';
};


export function useVisionEngine(onCapture?: (nodeId: string, base64: string) => void) {
  const [frame, setFrame] = useState<string | null>(null);
  const [nodesData, setNodesData] = useState<Record<string, any>>({});
  const [pluginSchemas, setPluginSchemas] = useState<any[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [lastCommands, setLastCommands] = useState<any[]>([]);
  const [notifications, setNotifications] = useState<EngineNotification[]>([]);
  const ws = useRef<WebSocket | null>(null);
  const dismissTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    let retryDelay = 1000;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      ws.current = new WebSocket('ws://localhost:8765');
      
      ws.current.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'update') {
            setFrame(`data:image/jpeg;base64,${msg.image}`);
            if (msg.nodes_data) {
                setNodesData(msg.nodes_data);
            }
            if (msg.commands && msg.commands.length > 0) {
              setLastCommands(msg.commands);
            } else {
              setLastCommands(prev => prev.length > 0 ? [] : prev);
            }
          } else if (msg.type === 'schema') {
            setPluginSchemas(msg.nodes);
          } else if (msg.type === 'node_capture') {
            onCapture?.(msg.node_id, msg.image);
          } else if (msg.type === 'notification') {
            const n: EngineNotification = {
              id: msg.id, message: msg.message,
              progress: msg.progress ?? null, level: msg.level ?? 'info'
            };
            setNotifications(prev => {
              const idx = prev.findIndex(x => x.id === n.id);
              return idx >= 0 ? prev.map((x, i) => i === idx ? n : x) : [...prev, n];
            });
            // Errors: never auto-dismiss (user must click ×)
            // Completion (progress=1): dismiss after 3s
            // In-progress: keep until updated
            if (n.level !== 'error') {
              const delay = (n.progress !== null && n.progress >= 1) ? 3000 : 60000;
              clearTimeout(dismissTimers.current[n.id]);
              dismissTimers.current[n.id] = setTimeout(() => {
                setNotifications(prev => prev.filter(x => x.id !== n.id));
                delete dismissTimers.current[n.id];
              }, delay);
            } else {
              clearTimeout(dismissTimers.current[n.id]);
            }
          }
        } catch (e) {
          console.warn('[Engine] Message parse error:', e);
        }
      };

      ws.current.onopen = () => {
        setIsConnected(true);
        retryDelay = 1000;
      };

      ws.current.onclose = () => {
        setIsConnected(false);
        retryTimer = setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 16000);
      };
    };

    connect();
    return () => {
      if (retryTimer) clearTimeout(retryTimer);
      ws.current?.close();
    };
  }, [onCapture]);

  const updateGraph = useCallback((nodes: any[], edges: any[]) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({
        type: 'update_graph',
        graph: { nodes: nodes.map(n => ({ id: n.id, type: n.type, data: n.data })), edges }
      }));
    }
  }, []);

  const requestCapture = useCallback((nodeId: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'request_node_capture', node_id: nodeId }));
    }
  }, []);

  const setPreviewNode = useCallback((nodeId: string | null) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'set_preview_node', node_id: nodeId }));
    }
  }, []);

  const dismissNotification = (id: string) => {
    clearTimeout(dismissTimers.current[id]);
    delete dismissTimers.current[id];
    setNotifications(prev => prev.filter(x => x.id !== id));
  };

  const pushNotification = useCallback((message: string, level: EngineNotification['level'] = 'info', ttl = 4000) => {
    const id = 'fe_' + Date.now();
    setNotifications(prev => {
      const next = [...prev.slice(-9), { id, message, progress: null, level }];
      return next;
    });
    if (ttl > 0) {
      dismissTimers.current[id] = setTimeout(() => dismissNotification(id), ttl);
    }
  }, []);

  return { frame, nodesData, pluginSchemas, isConnected, updateGraph, requestCapture, setPreviewNode, lastCommands, notifications, dismissNotification, pushNotification };
}
