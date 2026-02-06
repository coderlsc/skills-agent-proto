import { describe, expect, it } from "vitest";

import { chatReducer, createInitialState } from "./chatReducer";

describe("chatReducer", () => {
  it("creates waiting assistant turn when user submits message", () => {
    const state = createInitialState();
    const next = chatReducer(state, {
      type: "submit_user_message",
      threadId: "thread-1",
      message: "extract this url",
      userEntryId: "user-1",
      assistantEntryId: "assistant-1",
      createdAt: 1,
    });

    const timeline = next.threads["thread-1"].timeline;
    expect(next.isStreaming).toBe(true);
    expect(timeline).toHaveLength(2);
    expect(timeline[0]).toMatchObject({ kind: "user", text: "extract this url" });
    expect(timeline[1]).toMatchObject({ kind: "assistant", phase: "waiting" });
  });

  it("applies thinking and text stream events incrementally", () => {
    const start = chatReducer(createInitialState(), {
      type: "submit_user_message",
      threadId: "thread-1",
      message: "hello",
      userEntryId: "user-1",
      assistantEntryId: "assistant-1",
      createdAt: 1,
    });

    const withThinking = chatReducer(start, {
      type: "stream_event",
      threadId: "thread-1",
      assistantEntryId: "assistant-1",
      event: { type: "thinking", content: "plan " },
    });

    const withText = chatReducer(withThinking, {
      type: "stream_event",
      threadId: "thread-1",
      assistantEntryId: "assistant-1",
      event: { type: "text", content: "answer" },
    });

    const assistant = withText.threads["thread-1"].timeline[1];
    expect(assistant).toMatchObject({
      kind: "assistant",
      phase: "responding",
      thinking: "plan ",
      response: "answer",
    });
  });

  it("deduplicates tool_call by tool id and tracks detected skill", () => {
    const start = chatReducer(createInitialState(), {
      type: "submit_user_message",
      threadId: "thread-1",
      message: "use skill",
      userEntryId: "user-1",
      assistantEntryId: "assistant-1",
      createdAt: 1,
    });

    const firstCall = chatReducer(start, {
      type: "stream_event",
      threadId: "thread-1",
      assistantEntryId: "assistant-1",
      event: {
        type: "tool_call",
        name: "load_skill",
        id: "tool-1",
        args: {},
      },
    });

    const secondCall = chatReducer(firstCall, {
      type: "stream_event",
      threadId: "thread-1",
      assistantEntryId: "assistant-1",
      event: {
        type: "tool_call",
        name: "load_skill",
        id: "tool-1",
        args: { skill_name: "news-extractor" },
      },
    });

    const assistant = secondCall.threads["thread-1"].timeline[1];
    expect(assistant.kind).toBe("assistant");
    if (assistant.kind !== "assistant") return;

    expect(assistant.tools).toHaveLength(1);
    expect(assistant.tools[0].id).toBe("tool-1");
    expect(assistant.tools[0].args).toMatchObject({ skill_name: "news-extractor" });
    expect(secondCall.threads["thread-1"].activeSkillName).toBe("news-extractor");
  });

  it("marks tool result status and transitions to done on done event", () => {
    const submitted = chatReducer(createInitialState(), {
      type: "submit_user_message",
      threadId: "thread-1",
      message: "run tool",
      userEntryId: "user-1",
      assistantEntryId: "assistant-1",
      createdAt: 1,
    });

    const withToolCall = chatReducer(submitted, {
      type: "stream_event",
      threadId: "thread-1",
      assistantEntryId: "assistant-1",
      event: {
        type: "tool_call",
        id: "tool-1",
        name: "bash",
        args: { command: "echo ok" },
      },
    });

    const withResult = chatReducer(withToolCall, {
      type: "stream_event",
      threadId: "thread-1",
      assistantEntryId: "assistant-1",
      event: {
        type: "tool_result",
        name: "bash",
        content: "[OK]\n\nok",
        success: true,
      },
    });

    const done = chatReducer(withResult, {
      type: "stream_event",
      threadId: "thread-1",
      assistantEntryId: "assistant-1",
      event: {
        type: "done",
        response: "final answer",
      },
    });

    const assistant = done.threads["thread-1"].timeline[1];
    expect(assistant.kind).toBe("assistant");
    if (assistant.kind !== "assistant") return;

    expect(assistant.tools[0].status).toBe("success");
    expect(assistant.phase).toBe("done");
    expect(assistant.response).toBe("final answer");
    expect(done.isStreaming).toBe(false);
  });

  it("records stream failure on connection errors", () => {
    const submitted = chatReducer(createInitialState(), {
      type: "submit_user_message",
      threadId: "thread-1",
      message: "hello",
      userEntryId: "user-1",
      assistantEntryId: "assistant-1",
      createdAt: 1,
    });

    const failed = chatReducer(submitted, {
      type: "stream_failed",
      threadId: "thread-1",
      assistantEntryId: "assistant-1",
      message: "SSE closed unexpectedly",
    });

    const assistant = failed.threads["thread-1"].timeline[1];
    expect(assistant.kind).toBe("assistant");
    if (assistant.kind !== "assistant") return;

    expect(assistant.phase).toBe("error");
    expect(assistant.error).toContain("SSE closed unexpectedly");
    expect(failed.isStreaming).toBe(false);
  });
});
