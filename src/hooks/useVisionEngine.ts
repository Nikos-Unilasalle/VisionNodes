import { useState, useEffect, useCallback, useRef } from 'react';

export function useVisionEngine(onCapture?: (nodeId: string, base64: string) => void) {
  const [frame, setFrame] = useState<string | null>(null);
  const [nodesData, setNodesData] = useState<Record<string, any>>({});
  const [pluginSchemas, setPluginSchemas] = useState<any[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [lastCommands, setLastCommands] = useState<any[]>([]);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    const connect = () => {
      ws.current = new WebSocket('ws://localhost:8765');
      
      ws.current.onopen = () => setIsConnected(true);

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
          }
        } catch (e) {}
      };

      ws.current.onclose = () => {
        setIsConnected(false);
        setTimeout(connect, 2000);
      };
    };

    connect();
    return () => ws.current?.close();
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

  return { frame, nodesData, pluginSchemas, isConnected, updateGraph, requestCapture, setPreviewNode, lastCommands };
}
