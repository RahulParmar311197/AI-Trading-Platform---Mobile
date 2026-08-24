const DEFAULT_WS_URL = 'ws://10.0.2.2:8000';

export function connectMarketStream(symbol = 'NIFTY', {onTick, onOpen, onError, onClose, baseUrl = DEFAULT_WS_URL, reconnectMs = 2000} = {}) {
  let socket = null;
  let stopped = false;
  let timer = null;
  const connect = () => {
    if (stopped) return;
    socket = new WebSocket(`${baseUrl}/api/realtime/ws/${encodeURIComponent(symbol)}`);
    socket.onopen = () => onOpen?.();
    socket.onmessage = event => { try { onTick?.(JSON.parse(event.data)); } catch (e) { onError?.(e); } };
    socket.onerror = event => onError?.(event);
    socket.onclose = event => { onClose?.(event); if (!stopped) timer = setTimeout(connect, reconnectMs); };
  };
  connect();
  return () => { stopped = true; if (timer) clearTimeout(timer); socket?.close(); };
}
