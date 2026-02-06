import type { AgentStreamEvent } from "../types/events";

const STREAM_EVENT_TYPES = [
  "thinking",
  "text",
  "tool_call",
  "tool_result",
  "done",
  "error",
] as const;

type StreamOptions = {
  apiBaseUrl: string;
  message: string;
  threadId: string;
  onEvent: (event: AgentStreamEvent) => void;
  onError: (error: string) => void;
};

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
}

export function openChatStream({
  apiBaseUrl,
  message,
  threadId,
  onEvent,
  onError,
}: StreamOptions): () => void {
  const endpoint = new URL(`${normalizeBaseUrl(apiBaseUrl)}/api/chat/stream`);
  endpoint.searchParams.set("message", message);
  endpoint.searchParams.set("thread_id", threadId);

  const source = new EventSource(endpoint.toString());

  for (const eventName of STREAM_EVENT_TYPES) {
    source.addEventListener(eventName, (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent<string>).data) as AgentStreamEvent;
        onEvent(payload);

        if (payload.type === "done" || payload.type === "error") {
          source.close();
        }
      } catch (err) {
        const messageFromError = err instanceof Error ? err.message : String(err);
        onError(`Failed to parse SSE payload: ${messageFromError}`);
        source.close();
      }
    });
  }

  source.onerror = () => {
    onError("SSE connection failed.");
    source.close();
  };

  return () => {
    source.close();
  };
}
