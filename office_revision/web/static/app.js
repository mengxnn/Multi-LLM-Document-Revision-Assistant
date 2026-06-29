const projectsEl = document.querySelector("#projects");
const projectDetailEl = document.querySelector("#project-detail");
const profilesEl = document.querySelector("#profiles");
const requirementsEl = document.querySelector("#requirements-text");
const startButton = document.querySelector("#start-project");
const runStatusEl = document.querySelector("#run-status");
const runEventsEl = document.querySelector("#run-events");
const connectionStatusEl = document.querySelector("#connection-status");

function setText(element, text) {
  element.textContent = text;
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

  const acceptButton = document.createElement("button");
  acceptButton.type = "button";
  acceptButton.textContent = "接受";
  acceptButton.addEventListener("click", () => applyDecision(project.project_id, "accept"));

  const abandonButton = document.createElement("button");
  abandonButton.type = "button";
  abandonButton.className = "danger";
  abandonButton.textContent = "放弃";
  abandonButton.addEventListener("click", () => applyDecision(project.project_id, "abandon"));

  actions.append(detailButton, acceptButton, abandonButton);
  item.append(title, meta, actions);
  return item;
}

async function loadProjects() {
  projectsEl.innerHTML = "";
  projectDetailEl.textContent = "";
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
    const lines = detail.versions.map((version) => {
      const finalMd = version.artifacts.final_md || "暂无 final.md";
      return `${version.name}: ${version.status}, ${finalMd}`;
    });
    projectDetailEl.textContent = lines.join("\n");
  } catch (error) {
    projectDetailEl.textContent = error.message;
  }
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
requirementsEl.addEventListener("input", updateStartButton);
startButton.addEventListener("click", startProject);

updateStartButton();
loadProjects();
loadModelProfiles();
