/**
 * ADK & Firestore API Service
 *
 * Talks to the backend server (proxied via Vite at /api).
 */

const APP_NAME = 'cognitive_canvas';
const USER_ID = 'web_user';

// ─── ADK Agent Endpoints ────────────────────────────────────────

export async function createSession() {
  const res = await fetch(`/api/apps/${APP_NAME}/users/${USER_ID}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  return res.json();
}

export async function sendMessage(sessionId, message, onEvent) {
  const body = {
    app_name: APP_NAME,
    user_id: USER_ID,
    session_id: sessionId,
    streaming: false,
    new_message: {
      role: 'user',
      parts: [{ text: message }],
    },
  };

  const res = await fetch('/api/run_sse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) throw new Error(`Agent request failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('data: ')) {
        try {
          const data = JSON.parse(trimmed.slice(6));
          onEvent(data);
        } catch { /* skip */ }
      }
    }
  }
}

export function extractAgentText(events) {
  const textParts = [];
  for (const event of events) {
    if (event.content?.role === 'model' && event.content?.parts) {
      for (const part of event.content.parts) {
        if (part.text) textParts.push(part.text);
      }
    }
  }
  return textParts.join('\n');
}

// ─── Firestore Live Data Endpoints ──────────────────────────────

export async function fetchProjects() {
  const res = await fetch('/api/projects');
  if (!res.ok) throw new Error(`Failed to fetch projects: ${res.status}`);
  const data = await res.json();
  return data.projects || [];
}

export async function fetchProjectDetail(projectId) {
  const res = await fetch(`/api/projects/${projectId}`);
  if (!res.ok) throw new Error(`Failed to fetch project detail: ${res.status}`);
  return res.json();
}

export async function fetchSchedule() {
  const res = await fetch('/api/schedule');
  if (!res.ok) throw new Error(`Failed to fetch schedule: ${res.status}`);
  const data = await res.json();
  return data.schedule || [];
}

export async function toggleTask(taskId, isDone) {
  const res = await fetch(`/api/tasks/${taskId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ done: isDone }),
  });
  if (!res.ok) throw new Error(`Failed to update task: ${res.status}`);
  return res.json();
}
