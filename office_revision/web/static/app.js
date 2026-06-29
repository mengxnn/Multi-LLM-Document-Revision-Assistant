const projectsEl = document.querySelector("#projects");
const projectDetailEl = document.querySelector("#project-detail");
const projectActionsEl = document.querySelector("#project-actions");
const profilesEl = document.querySelector("#profiles");
const requirementsEl = document.querySelector("#requirements-text");
const startButton = document.querySelector("#start-project");
const runStatusEl = document.querySelector("#run-status");
const runEventsEl = document.querySelector("#run-events");
const connectionStatusEl = document.querySelector("#connection-status");
let selectedProjectId = null;

function setText(element, text) {
  element.textContent = text;
}

function createTextElement(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) {
    element.className = className;
  }
  element.textContent = text;
  return element;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "请求失败");
  }
  return payload;
}

function showView(name) {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.view === name);
  });
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("is-active", view.id === `view-${name}`);
  });
}

function renderProject(project) {
  const item = document.createElement("div");
  item.className = "item";

  const title = document.createElement("div");
  title.className = "item-title";
  title.textContent = project.title || project.project_id;

  const meta = document.createElement("div");
  meta.className = "item-meta";
  meta.textContent = `${project.project_id} | v${project.latest_version || "-"} ${project.latest_status || ""}`;

  const actions = document.createElement("div");
  actions.className = "actions";

  const detailButton = document.createElement("button");
  detailButton.type = "button";
  detailButton.className = "secondary";
  detailButton.textContent = "详情";
  detailButton.addEventListener("click", () => loadProjectDetail(project.project_id));

  actions.append(detailButton);
  item.append(title, meta, actions);
  return item;
}

async function loadProjects() {
  projectsEl.innerHTML = "";
  projectDetailEl.innerHTML = '<div class="empty-state">请选择一个项目查看详情。</div>';
  projectActionsEl.hidden = true;
  selectedProjectId = null;
  try {
    const payload = await requestJson("/api/projects");
    for (const project of payload.projects) {
      projectsEl.appendChild(renderProject(project));
    }
    if (payload.projects.length === 0) {
      projectsEl.textContent = "暂无项目";
    }
  } catch (error) {
    projectsEl.textContent = error.message;
  }
}

async function loadProjectDetail(projectId) {
  try {
    const detail = await requestJson(`/api/projects/${projectId}`);
    selectedProjectId = projectId;
    projectActionsEl.hidden = false;
    renderProjectDetail(detail);
  } catch (error) {
    projectDetailEl.textContent = error.message;
  }
}

function renderProjectDetail(detail) {
  projectDetailEl.innerHTML = "";
  const summary = detail.summary;
  projectDetailEl.appendChild(createTextElement("h3", null, summary.title || summary.project_id));
  projectDetailEl.appendChild(
    createTextElement(
      "div",
      "item-meta",
      `${summary.project_id} | 最新 v${summary.latest_version || "-"} | ${summary.latest_status || "无状态"} | ${summary.path}`
    )
  );

  for (const version of detail.versions) {
    const card = document.createElement("article");
    card.className = "version-card";
    const latestMark = version.is_latest ? " | latest" : "";
    card.appendChild(
      createTextElement(
        "div",
        "version-title",
        `${version.name} | v${version.version || "-"} | ${version.status} | ${version.mode}${latestMark}`
      )
    );
    card.appendChild(createTextElement("div", "item-meta", version.path));
    card.appendChild(renderArtifacts(version.artifacts));
    projectDetailEl.appendChild(card);
  }

  const inputNames = Object.keys(detail.inputs || {});
  if (inputNames.length > 0) {
    const inputs = document.createElement("div");
    inputs.className = "artifact-list";
    inputs.appendChild(createTextElement("strong", null, "输入文件"));
    for (const name of inputNames) {
      inputs.appendChild(createPathLine(name, detail.inputs[name]));
    }
    projectDetailEl.appendChild(inputs);
  }
}

function renderArtifacts(artifacts) {
  const list = document.createElement("div");
  list.className = "artifact-list";
  list.appendChild(createTextElement("strong", null, "产物路径"));
  const entries = [
    ["final.docx", artifacts.final_docx],
    ["final.md", artifacts.final_md],
    ["revision summary.docx", artifacts.revision_summary_docx],
    ["revision summary.md", artifacts.revision_summary_md],
    ["final review report.docx", artifacts.final_review_report_docx],
    ["final review report.md", artifacts.final_review_report_md],
    ["run log", artifacts.run_log]
  ];
  for (const [label, path] of entries) {
    if (path) {
      list.appendChild(createPathLine(label, path));
    }
  }
  if (list.childElementCount === 1) {
    list.appendChild(createTextElement("span", null, "暂无产物路径"));
  }
  return list;
}

function createPathLine(label, path) {
  const row = document.createElement("div");
  row.appendChild(createTextElement("span", null, `${label}: `));
  row.appendChild(createTextElement("code", null, path));
  return row;
}

async function applyDecision(projectId, decision) {
  try {
    const payload = await requestJson(`/api/projects/${projectId}/decision`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({decision})
    });
    projectDetailEl.textContent = payload.message;
    await loadProjects();
  } catch (error) {
    projectDetailEl.textContent = error.message;
  }
}

