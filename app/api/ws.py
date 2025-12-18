import asyncio
import os
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from starlette.websockets import WebSocketState

from app.archivist.impl_jsonl import JsonlArchivist
from app.config import settings
from app.errors import VimaniError
from app.executor.impl_mock import MockExecutor
from app.orchestrator.models import ErrorEnvelope, ErrorSeverity, ErrorSource
from app.orchestrator.service import OrchestratorService
from app.planner.impl_llm import LLMPlanner
from app.planner.impl_mock import MockPlanner

router = APIRouter()


@router.get("/test", response_class=HTMLResponse)
async def test_page(request: Request) -> str:
    return """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Vimani Agent Demo</title>
    <style>
      :root {
        color-scheme: dark;
        font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      * {
        box-sizing: border-box;
      }
      body {
        margin: 0;
        background: #050910;
        color: #f5f7fb;
        min-height: 100vh;
        padding: 24px;
      }
      h1,
      h2,
      h3,
      h4 {
        margin: 0 0 12px;
        font-weight: 600;
      }
      .app {
        max-width: 1200px;
        margin: 0 auto;
        display: grid;
        grid-template-columns: 1fr 360px;
        gap: 24px;
      }
      .card {
        background: #0f1726;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35);
      }
      .card h3 {
        font-size: 1.1rem;
        letter-spacing: 0.01em;
      }
      .left-column {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .chat-header {
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin-bottom: 12px;
      }
      .control-row {
        display: flex;
        gap: 12px;
      }
      label {
        font-size: 0.85rem;
        opacity: 0.8;
        display: flex;
        flex-direction: column;
        gap: 6px;
        flex: 1;
      }
      input,
      textarea {
        border: 1px solid rgba(255, 255, 255, 0.15);
        background: rgba(255, 255, 255, 0.04);
        color: #f5f7fb;
        border-radius: 10px;
        padding: 10px 12px;
        font-size: 0.95rem;
        width: 100%;
      }
      textarea {
        min-height: 80px;
        resize: vertical;
      }
      button {
        border: none;
        border-radius: 10px;
        padding: 10px 16px;
        font-weight: 600;
        cursor: pointer;
        transition: opacity 0.2s ease;
      }
      button:disabled {
        opacity: 0.4;
        cursor: not-allowed;
      }
      .primary {
        background: linear-gradient(135deg, #66d1ff, #7c5dff);
        color: #050910;
      }
      .ghost {
        background: rgba(255, 255, 255, 0.08);
        color: #f5f7fb;
      }
      .chat-window {
        background: rgba(5, 9, 16, 0.5);
        border-radius: 18px;
        padding: 16px;
        min-height: 520px;
        max-height: 520px;
        overflow: hidden;
        display: flex;
        flex-direction: column;
      }
      .chat-messages {
        flex: 1;
        overflow-y: auto;
        padding-right: 8px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .bubble {
        max-width: 82%;
        padding: 12px 16px;
        border-radius: 16px;
        font-size: 0.95rem;
        line-height: 1.4;
        white-space: pre-wrap;
      }
      .bubble.assistant {
        align-self: flex-start;
        background: rgba(102, 209, 255, 0.15);
        border-bottom-left-radius: 4px;
      }
      .bubble.user {
        align-self: flex-end;
        background: rgba(124, 93, 255, 0.4);
        border-bottom-right-radius: 4px;
      }
      .composer {
        margin-top: 16px;
        display: flex;
        gap: 12px;
      }
      .composer textarea {
        flex: 1;
        min-height: 60px;
        max-height: 120px;
      }
      .planner-form {
        margin-top: 12px;
        padding: 14px;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.05);
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      .right-column {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .progress-list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 10px;
        max-height: 260px;
        overflow-y: auto;
      }
      .progress-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 12px;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.04);
        font-size: 0.9rem;
      }
      .progress-item .meta {
        opacity: 0.6;
        font-size: 0.8rem;
      }
      .status-icon {
        margin-right: 8px;
        font-size: 1.1rem;
      }
      .decision-panel {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .decision-buttons {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.08);
        font-size: 0.8rem;
      }
      .event-log {
        font-family: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
        font-size: 0.8rem;
        max-height: 160px;
        overflow-y: auto;
        background: rgba(0, 0, 0, 0.35);
        padding: 12px;
        border-radius: 12px;
        line-height: 1.5;
      }
      .hidden {
        display: none !important;
      }
      .result-card {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .result-card span {
        opacity: 0.85;
        font-size: 0.9rem;
      }
      @media (max-width: 960px) {
        .app {
          grid-template-columns: 1fr;
        }
      }
    </style>
  </head>
  <body>
    <div class="app">
      <section class="left-column">
        <div id="start-card" class="card">
          <h3>Start a run</h3>
          <div class="chat-header">
            <label>
              Intent
              <input id="intent-input" placeholder="e.g. Create work plan for launch" />
            </label>
            <label>
              Fail on step (demo)
              <input id="fail-step-input" placeholder="Optional step id" />
            </label>
            <button id="start-btn" class="primary">Start Run</button>
          </div>
        </div>
        <div class="card">
          <div class="chat-window">
            <div class="chat-messages" id="chat-messages"></div>
            <div id="planner-form" class="planner-form hidden">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <strong>Planner needs more info</strong>
                <button class="ghost" id="planner-hide-btn">Hide</button>
              </div>
              <div id="planner-fields"></div>
              <button class="primary" id="planner-submit">Continue</button>
            </div>
            <div class="composer hidden" id="composer">
              <textarea id="user-input" placeholder="Respond or provide context..."></textarea>
              <button class="primary" id="send-btn">Send</button>
            </div>
          </div>
        </div>
      </section>
      <section class="right-column">
        <div class="card">
          <h3>Progress</h3>
          <ul id="progress-list" class="progress-list">
            <li class="progress-item" style="justify-content:center; opacity:0.6;">Awaiting plan...</li>
          </ul>
        </div>
        <div id="decision-card" class="card hidden">
          <div class="decision-panel">
            <div class="badge">Paused — choose what to do</div>
            <div class="decision-buttons">
              <button class="primary" data-decision="RETRY_STEP">Retry step</button>
              <button class="ghost" data-decision="SKIP_STEP">Skip step</button>
              <button class="ghost" data-decision="SKIP_DEPENDENTS">Skip dependents</button>
              <button class="ghost" data-decision="REPLAN">Replan</button>
              <button class="ghost" data-decision="ABORT_RUN">Abort run</button>
            </div>
          </div>
        </div>
        <div id="result-card" class="card hidden">
          <div class="result-card">
            <h3>Result</h3>
            <span id="result-summary">Run completed.</span>
            <span id="result-archive">Run archived ✅</span>
          </div>
        </div>
        <div class="card">
          <h3>Event log</h3>
          <div id="event-log" class="event-log"></div>
        </div>
      </section>
    </div>
    <script>
      (() => {
        const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
        const wsUrl = `${wsProtocol}://${window.location.host}/ws`;

        const state = {
          ws: null,
          runId: null,
          phase: "IDLE",
          messages: [],
          execEvents: [],
          steps: {},
          stepOrder: [],
          paused: null,
          final: null,
        };

        const elements = {
          startCard: document.getElementById("start-card"),
          intent: document.getElementById("intent-input"),
          failStep: document.getElementById("fail-step-input"),
          startBtn: document.getElementById("start-btn"),
          chatMessages: document.getElementById("chat-messages"),
          composer: document.getElementById("composer"),
          userInput: document.getElementById("user-input"),
          sendBtn: document.getElementById("send-btn"),
          plannerForm: document.getElementById("planner-form"),
          plannerHide: document.getElementById("planner-hide-btn"),
          plannerSubmit: document.getElementById("planner-submit"),
          plannerFields: document.getElementById("planner-fields"),
          progressList: document.getElementById("progress-list"),
          decisionCard: document.getElementById("decision-card"),
          decisionButtons: document.querySelectorAll("#decision-card button[data-decision]"),
          eventLog: document.getElementById("event-log"),
          resultCard: document.getElementById("result-card"),
          resultSummary: document.getElementById("result-summary"),
          resultArchive: document.getElementById("result-archive"),
        };

        const statusIcons = {
          PENDING: "…",
          RUNNING: "⏳",
          DONE: "✅",
          FAILED: "❌",
          PAUSED: "⏸",
          SKIPPED: "⏭",
        };

        const logLines = [];

        function appendLog(line) {
          const timestamp = new Date().toLocaleTimeString();
          logLines.push(`[${timestamp}] ${line}`);
          while (logLines.length > 40) logLines.shift();
          elements.eventLog.textContent = logLines.join("\\n");
          elements.eventLog.scrollTop = elements.eventLog.scrollHeight;
        }

        function togglePlannerForm(visible) {
          elements.plannerForm.classList.toggle("hidden", !visible);
        }

        function toggleComposer(visible) {
          elements.composer.classList.toggle("hidden", !visible);
        }

        function renderChat() {
          const container = elements.chatMessages;
          container.innerHTML = "";
          state.messages.forEach((msg) => {
            const bubble = document.createElement("div");
            bubble.className = `bubble ${msg.role === "user" ? "user" : "assistant"}`;
            bubble.textContent = msg.text;
            container.appendChild(bubble);
          });
          container.scrollTop = container.scrollHeight;
          const shouldShowComposer =
            Boolean(state.runId) &&
            state.phase === "PLANNING" &&
            elements.plannerForm.classList.contains("hidden");

          toggleComposer(shouldShowComposer);

          elements.startCard.classList.toggle("hidden", Boolean(state.runId));
        }

        function renderSteps() {
          const list = elements.progressList;
          list.innerHTML = "";
          if (!state.stepOrder.length) {
            const li = document.createElement("li");
            li.className = "progress-item";
            li.style.justifyContent = "center";
            li.style.opacity = "0.65";
            li.textContent = "Awaiting plan...";
            list.appendChild(li);
            return;
          }
          state.stepOrder
            .map((id) => state.steps[id])
            .filter(Boolean)
            .sort((a, b) => a.order - b.order)
            .forEach((step) => {
              const li = document.createElement("li");
              li.className = "progress-item";
              const icon = document.createElement("span");
              icon.className = "status-icon";
              icon.textContent = statusIcons[step.status] || "…";
              const info = document.createElement("div");
              info.style.flex = "1";
              info.innerHTML = `<strong>${step.id}</strong><div class="meta">${step.op}</div>`;
              li.appendChild(icon);
              li.appendChild(info);
              list.appendChild(li);
            });
        }

                 

        function renderDecision() {
          if (!state.paused) {
            elements.decisionCard.classList.add("hidden");
           return;
          }

          elements.decisionCard.classList.remove("hidden");

          const error = state.paused.error;
          if (error?.message) {
            appendLog(`Paused: ${error.message}`);
          }
        }

        function renderFinal() {
          if (state.final) {
            elements.resultCard.classList.remove("hidden");
            const status = state.final.status || "SUCCESS";
            const summary = state.final.summary || "Run completed.";
            elements.resultSummary.textContent = `${summary} (status: ${status})`;
            elements.resultArchive.textContent = state.final.archive_ref
              ? `Run archived ✅  archive_ref: ${state.final.archive_ref}`
              : "Run archived ✅";
          } else {
            elements.resultCard.classList.add("hidden");
          }
        }

        function render() {
          renderChat();
          renderSteps();
          renderDecision();
          renderFinal();
        }

        function addMessage(role, text) {
          if (!text) return;
          state.messages.push({ role, text });
          render();
        }

        function setPlanSteps(plan) {
          if (!plan || !Array.isArray(plan.steps)) return;
          state.steps = {};
          state.stepOrder = [];
          plan.steps.forEach((step, index) => {
            const id = step.step_id || `step_${index + 1}`;
            state.stepOrder.push(id);
            state.steps[id] = {
              id,
              op: step.op_id || "operation",
              status: "PENDING",
              dependsOn: Array.isArray(step.depends_on) ? step.depends_on : [],
              order: index,
            };
          });
          render();
        }

        function updateStepStatus(stepId, status) {
          if (!state.steps[stepId]) return;
          state.steps[stepId].status = status;
          render();
        }

        function markDependentsSkipped(stepId) {
          Object.values(state.steps).forEach((step) => {
            if (step.dependsOn.includes(stepId)) {
              step.status = "SKIPPED";
            }
          });
          render();
        }

        function normalizeMessageText(msg) {
          if (!msg) return "";
          return (
            msg.text ||
            msg.message ||
            (typeof msg === "string" ? msg : JSON.stringify(msg, null, 2))
          );
        }

        function normalizeExecEvent(msg) {
          if (!msg) return null;
          if (msg.event && msg.event.type) return msg.event;
          if (msg.event && msg.event.event) return msg.event.event;
          if (msg.type && msg.step_id !== undefined) return msg;
          return msg.event || msg;
        }

        function renderPlannerForm(message) {
          const container = elements.plannerFields;
          if (!container) return;
          container.innerHTML = "";

          const fields = Array.isArray(message.fields) ? message.fields : [];

          fields.forEach((field) => {
            if (!field || !field.key) return;

            const wrapper = document.createElement("label");
            wrapper.dataset.key = field.key;
            wrapper.style.display = "flex";
            wrapper.style.flexDirection = "column";
            wrapper.style.gap = "6px";

            const labelEl = document.createElement("span");
            const requiredMark = field.required ? " *" : "";
            labelEl.textContent = `${field.label || field.key}${requiredMark}`;
            wrapper.appendChild(labelEl);

            const fieldType = (field.type || "text").toLowerCase();
            let inputEl;

            if (fieldType === "textarea") {
              inputEl = document.createElement("textarea");
            } else if (fieldType === "select") {
              inputEl = document.createElement("select");
              const options = Array.isArray(field.options) ? field.options : [];
              options.forEach((opt) => {
                const optionEl = document.createElement("option");
                let value;
                let label;
                if (typeof opt === "string") {
                  value = opt;
                  label = opt;
                } else {
                  value = opt.value ?? opt.id ?? opt.label ?? "";
                  label = opt.label ?? String(value);
                }
                optionEl.value = value;
                optionEl.textContent = label;
                inputEl.appendChild(optionEl);
              });
            } else {
              inputEl = document.createElement("input");
              inputEl.type = fieldType === "number" ? "number" : "text";
            }

            inputEl.name = field.key;
            if (field.placeholder) {
              inputEl.placeholder = field.placeholder;
            }
            if (field.required) {
              inputEl.required = true;
            }

            wrapper.appendChild(inputEl);
            container.appendChild(wrapper);
          });
        }

        function renderDynamicForm(text, fields) {
          const container = elements.plannerFields;
          if (!container) return;
          container.innerHTML = "";

          const fieldsArray = Array.isArray(fields) ? fields : [];

          fieldsArray.forEach((field) => {
            if (!field || !field.key) return;

            const wrapper = document.createElement("label");
            wrapper.dataset.key = field.key;
            wrapper.style.display = "flex";
            wrapper.style.flexDirection = "column";
            wrapper.style.gap = "6px";

            const labelEl = document.createElement("span");
            const requiredMark = field.required ? " *" : "";
            labelEl.textContent = `${field.label || field.key}${requiredMark}`;
            wrapper.appendChild(labelEl);

            const fieldType = (field.type || "text").toLowerCase();
            let inputEl;

            if (fieldType === "textarea") {
              inputEl = document.createElement("textarea");
            } else if (fieldType === "select") {
              inputEl = document.createElement("select");
              const options = Array.isArray(field.options) ? field.options : [];
              options.forEach((opt) => {
                const optionEl = document.createElement("option");
                let value;
                let label;
                if (typeof opt === "string") {
                  value = opt;
                  label = opt;
                } else {
                  value = opt.value ?? opt.id ?? opt.label ?? "";
                  label = opt.label ?? String(value);
                }
                optionEl.value = value;
                optionEl.textContent = label;
                inputEl.appendChild(optionEl);
              });
            } else {
              inputEl = document.createElement("input");
              inputEl.type = fieldType === "number" ? "number" : "text";
            }

            inputEl.name = field.key;
            if (field.placeholder) {
              inputEl.placeholder = field.placeholder;
            }
            if (field.required) {
              inputEl.required = true;
            }

            wrapper.appendChild(inputEl);
            container.appendChild(wrapper);
          });
        }

        function handlePlannerMessage(msg) {
          if (msg.message && msg.message.type === "form") {
            renderDynamicForm(msg.message.text, msg.message.fields);
            togglePlannerForm(true);
            return;
          }
          
          // If msg.message exists but we're not handling it as a form, log it to catch payload mismatches
          if (msg.message && msg.message.type !== "form") {
            console.log("Unhandled planner message:", msg.message);
          }
          
          const messageText = msg.message?.text || JSON.stringify(msg.message || msg, null, 2);
          addMessage("assistant", messageText);
        }

        function sendUserMessage(text) {
          const trimmed = (text || elements.userInput.value).trim();
          if (!trimmed || !state.runId) return;
          state.ws?.send(
            JSON.stringify({
              type: "USER_MESSAGE",
              run_id: state.runId,
              text: trimmed,
            })
          );
          addMessage("user", trimmed);
          elements.userInput.value = "";
          togglePlannerForm(false);
        }

        function sendDecision(decision) {
          if (!state.runId || !state.paused) return;
          state.ws?.send(
            JSON.stringify({
              type: "STEP_DECISION",
              run_id: state.runId,
              step_id: state.paused.step_id,
              decision,
            })
          );
          appendLog(`Decision sent: ${decision}`);
          if (decision === "SKIP_STEP") {
            updateStepStatus(state.paused.step_id, "SKIPPED");
          } else if (decision === "SKIP_DEPENDENTS") {
            updateStepStatus(state.paused.step_id, "SKIPPED");
            markDependentsSkipped(state.paused.step_id);
          } else if (decision === "RETRY_STEP") {
            updateStepStatus(state.paused.step_id, "PENDING");
          }
          state.paused = null;
          state.phase = "EXECUTING";
          render();
        }

        elements.decisionButtons.forEach((btn) => {
          btn.addEventListener("click", () => sendDecision(btn.dataset.decision));
        });

        elements.sendBtn.addEventListener("click", () => sendUserMessage());
        elements.userInput.addEventListener("keydown", (evt) => {
          if (evt.key === "Enter" && evt.metaKey) {
            sendUserMessage();
          }
        });

        elements.startBtn.addEventListener("click", () => {
          const intent = elements.intent.value.trim();
          if (!intent) {
            elements.intent.focus();
            return;
          }
          const payload = {
            type: "START_RUN",
            tool_key: "clickup",
            intent,
            user_context: {},
          };
          const fail = elements.failStep.value.trim();
          if (fail) {
            payload.fail_on_step_id = fail;
          }
          state.phase = "PLANNING";
          state.ws?.send(JSON.stringify(payload));
          appendLog("START_RUN sent.");
          elements.startBtn.disabled = true;
          render();
        });

        elements.plannerSubmit.addEventListener("click", () => {
          if (!state.runId || !elements.plannerFields) return;

          const values = {};
          const fieldWrappers = elements.plannerFields.querySelectorAll("label[data-key]");

          fieldWrappers.forEach((wrapper) => {
            const key = wrapper.dataset.key;
            if (!key) return;
            const inputEl = wrapper.querySelector("input, select, textarea");
            if (!inputEl) return;

            let value = inputEl.value;
            if (inputEl.tagName === "INPUT" && inputEl.type === "number") {
              value = value === "" ? null : Number(value);
            }
            values[key] = value;
          });

          state.ws?.send(
            JSON.stringify({
              type: "USER_MESSAGE",
              run_id: state.runId,
              text: "",
              metadata: {
                form_response: values,
              },
            })
          );

          togglePlannerForm(false);
        });
        elements.plannerHide.addEventListener("click", () => togglePlannerForm(false));

        const ws = new WebSocket(wsUrl);
        state.ws = ws;

        ws.addEventListener("open", () => appendLog("Connected to orchestrator."));
        ws.addEventListener("close", () => appendLog("Connection closed."));

        ws.addEventListener("message", (event) => {
          const msg = JSON.parse(event.data);
          switch (msg.type) {
            case "RUN_CREATED":
              state.runId = msg.run_id;
              state.phase = "PLANNING";
              appendLog("Run created: " + state.runId);
              render();
              break;
            case "PLANNER_MESSAGE":
              console.log("PLANNER_MESSAGE raw:", msg);
              console.log("PLANNER_MESSAGE message:", msg.message);
              handlePlannerMessage(msg);
              break;
            case "PLAN_ACCEPTED":
              if (msg.plan) setPlanSteps(msg.plan);
              state.phase = "EXECUTING";
              appendLog("Plan accepted.");
              render();
              break;
            case "EXEC_EVENT": {
              const eventPayload = normalizeExecEvent(msg);
              if (!eventPayload || eventPayload.type === "RUN_SUMMARY") break;
              state.execEvents.push(eventPayload);
              if (eventPayload.type === "STEP_STARTED") {
                updateStepStatus(eventPayload.step_id, "RUNNING");
              } else if (eventPayload.type === "STEP_DONE") {
                updateStepStatus(eventPayload.step_id, "DONE");
              } else if (eventPayload.type === "STEP_FAILED") {
                updateStepStatus(eventPayload.step_id, "FAILED");
              }
              appendLog(
                `Event: ${eventPayload.type}${
                  eventPayload.step_id ? " (" + eventPayload.step_id + ")" : ""
                }`
              );
              break;
            }
            case "NEED_STEP_DECISION":
              state.phase = "PAUSED";
              state.paused = { step_id: msg.step_id, error: msg.error };
              updateStepStatus(msg.step_id, "PAUSED");
              appendLog("Awaiting decision for " + msg.step_id);
              render();
              break;
            case "RUN_DONE":
              state.phase = "DONE";
              state.paused = null;
              state.final = {
                status: msg.status || msg.result?.status,
                summary: msg.summary || "Run completed.",
                archive_ref: msg.archive_ref || msg.result?.archive_ref,
              };
              elements.startBtn.disabled = false;
              toggleComposer(false);
              togglePlannerForm(false);
              appendLog("Run completed.");
              render();
              break;
            case "RUN_ERROR":
              state.phase = "DONE";
              state.paused = null;
              const errText = msg.error?.message || "Unknown error.";
              addMessage("assistant", "Something went wrong: " + errText);
              appendLog("Error: " + errText);
              render();
              break;
            case "PLAN_INVALID":
              appendLog("Plan invalid: " + JSON.stringify(msg.errors || []));
              break;
            default:
              appendLog("Event: " + msg.type);
          }
        });

        render();
      })();
    </script>
  </body>
</html>
"""


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    user_messages: asyncio.Queue = asyncio.Queue()
    step_decisions: asyncio.Queue = asyncio.Queue()

    async def send_event(payload: Dict[str, Any]) -> None:
        if payload.get("type") == "PLANNER_MESSAGE":
            print("PLANNER_MESSAGE:", payload)
        await websocket.send_json(payload)

    async def wait_for_user_message() -> Any:
        return await user_messages.get()

    async def wait_for_step_decision() -> Any:
        """Wait for the next step decision from the queue."""
        # Note: This returns the next decision regardless of run_id/step_id.
        # The orchestrator should filter by step_id after receiving it.
        return await step_decisions.get()

    orchestrator: OrchestratorService | None = None
    run_task: asyncio.Task | None = None

    def make_error_envelope(
        code: str,
        message: str,
        *,
        source: ErrorSource = ErrorSource.ORCHESTRATOR,
        severity: ErrorSeverity = ErrorSeverity.RUN,
        step_id: str | None = None,
        retryable: bool = False,
    ) -> Dict[str, Any]:
        return ErrorEnvelope(
            code=code,
            message=message,
            source=source,
            severity=severity,
            step_id=step_id,
            retryable=retryable,
        ).model_dump()

    def resolve_planner() -> Any:
        planner_mode = (os.getenv("VIMANI_PLANNER") or "").strip().lower()
        if planner_mode == "llm":
            return LLMPlanner()
        return MockPlanner()

    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")

            if msg_type == "START_RUN":
                tool_key = message.get("tool_key")
                intent = message.get("intent")
                user_context = dict(message.get("user_context") or {})
                fail_on_step_id = message.get("fail_on_step_id")

                if fail_on_step_id is not None:
                    user_context["fail_on_step_id"] = fail_on_step_id

                # Emit debug info before constructing planner to confirm env vars at runtime.
                planner_mode = (os.getenv("VIMANI_PLANNER") or "").strip().lower()
                planner_type = "LLM" if planner_mode == "llm" else "Mock"
                has_api_key = bool(os.getenv("OPENAI_API_KEY"))
                await send_event({
                    "type": "DEBUG",
                    "message": f"START_RUN: OPENAI_API_KEY present={has_api_key}, planner={planner_type}"
                })

                try:
                    planner_impl = resolve_planner()
                except Exception as exc:
                    await websocket.send_json(
                        {
                            "type": "RUN_ERROR",
                            "error": make_error_envelope(
                                code="PLANNER_INIT_FAILED",
                                message=str(exc),
                            ),
                        }
                    )
                    continue

                # Emit a debug event so we can confirm the active planner at runtime.
                if isinstance(planner_impl, LLMPlanner):
                    debug_message = f"planner=LLMPlanner model={settings.planner_model}"
                else:
                    debug_message = "planner=MockPlanner"
                await send_event({"type": "DEBUG", "message": debug_message})

                orchestrator = OrchestratorService(
                    planner=planner_impl,
                    executor=MockExecutor(),
                    archivist=JsonlArchivist(),
                )
                
                async def handle_run_task_done(task: asyncio.Task) -> None:
                    """Handle run task completion and catch any exceptions."""
                    try:
                        # This will raise if the task raised an exception
                        task.result()
                    except VimaniError as ve:
                        # Structured error from orchestrator
                        envelope = ve.envelope
                        error_dict = envelope.model_dump() if hasattr(envelope, "model_dump") else envelope
                        try:
                            await websocket.send_json({
                                "type": "RUN_ERROR",
                                "error": error_dict,
                            })
                        except Exception:
                            # Websocket may be closed, ignore
                            pass
                    except Exception as exc:
                        # Any other exception - wrap in ErrorEnvelope
                        try:
                            await websocket.send_json({
                                "type": "RUN_ERROR",
                                "error": make_error_envelope(
                                    code="RUN_TASK_FAILED",
                                    message=f"Run task crashed: {exc}",
                                    source=ErrorSource.ORCHESTRATOR,
                                    severity=ErrorSeverity.RUN,
                                    retryable=False,
                                ),
                            })
                        except Exception:
                            # Websocket may be closed, ignore
                            pass

                run_task = asyncio.create_task(
                    orchestrator.start_run(
                        tool_key=tool_key,
                        intent=intent,
                        user_context=user_context,
                        send_event=send_event,
                        wait_for_user_message=wait_for_user_message,
                        wait_for_step_decision=wait_for_step_decision,
                    )
                )
                run_task.add_done_callback(lambda task: asyncio.create_task(handle_run_task_done(task)))
            elif msg_type == "USER_MESSAGE":
                user_payload = {
                    "role": "user",
                    "type": "text",
                    "text": message.get("text", ""),
                    "metadata": message.get("metadata") if "metadata" in message else None,
                }
                await user_messages.put(user_payload)
            elif msg_type == "STEP_DECISION":
                await step_decisions.put(message)
            else:
                await websocket.send_json(
                    {
                        "type": "RUN_ERROR",
                        "error": make_error_envelope(
                            code="UNKNOWN_MESSAGE",
                            message="Unknown message type",
                        ),
                    }
                )
    except WebSocketDisconnect:
        if run_task:
            run_task.cancel()
        return
    except VimaniError as ve:
        envelope = ve.envelope
        payload = envelope.model_dump() if hasattr(envelope, "model_dump") else envelope
        await websocket.send_json(
            {
                "type": "RUN_ERROR",
                "error": payload,
            }
        )
        return
    except Exception as exc:  # pragma: no cover - guardrail for WS lifecycle
        await websocket.send_json(
            {
                "type": "RUN_ERROR",
                "error": make_error_envelope(
                    code="WS_FAILURE",
                    message=str(exc),
                ),
            }
        )
    finally:
        if run_task:
            run_task.cancel()
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
