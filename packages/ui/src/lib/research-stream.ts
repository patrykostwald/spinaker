export type StreamEvent = { event: string; data: unknown };

// Network chunks need not align with SSE lines, JSON, or UTF-8 characters.
export async function readResearchStream(response: Response, receive: (event: StreamEvent) => void, signal: AbortSignal) {
  if (!response.body) throw new Error('Przeglądarka nie otrzymała strumienia wyników.');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const cancel = () => { void reader.cancel().catch(() => {}); };
  signal.addEventListener('abort', cancel, { once: true });
  try {
    while (!signal.aborted) {
      const chunk = await reader.read();
      buffer += decoder.decode(chunk.value, { stream: !chunk.done });
      let match: RegExpExecArray | null;
      while ((match = /\r?\n\r?\n/.exec(buffer))) {
        const frame = buffer.slice(0, match.index);
        buffer = buffer.slice(match.index + match[0].length);
        const lines = frame.split(/\r?\n/);
        const event = lines.find(line => line.startsWith('event:'))?.slice(6).trim() || 'message';
        const data = lines.filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
        if (data && !signal.aborted) receive({ event, data: JSON.parse(data) });
      }
      if (buffer.length > 1_000_000) throw new Error('Strumień przekroczył dozwolony rozmiar.');
      if (chunk.done) break;
    }
  } finally {
    signal.removeEventListener('abort', cancel);
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
