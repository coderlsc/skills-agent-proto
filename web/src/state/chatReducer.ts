import type {
  AgentStreamEvent,
  DoneEvent,
  ErrorEvent,
  ThinkingEvent,
  ToolCallEvent,
  ToolResultEvent,
  TextEvent,
} from "../types/events";

export type RunPhase =
  | "waiting"
  | "thinking"
  | "analyzing"
  | "responding"
  | "done"
  | "error";

export type ToolStatus = "running" | "success" | "failed";

export type SkillSummary = {
  name: string;
  description: string;
  path: string;
};

export type SessionSummary = {
  id: number;
  thread_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type ToolCallView = {
  id: string;
  name: string;
  args: Record<string, unknown>;
  status: ToolStatus;
  result?: string;
  success?: boolean;
  expanded?: boolean;
  skillName?: string;
};

export type UserEntry = {
  kind: "user";
  id: string;
  text: string;
  createdAt: number;
};

export type AssistantEntry = {
  kind: "assistant";
  id: string;
  createdAt: number;
  phase: RunPhase;
  thinking: string;
  response: string;
  tools: ToolCallView[];
  error?: string;
};

export type SystemEntry = {
  kind: "system";
  id: string;
  text: string;
  markdown: boolean;
  createdAt: number;
};

export type TimelineEntry = UserEntry | AssistantEntry | SystemEntry;

export type ThreadState = {
  id: string;
  label: string;
  timeline: TimelineEntry[];
  activeAssistantEntryId?: string;
  activeSkillName?: string;
};

export type ChatState = {
  skills: SkillSummary[];
  skillsLoaded: boolean;
  skillsError?: string;
  promptCache?: string;
  threads: Record<string, ThreadState>;
  threadOrder: string[];
  activeThreadId: string;
  isStreaming: boolean;
  streamError?: string;
  // 会话管理
  sessions: SessionSummary[];
  sessionsLoaded: boolean;
  sessionsError?: string;
  leftPanelTab: "skills" | "sessions";
};

export type ChatAction =
  | { type: "skills_loaded"; skills: SkillSummary[] }
  | { type: "skills_failed"; message: string }
  | { type: "prompt_loaded"; prompt: string }
  | { type: "create_thread"; threadId: string; label: string }
  | { type: "switch_thread"; threadId: string }
  | {
      type: "submit_user_message";
      threadId: string;
      message: string;
      userEntryId: string;
      assistantEntryId: string;
      createdAt: number;
    }
  | {
      type: "append_user_entry";
      threadId: string;
      entryId: string;
      text: string;
      createdAt: number;
    }
  | {
      type: "append_assistant_entry";
      threadId: string;
      entryId: string;
      response: string;
      tools: ToolCallView[];
      thinking?: string;  // 可选的 thinking 内容
      createdAt: number;
    }
  | {
      type: "append_system_message";
      threadId: string;
      entryId: string;
      message: string;
      markdown: boolean;
      createdAt: number;
    }
  | {
      type: "stream_event";
      threadId: string;
      assistantEntryId: string;
      event: AgentStreamEvent;
    }
  | {
      type: "toggle_tool_expand";
      threadId: string;
      assistantEntryId: string;
      toolId: string;
    }
  | {
      type: "stream_failed";
      threadId: string;
      assistantEntryId: string;
      message: string;
    }
  // 会话管理 actions
  | { type: "sessions_loaded"; sessions: SessionSummary[] }
  | { type: "sessions_failed"; message: string }
  | { type: "switch_left_panel"; tab: "skills" | "sessions" }
  | { type: "load_session"; threadId: string };

const DEFAULT_THREAD_ID = "thread-1";

export function createInitialState(): ChatState {
  return {
    skills: [],
    skillsLoaded: false,
    threads: {
      [DEFAULT_THREAD_ID]: {
        id: DEFAULT_THREAD_ID,
        label: "Thread 1",
        timeline: [],
      },
    },
    threadOrder: [DEFAULT_THREAD_ID],
    activeThreadId: DEFAULT_THREAD_ID,
    isStreaming: false,
    // 会话管理
    sessions: [],
    sessionsLoaded: false,
    leftPanelTab: "skills",
  };
}

function getThread(state: ChatState, threadId: string): ThreadState | undefined {
  return state.threads[threadId];
}

function replaceThread(
  state: ChatState,
  threadId: string,
  thread: ThreadState,
): ChatState {
  return {
    ...state,
    threads: {
      ...state.threads,
      [threadId]: thread,
    },
  };
}

function inferToolSuccess(content: string, explicit?: boolean): boolean {
  if (typeof explicit === "boolean") {
    return explicit;
  }
  return !content.trimStart().startsWith("[FAILED]");
}

function updateAssistantEntry(
  thread: ThreadState,
  assistantEntryId: string,
  updater: (assistant: AssistantEntry) => AssistantEntry,
): ThreadState {
  const nextTimeline = thread.timeline.map((entry) => {
    if (entry.kind !== "assistant" || entry.id !== assistantEntryId) {
      return entry;
    }
    return updater(entry);
  });

  return {
    ...thread,
    timeline: nextTimeline,
  };
}

function upsertToolCall(
  tools: ToolCallView[],
  event: ToolCallEvent,
): { tools: ToolCallView[]; skillName?: string } {
  const args = event.args ?? {};
  const toolId = event.id?.trim() || `${event.name}-${tools.length + 1}`;
  const existingIndex = tools.findIndex((item) => item.id === toolId);

  let skillName: string | undefined;
  if (event.name === "load_skill") {
    const maybeSkill = args["skill_name"];
    if (typeof maybeSkill === "string" && maybeSkill.trim()) {
      skillName = maybeSkill.trim();
    }
  }

  const nextTool: ToolCallView = {
    id: toolId,
    name: event.name,
    args,
    status: "running",
    skillName,
  };

  if (existingIndex >= 0) {
    const cloned = [...tools];
    const original = cloned[existingIndex];
    cloned[existingIndex] = {
      ...original,
      ...nextTool,
      expanded: original.expanded,
      result: original.result,
      success: original.success,
      status: original.status === "running" ? "running" : original.status,
      skillName: skillName ?? original.skillName,
    };
    return { tools: cloned, skillName };
  }

  return { tools: [...tools, nextTool], skillName };
}

function applyToolResult(
  tools: ToolCallView[],
  event: ToolResultEvent,
): ToolCallView[] {
  const success = inferToolSuccess(event.content, event.success);
  const nextStatus: ToolStatus = success ? "success" : "failed";

  // 优先使用 tool_use_id 精确匹配（支持并行同名工具调用）
  let index = tools.findIndex((tool) => tool.id === event.tool_use_id);

  if (index < 0 && !event.tool_use_id) {
    // Fallback：如果没有 tool_use_id，才用 name + status 匹配
    index = tools.findIndex(
      (tool) => tool.status === "running" && tool.name === event.name,
    );
  }

  if (index < 0 && !event.tool_use_id) {
    // 最后的兜底：匹配任意运行中的工具
    index = tools.findIndex((tool) => tool.status === "running");
  }

  if (index < 0) {
    const fallbackId = `${event.name}-${tools.length + 1}`;
    return [
      ...tools,
      {
        id: fallbackId,
        name: event.name,
        args: {},
        status: nextStatus,
        result: event.content,
        success,
        expanded: false,
      },
    ];
  }

  const cloned = [...tools];
  cloned[index] = {
    ...cloned[index],
    status: nextStatus,
    result: event.content,
    success,
  };
  return cloned;
}

function applyThinkingEvent(
  assistant: AssistantEntry,
  event: ThinkingEvent,
): AssistantEntry {
  return {
    ...assistant,
    phase: "thinking",
    thinking: assistant.thinking + event.content,
  };
}

function applyTextEvent(
  assistant: AssistantEntry,
  event: TextEvent,
): AssistantEntry {
  return {
    ...assistant,
    phase: "responding",
    response: assistant.response + event.content,
  };
}

function applyDoneEvent(
  assistant: AssistantEntry,
  event: DoneEvent,
): AssistantEntry {
  return {
    ...assistant,
    phase: "done",
    response: assistant.response || event.response || "",
  };
}

function applyErrorEvent(
  assistant: AssistantEntry,
  event: ErrorEvent,
): AssistantEntry {
  return {
    ...assistant,
    phase: "error",
    error: event.message,
  };
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "skills_loaded":
      return {
        ...state,
        skills: action.skills,
        skillsLoaded: true,
        skillsError: undefined,
      };

    case "skills_failed":
      return {
        ...state,
        skillsLoaded: true,
        skillsError: action.message,
      };

    case "prompt_loaded":
      return {
        ...state,
        promptCache: action.prompt,
      };

    case "create_thread": {
      if (state.threads[action.threadId]) {
        return {
          ...state,
          activeThreadId: action.threadId,
        };
      }

      return {
        ...state,
        threads: {
          ...state.threads,
          [action.threadId]: {
            id: action.threadId,
            label: action.label,
            timeline: [],
          },
        },
        threadOrder: [...state.threadOrder, action.threadId],
        activeThreadId: action.threadId,
      };
    }

    case "switch_thread":
      if (!state.threads[action.threadId]) {
        return state;
      }
      return {
        ...state,
        activeThreadId: action.threadId,
      };

    case "submit_user_message": {
      const thread = getThread(state, action.threadId);
      if (!thread) {
        return state;
      }

      const updatedThread: ThreadState = {
        ...thread,
        activeAssistantEntryId: action.assistantEntryId,
        timeline: [
          ...thread.timeline,
          {
            kind: "user",
            id: action.userEntryId,
            text: action.message,
            createdAt: action.createdAt,
          },
          {
            kind: "assistant",
            id: action.assistantEntryId,
            createdAt: action.createdAt,
            phase: "waiting",
            thinking: "",
            response: "",
            tools: [],
          },
        ],
      };

      return {
        ...replaceThread(state, action.threadId, updatedThread),
        isStreaming: true,
        streamError: undefined,
      };
    }

    case "append_system_message": {
      const thread = getThread(state, action.threadId);
      if (!thread) {
        return state;
      }

      const updatedThread: ThreadState = {
        ...thread,
        timeline: [
          ...thread.timeline,
          {
            kind: "system",
            id: action.entryId,
            text: action.message,
            markdown: action.markdown,
            createdAt: action.createdAt,
          },
        ],
      };
      return replaceThread(state, action.threadId, updatedThread);
    }

    case "append_user_entry": {
      const thread = getThread(state, action.threadId);
      if (!thread) {
        return state;
      }

      const updatedThread: ThreadState = {
        ...thread,
        timeline: [
          ...thread.timeline,
          {
            kind: "user",
            id: action.entryId,
            text: action.text,
            createdAt: action.createdAt,
          },
        ],
      };
      return replaceThread(state, action.threadId, updatedThread);
    }

    case "append_assistant_entry": {
      const thread = getThread(state, action.threadId);
      if (!thread) {
        return state;
      }

      const updatedThread: ThreadState = {
        ...thread,
        timeline: [
          ...thread.timeline,
          {
            kind: "assistant",
            id: action.entryId,
            createdAt: action.createdAt,
            phase: "done",
            thinking: action.thinking || "",  // 使用传入的 thinking 或空字符串
            response: action.response,
            tools: action.tools,
          },
        ],
      };
      return replaceThread(state, action.threadId, updatedThread);
    }

    case "stream_event": {
      const thread = getThread(state, action.threadId);
      if (!thread) {
        return state;
      }

      let nextThread = thread;
      nextThread = updateAssistantEntry(nextThread, action.assistantEntryId, (assistant) => {
        const event = action.event;
        switch (event.type) {
          case "thinking":
            return applyThinkingEvent(assistant, event);

          case "text":
            return applyTextEvent(assistant, event);

          case "tool_call": {
            const { tools } = upsertToolCall(assistant.tools, event);
            return {
              ...assistant,
              tools,
            };
          }

          case "tool_result":
            return {
              ...assistant,
              phase: "analyzing",
              tools: applyToolResult(assistant.tools, event),
            };

          case "done":
            return applyDoneEvent(assistant, event);

          case "error":
            return applyErrorEvent(assistant, event);

          default:
            return assistant;
        }
      });

      if (action.event.type === "tool_call" && action.event.name === "load_skill") {
        const maybeSkill = action.event.args?.["skill_name"];
        if (typeof maybeSkill === "string" && maybeSkill.trim()) {
          nextThread = {
            ...nextThread,
            activeSkillName: maybeSkill.trim(),
          };
        }
      }

      if (action.event.type === "done" || action.event.type === "error") {
        nextThread = {
          ...nextThread,
          activeAssistantEntryId: undefined,
        };
      }

      return {
        ...replaceThread(state, action.threadId, nextThread),
        isStreaming:
          action.event.type === "done" || action.event.type === "error"
            ? false
            : state.isStreaming,
        streamError:
          action.event.type === "error" ? action.event.message : state.streamError,
      };
    }

    case "toggle_tool_expand": {
      const thread = getThread(state, action.threadId);
      if (!thread) {
        return state;
      }

      const updatedThread = updateAssistantEntry(
        thread,
        action.assistantEntryId,
        (assistant) => ({
          ...assistant,
          tools: assistant.tools.map((tool) =>
            tool.id === action.toolId
              ? { ...tool, expanded: !tool.expanded }
              : tool,
          ),
        }),
      );

      return replaceThread(state, action.threadId, updatedThread);
    }

    case "stream_failed": {
      const thread = getThread(state, action.threadId);
      if (!thread) {
        return {
          ...state,
          isStreaming: false,
          streamError: action.message,
        };
      }

      const updatedThread = updateAssistantEntry(
        thread,
        action.assistantEntryId,
        (assistant) => ({
          ...assistant,
          phase: "error",
          error: action.message,
        }),
      );

      return {
        ...replaceThread(state, action.threadId, {
          ...updatedThread,
          activeAssistantEntryId: undefined,
        }),
        isStreaming: false,
        streamError: action.message,
      };
    }

    case "sessions_loaded":
      return {
        ...state,
        sessions: action.sessions,
        sessionsLoaded: true,
        sessionsError: undefined,
      };

    case "sessions_failed":
      return {
        ...state,
        sessionsLoaded: true,
        sessionsError: action.message,
      };

    case "switch_left_panel":
      return {
        ...state,
        leftPanelTab: action.tab,
      };

    case "load_session":
      return {
        ...state,
        activeThreadId: action.threadId,
        leftPanelTab: "sessions",
      };

    default:
      return state;
  }
}
