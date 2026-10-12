const conversation = document.querySelector("#conversation");
const welcome = document.querySelector("#welcome");
const messages = document.querySelector("#messages");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");
const statusBox = document.querySelector("#status");
const statusText = document.querySelector("#status-text");
const customerPicker = document.querySelector("#customer-picker");
let sessionId = null;
let busy = false;

function setStatus(message, state = "ready") {
  statusText.textContent = message;
  statusBox.classList.toggle("busy", state === "busy");
  statusBox.classList.toggle("error", state === "error");
}

function scrollToLatest() {
  conversation.scrollTop = conversation.scrollHeight;
}

function addMessage(role, content, typing = false) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;
  if (role === "assistant") {
    const avatar = document.createElement("span");
    avatar.className = "message-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "✳";
    row.append(avatar);
  }

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  if (typing) {
    bubble.innerHTML = '<span class="typing" aria-label="Assistant is thinking"><i></i><i></i><i></i></span>';
  } else {
    bubble.textContent = content;
    if (role === "assistant") bubble.innerHTML = formatAssistantText(content);
  }
  row.append(bubble);
  messages.append(row);
  scrollToLatest();
  return row;
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function formatAssistantText(text) {
  const safe = escapeHtml(text);
  const blocks = safe.split(/\n{2,}/).map((block) => {
    const lines = block.split("\n");
    if (lines.every((line) => /^\s*[-*]\s+/.test(line))) {
      const items = lines.map((line) => `<li>${inlineFormat(line.replace(/^\s*[-*]\s+/, ""))}</li>`).join("");
      return `<ul>${items}</ul>`;
    }
    if (lines.every((line) => /^\s*\d+[.)]\s+/.test(line))) {
      const items = lines.map((line) => `<li>${inlineFormat(line.replace(/^\s*\d+[.)]\s+/, ""))}</li>`).join("");
      return `<ol>${items}</ol>`;
    }
    return `<p>${lines.map(inlineFormat).join("<br>")}</p>`;
  });
  return blocks.join("");
}

function inlineFormat(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

async function startSession() {
  setStatus("Starting a secure demo session…", "busy");
  try {
    const response = await fetch("/chat/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ customer_id: customerPicker.value }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not start the chat session.");
    sessionId = data.session_id;
    setStatus(`Demo account · ${data.customer_name}`);
    input.disabled = false;
    document.querySelector("#send-button").disabled = true;
    input.placeholder = "Ask me anything about your banking...";
    input.focus();
  } catch (error) {
    sessionId = null;
    input.disabled = true;
    setStatus(error.message, "error");
  }
}

async function sendMessage(message) {
  if (!sessionId || busy || !message.trim()) return;
  busy = true;
  input.value = "";
  input.style.height = "auto";
  sendButton.disabled = true;
  welcome.hidden = true;
  addMessage("user", message);
  const typingRow = addMessage("assistant", "", true);
  setStatus("Your assistant is thinking…", "busy");

  try {
    const response = await fetch(`/chat/sessions/${encodeURIComponent(sessionId)}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await response.json();
    typingRow.remove();
    if (!response.ok) throw new Error(data.detail || "The assistant could not reply.");
    addMessage("assistant", data.reply);
    setStatus("Demo estimate · Not a real bank decision");
  } catch (error) {
    typingRow.remove();
    addMessage("assistant", error.message);
    setStatus("There was a problem. You can try again.", "error");
  } finally {
    busy = false;
    sendButton.disabled = !input.value.trim();
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(input.value);
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 132)}px`;
  sendButton.disabled = busy || !input.value.trim() || !sessionId;
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => sendMessage(button.dataset.message || ""));
});

document.querySelector("#new-chat").addEventListener("click", async () => {
  messages.replaceChildren();
  welcome.hidden = false;
  await startSession();
});

customerPicker.addEventListener("change", async () => {
  messages.replaceChildren();
  welcome.hidden = false;
  await startSession();
});
startSession();
