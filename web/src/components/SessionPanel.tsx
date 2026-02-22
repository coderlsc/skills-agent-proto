import { memo } from "react";

import type { SessionSummary } from "../state/chatReducer";

type SessionPanelProps = {
  sessions: SessionSummary[];
  activeThreadId: string;
  loading: boolean;
  error?: string;
  onLoadSession: (threadId: string) => void;
  onNewSession: () => void;
};

export const SessionPanel = memo(function SessionPanel({
  sessions,
  activeThreadId,
  loading,
  error,
  onLoadSession,
  onNewSession,
}: SessionPanelProps) {
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <aside className="sessions-panel">
      <header className="sessions-panel__header">
        <div>
          <p className="eyebrow">History</p>
          <h2>Conversations</h2>
        </div>
        <button
          type="button"
          className="sessions-panel__new-btn"
          onClick={onNewSession}
          title="New conversation"
        >
          +
        </button>
      </header>

      {loading && <p className="sessions-panel__hint">Loading conversations...</p>}
      {error && <p className="sessions-panel__error">{error}</p>}

      {!loading && !error && sessions.length === 0 && (
        <p className="sessions-panel__hint">No conversations yet.</p>
      )}

      <ul className="sessions-list">
        {sessions.map((session) => {
          const isActive = session.thread_id === activeThreadId;
          return (
            <li
              key={session.thread_id}
              className={isActive ? "sessions-list__item sessions-list__item--active" : "sessions-list__item"}
              onClick={() => onLoadSession(session.thread_id)}
            >
              <h3 className="sessions-list__title">{session.title}</h3>
              <div className="sessions-list__meta">
                <time className="sessions-list__time">{formatDate(session.updated_at)}</time>
                {session.message_count > 0 && (
                  <span className="sessions-list__count">{session.message_count} messages</span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </aside>
  );
});
