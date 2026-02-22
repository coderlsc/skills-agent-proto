import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";

import { ChatTimeline } from "./components/ChatTimeline";
import { Composer } from "./components/Composer";
import { SkillPanel } from "./components/SkillPanel";
import { SessionPanel } from "./components/SessionPanel";
import { openChatStream } from "./lib/sse";
import {
  chatReducer,
  createInitialState,
  type SkillSummary,
  type SessionSummary,
} from "./state/chatReducer";
import type { AgentStreamEvent } from "./types/events";
import "./App.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || "http://localhost:8001";

function makeId(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function skillsAsMarkdown(skills: SkillSummary[]): string {
  if (!skills.length) {
    return "No skills discovered.";
  }

  return [
    "## Available Skills",
    ...skills.map(
      (skill) =>
        `- **${skill.name}**: ${skill.description || "No description"}\n  - path: \`${skill.path}\``,
    ),
  ].join("\n");
}

function promptAsMarkdown(prompt: string): string {
  const escaped = prompt.replaceAll("```", "` ` `");
  return `## System Prompt\n\n\`\`\`text\n${escaped}\n\`\`\``;
}

export default function App() {
  const [state, dispatch] = useReducer(chatReducer, undefined, createInitialState);
  const streamCloserRef = useRef<(() => void) | null>(null);

  const activeThread = state.threads[state.activeThreadId];

  // 加载 Skills 列表
  useEffect(() => {
    let cancelled = false;

    const loadSkills = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/skills`);
        if (!response.ok) {
          throw new Error(`Failed to load skills (${response.status})`);
        }
        const payload = (await response.json()) as { skills: SkillSummary[] };
        if (!cancelled) {
          dispatch({ type: "skills_loaded", skills: payload.skills || [] });
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (!cancelled) {
          dispatch({ type: "skills_failed", message });
        }
      }
    };

    loadSkills();

    return () => {
      cancelled = true;
    };
  }, []);

  // 加载会话列表
  useEffect(() => {
    let cancelled = false;

    const loadSessions = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/sessions`);
        if (!response.ok) {
          throw new Error(`Failed to load sessions (${response.status})`);
        }
        const payload = (await response.json()) as { sessions: SessionSummary[] };
        if (!cancelled) {
          dispatch({ type: "sessions_loaded", sessions: payload.sessions || [] });
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (!cancelled) {
          dispatch({ type: "sessions_failed", message });
        }
      }
    };

    loadSessions();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      streamCloserRef.current?.();
    };
  }, []);

  const threadOptions = useMemo(
    () =>
      state.threadOrder.map((threadId) => {
        const thread = state.threads[threadId];
        return {
          value: threadId,
          label: thread?.label || threadId,
        };
      }),
    [state.threadOrder, state.threads],
  );

  const appendSystemMessage = (content: string, markdown = true) => {
    dispatch({
      type: "append_system_message",
      threadId: state.activeThreadId,
      entryId: makeId("system"),
      message: content,
      markdown,
      createdAt: Date.now(),
    });
  };

  const handleSend = async (text: string) => {
    if (state.isStreaming) {
      return;
    }

    if (text === "/skills") {
      appendSystemMessage(skillsAsMarkdown(state.skills));
      return;
    }

    if (text === "/prompt") {
      try {
        const response = await fetch(`${API_BASE_URL}/api/prompt`);
        if (!response.ok) {
          throw new Error(`Failed to load system prompt (${response.status})`);
        }
        const payload = (await response.json()) as { prompt: string };
        dispatch({ type: "prompt_loaded", prompt: payload.prompt || "" });
        appendSystemMessage(promptAsMarkdown(payload.prompt || ""));
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        appendSystemMessage(`Error: ${message}`, false);
      }
      return;
    }

    const threadId = state.activeThreadId;
    const userEntryId = makeId("user");
    const assistantEntryId = makeId("assistant");

    dispatch({
      type: "submit_user_message",
      threadId,
      message: text,
      userEntryId,
      assistantEntryId,
      createdAt: Date.now(),
    });

    streamCloserRef.current?.();
    streamCloserRef.current = openChatStream({
      apiBaseUrl: API_BASE_URL,
      message: text,
      threadId,
      onEvent: (event: AgentStreamEvent) => {
        dispatch({
          type: "stream_event",
          threadId,
          assistantEntryId,
          event,
        });

        if (event.type === "done" || event.type === "error") {
          streamCloserRef.current = null;
        }
      },
      onError: (message) => {
        dispatch({
          type: "stream_failed",
          threadId,
          assistantEntryId,
          message,
        });
        streamCloserRef.current = null;
      },
    });
  };

  const handleToggleToolExpand = useCallback(
    (assistantId: string, toolId: string) => {
      dispatch({
        type: "toggle_tool_expand",
        threadId: state.activeThreadId,
        assistantEntryId: assistantId,
        toolId,
      });
    },
    [state.activeThreadId],
  );

  const createThread = () => {
    if (state.isStreaming) {
      return;
    }
    const threadNumber = state.threadOrder.length + 1;
    const threadId = `thread-${threadNumber}`;
    dispatch({
      type: "create_thread",
      threadId,
      label: `Thread ${threadNumber}`,
    });
  };

  const handleLoadSession = useCallback(
    async (threadId: string) => {
      // 如果会话不存在，先创建
      if (!state.threads[threadId]) {
        dispatch({
          type: "create_thread",
          threadId,
          label: `Conversation ${threadId}`,
        });
      }

      // 从服务器加载会话历史
      try {
        const response = await fetch(`${API_BASE_URL}/api/sessions/${threadId}/messages`);
        if (!response.ok) {
          throw new Error(`Failed to load session messages (${response.status})`);
        }
        const payload = await response.json();
        const messages = payload.messages || [];

        // 将加载的消息添加到 timeline
        for (const msg of messages) {
          const entryId = `db-${msg.id}`;
          const createdAt = new Date(msg.created_at).getTime();

          if (msg.role === "human") {
            // 创建 UserEntry
            dispatch({
              type: "append_user_entry",
              threadId,
              entryId,
              text: msg.content || "",
              createdAt,
            });
          } else if (msg.role === "ai") {
            // 解析 tool_calls 和 tool_results
            let tools: ToolCallView[] = [];

            if (msg.tool_calls) {
              try {
                const toolCalls = JSON.parse(msg.tool_calls);
                const toolResults = msg.tool_results ? JSON.parse(msg.tool_results) : {};

                // 合并 tool_calls 和 tool_results
                tools = toolCalls.map((tc: any) => {
                  const result = toolResults[tc.id];
                  return {
                    id: tc.id,
                    name: tc.name,
                    args: tc.args || {},
                    status: result ? (result.success ? "success" : "failed") : "running",
                    result: result?.result,
                    success: result?.success,
                    expanded: false,
                  };
                });
              } catch (e) {
                console.error("Failed to parse tool_calls:", e);
              }
            }

            // 创建 AssistantEntry
            dispatch({
              type: "append_assistant_entry",
              threadId,
              entryId,
              response: msg.content || "",
              tools,
              thinking: msg.reasoning_content || "",  // 新增：传递 thinking 内容
              createdAt,
            });
          }
        }

        // 切换到该会话
        dispatch({
          type: "switch_thread",
          threadId,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        console.error("Failed to load session:", message);
        // 即使加载失败也切换会话
        dispatch({
          type: "switch_thread",
          threadId,
        });
      }
    },
    [state.threads],
  );

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div className="brand">
          <p className="eyebrow">Skills Agent</p>
          <h1>Streaming Web Console</h1>
        </div>

        <div className="thread-controls">
          <label htmlFor="thread-select">Thread</label>
          <select
            id="thread-select"
            value={state.activeThreadId}
            disabled={state.isStreaming}
            onChange={(event) =>
              dispatch({
                type: "switch_thread",
                threadId: event.target.value,
              })
            }
          >
            {threadOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <button type="button" disabled={state.isStreaming} onClick={createThread}>
            New Thread
          </button>
        </div>
      </header>

      <div className="workspace">
        <div className="left-panel">
          <div className="tab-tabs">
            <button
              className={state.leftPanelTab === "skills" ? "tab-tabs__button tab-tabs__button--active" : "tab-tabs__button"}
              onClick={() => dispatch({ type: "switch_left_panel", tab: "skills" })}
              type="button"
            >
              Skills
            </button>
            <button
              className={state.leftPanelTab === "sessions" ? "tab-tabs__button tab-tabs__button--active" : "tab-tabs__button"}
              onClick={() => dispatch({ type: "switch_left_panel", tab: "sessions" })}
              type="button"
            >
              Conversations
            </button>
          </div>

          {state.leftPanelTab === "skills" && (
            <SkillPanel
              skills={state.skills}
              activeSkillName={activeThread?.activeSkillName}
              loading={!state.skillsLoaded && !state.skillsError}
              error={state.skillsError}
            />
          )}

          {state.leftPanelTab === "sessions" && (
            <SessionPanel
              sessions={state.sessions}
              activeThreadId={state.activeThreadId}
              loading={!state.sessionsLoaded && !state.sessionsError}
              error={state.sessionsError}
              onLoadSession={handleLoadSession}
              onNewSession={createThread}
            />
          )}
        </div>

        <main className="chat-panel">
          <ChatTimeline
            entries={activeThread?.timeline || []}
            onToggleToolExpand={handleToggleToolExpand}
          />

          {state.streamError && <p className="global-error">{state.streamError}</p>}

          <Composer disabled={state.isStreaming} onSubmit={handleSend} />
        </main>
      </div>
    </div>
  );
}
