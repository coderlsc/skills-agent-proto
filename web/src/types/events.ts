export type ThinkingEvent = {
  type: "thinking";
  content: string;
  id?: number;
};

export type TextEvent = {
  type: "text";
  content: string;
};

export type ToolCallEvent = {
  type: "tool_call";
  name: string;
  args: Record<string, unknown>;
  id?: string;
};

export type ToolResultEvent = {
  type: "tool_result";
  name: string;
  content: string;
  success?: boolean;
  tool_use_id?: string;
};

export type DoneEvent = {
  type: "done";
  response?: string;
};

export type ErrorEvent = {
  type: "error";
  message: string;
};

export type AgentStreamEvent =
  | ThinkingEvent
  | TextEvent
  | ToolCallEvent
  | ToolResultEvent
  | DoneEvent
  | ErrorEvent;

// 存储的消息类型（从数据库加载）
export type StoredMessage = {
  id: number;
  role: "human" | "ai" | "tool" | "system";
  content: string;
  reasoning_content?: string;
  tool_calls?: string;  // JSON 字符串
  tool_results?: string;  // JSON 字符串
  tool_call_id?: string;
  created_at: string;
};

export type StoredToolResult = {
  [toolCallId: string]: {
    name: string;
    result: string;
    success: boolean;
  };
};
