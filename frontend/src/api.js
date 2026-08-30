/**
 * ADK API Service
 *
 * Talks to the ADK web server (proxied via Vite at /api).
 * The ADK server exposes:
 *   POST /apps/{app_name}/users/{user_id}/sessions  → create a session
 *   POST /run_sse                                    → send a message, get SSE stream
 */

const APP_NAME = 'cognitive_canvas';
const USER_ID = 'web_user';

/**
 * Create a new ADK session. Returns the session object.
 */
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
 * Send a message to the agent via SSE and collect events.
 *
 * @param {string} sessionId  — The ADK session ID
 * @param {string} message    — The user's text message
 * @param {function} onEvent  — Called with each parsed SSE event object
 * @returns {Promise<void>}
 */
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

  // The response is an SSE stream: lines like "data: {json}\n\n"
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Process complete SSE lines
    const lines = buffer.split('\n');
    buffer = lines.pop(); // Keep incomplete line in buffer

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('data: ')) {
        try {
          const data = JSON.parse(trimmed.slice(6));
          onEvent(data);
        } catch {
          // skip malformed events
        }
      }
    }
  }
}

/**
 * Extract the final text response from a list of ADK events.
 * The agent's response lives in events where content.role === 'model'
 * and the author matches the root_agent or a sub-agent.
 */
export function extractAgentText(events) {
  const textParts = [];
  for (const event of events) {
    if (
      event.content &&
      event.content.role === 'model' &&
      event.content.parts
    ) {
      for (const part of event.content.parts) {
        if (part.text) {
          textParts.push(part.text);
        }
      }
    }
  }
  return textParts.join('\n');
}
