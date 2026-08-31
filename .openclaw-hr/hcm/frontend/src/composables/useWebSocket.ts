import { ref, onMounted, onUnmounted } from 'vue'

export type WSEvent =
  | { event: 'node_updated'; data: { candidate_id: number; node_type: string; status: string; data: Record<string, any> }; ts: string }

export function useWebSocket(onEvent: (evt: WSEvent) => void) {
  const connected = ref(false)
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${location.host}/ws/dashboard`
    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
    }

    ws.onmessage = (msg) => {
      try {
        const evt = JSON.parse(msg.data) as WSEvent
        onEvent(evt)
      } catch { /* ignore malformed messages */ }
    }

    ws.onclose = () => {
      connected.value = false
      reconnectTimer = setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  onMounted(connect)

  onUnmounted(() => {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    ws?.close()
  })

  return { connected }
}
