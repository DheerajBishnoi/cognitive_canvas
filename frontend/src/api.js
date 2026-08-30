/**
 * ADK & Firestore API Service with Model Fallback
 *
 * Talks to the backend server (proxied via Vite at /api).
 */

const APP_NAME = 'cognitive_canvas';
const USER_ID = 'web_user';

// ─── Agent Chat with Automatic Model Fallback ───────────────────

export async function createSession() {
  const res = await fetch(`/api/apps/${APP_NAME}/users/${USER_ID}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  return res.json();
}

/**
 * Send a message with automatic quota fallback streaming.
 * 
 * @param {string} message - The user's input text
 * @param {function} onEvent - Callback for events: text chunk, fallback warning, done, error
 */
export async function sendChatMessage(message, onEvent) {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      user_id: USER_ID,
    }),
  });

  if (!res.ok) throw new Error(`Chat request failed with status: ${res.status}`);

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
          const event = JSON.parse(trimmed.slice(6));
          onEvent(event);
        } catch {
          // skip invalid json
        }
      }
    }
  }
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

export async function createTask({ title, dueDate, projectId, priority, taskType }) {
  const res = await fetch('/api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title,
      due_date: dueDate,
      project_id: projectId,
      priority: priority || 'medium',
      task_type: taskType || 'task',
    }),
  });
  if (!res.ok) throw new Error(`Failed to create task: ${res.status}`);
  return res.json();
}