async function continueProject() {
  if (!selectedProjectId) {
    setText(runStatusEl, "请先选择项目");
    return;
  }
  try {
    const payload = await requestJson(`/api/projects/${selectedProjectId}/continue`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        feedback_text: document.querySelector("#continue-feedback-text").value,
        cycles: Number(document.querySelector("#continue-cycles").value || 2),
        dry_run: document.querySelector("#continue-dry-run").checked
      })
    });
    setText(runStatusEl, "started");
    runEventsEl.innerHTML = "";
    pollRun(payload.run_id);
  } catch (error) {
    setText(runStatusEl, error.message);
  }
}

async function deleteProject() {
  if (!selectedProjectId) {
    projectDetailEl.textContent = "请先选择项目";
    return;
  }
  const permanent = document.querySelector("#delete-permanent").checked;
  try {
    const payload = await requestJson(`/api/projects/${selectedProjectId}`, {
      method: "DELETE",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({permanent})
    });
    projectDetailEl.textContent = payload.message;
    projectActionsEl.hidden = true;
    selectedProjectId = null;
    await loadProjects();
  } catch (error) {
    projectDetailEl.textContent = error.message;
  }
}

async function loadModelProfiles() {
  profilesEl.innerHTML = "";
  try {
    const payload = await requestJson("/api/model-profiles");
    for (const profile of payload.profiles) {
      const item = document.createElement("div");
      item.className = "item";
      item.textContent = `${profile.name} / ${profile.model}`;
      profilesEl.appendChild(item);
    }
    if (payload.profiles.length === 0) {
      profilesEl.textContent = "暂无模型配置";
    }
  } catch (error) {
    profilesEl.textContent = error.message;
  }
}

function updateStartButton() {
  startButton.disabled = requirementsEl.value.trim().length === 0;
}

async function pollRun(runId) {
  try {
    const payload = await requestJson(`/api/runs/${runId}`);
    setText(runStatusEl, payload.status);
    runEventsEl.innerHTML = "";
    for (const event of payload.events) {
      const item = document.createElement("li");
      item.textContent = event.display_message || event.message;
      runEventsEl.appendChild(item);
    }
    if (payload.status === "queued" || payload.status === "running") {
      window.setTimeout(() => pollRun(runId), 1000);
    } else {
      await loadProjects();
    }
  } catch (error) {
    setText(runStatusEl, error.message);
  }
}

async function startProject() {
  try {
    const payload = await requestJson("/api/projects/start", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        requirements_text: requirementsEl.value,
        source_text: document.querySelector("#source-text").value,
        meeting_notes_text: document.querySelector("#meeting-notes-text").value,
        cycles: Number(document.querySelector("#cycles").value || 2),
        dry_run: document.querySelector("#dry-run").checked
      })
    });
    setText(runStatusEl, "started");
    runEventsEl.innerHTML = "";
    pollRun(payload.run_id);
  } catch (error) {
    setText(runStatusEl, error.message);
  }
}

async function saveModelProfile(event) {
  event.preventDefault();
  try {
    await requestJson("/api/model-profiles", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        profile_id: document.querySelector("#profile-id").value,
        name: document.querySelector("#profile-name").value,
        model: document.querySelector("#profile-model").value,
        provider: document.querySelector("#profile-provider").value,
        base_url: document.querySelector("#profile-base-url").value,
        api_key: document.querySelector("#profile-api-key").value
      })
    });
    await loadModelProfiles();
  } catch (error) {
    profilesEl.textContent = error.message;
  }
}

async function checkConnections() {
  try {
    const payload = await requestJson("/api/model-connections/check", {method: "POST"});
    connectionStatusEl.textContent = payload.connections
      .map((item) => `${item.role}: ${item.ok ? "OK" : "失败"} (${item.message})`)
      .join("\n");
  } catch (error) {
    connectionStatusEl.textContent = error.message;
  }
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => showView(tab.dataset.view));
});
document.querySelector("#refresh-all").addEventListener("click", () => {
  loadProjects();
  loadModelProfiles();
});
document.querySelector("#refresh-projects").addEventListener("click", loadProjects);
document.querySelector("#refresh-profiles").addEventListener("click", loadModelProfiles);
document.querySelector("#profile-form").addEventListener("submit", saveModelProfile);
document.querySelector("#check-connections").addEventListener("click", checkConnections);
document.querySelector("#continue-project").addEventListener("click", continueProject);
document.querySelector("#decision-accept").addEventListener("click", () => applyDecision(selectedProjectId, "accept"));
document.querySelector("#decision-continue").addEventListener("click", () => applyDecision(selectedProjectId, "continue"));
document.querySelector("#decision-skip").addEventListener("click", () => applyDecision(selectedProjectId, "skip"));
document.querySelector("#decision-abandon").addEventListener("click", () => applyDecision(selectedProjectId, "abandon"));
document.querySelector("#delete-project").addEventListener("click", deleteProject);
requirementsEl.addEventListener("input", updateStartButton);
startButton.addEventListener("click", startProject);

updateStartButton();
loadProjects();
loadModelProfiles();
