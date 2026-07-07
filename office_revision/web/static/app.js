const projectsEl = document.querySelector("#projects");
const projectSearchEl = document.querySelector("#project-search");
const projectSortEl = document.querySelector("#project-sort");
const projectDetailEl = document.querySelector("#project-detail");
const projectActionsEl = document.querySelector("#project-actions");
const profilesEl = document.querySelector("#profiles");
const addProfileSectionEl = document.querySelector("#add-profile-section");
const profileAdvancedSettingsEl = document.querySelector("#profile-advanced-settings");
const activeWriterProfileEl = document.querySelector("#active-writer-profile");
const activeReviewerProfileEl = document.querySelector("#active-reviewer-profile");
const requirementsEl = document.querySelector("#requirements-text");
const requirementsFileEl = document.querySelector("#requirements-file");
const sourceFileEl = document.querySelector("#source-file");
const meetingNotesFileEl = document.querySelector("#meeting-notes-file");
const startButton = document.querySelector("#start-project");
const runStatusEl = document.querySelector("#run-status");
const runEventsEl = document.querySelector("#run-events");
const connectionStatusEl = document.querySelector("#connection-status");
let loadedProjects = [];
let selectedProjectId = null;
let selectedBaseVersionPath = null;
let selectedBaseVersionName = null;
let editingProfileId = null;

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
  const text = await response.text();
  let payload = {};
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (error) {
      throw new Error(response.ok ? "响应不是有效 JSON" : text);
    }
  }
  if (!response.ok) {
    throw new Error(payload.detail || text || "请求失败");
  }
  return payload;
}

function shortPath(path) {
  if (!path) {
    return "";
  }
  const normalized = String(path).replaceAll("\\", "/");
  const marker = "/projects/";
  const markerIndex = normalized.toLowerCase().indexOf(marker);
  if (markerIndex >= 0) {
    return normalized.slice(markerIndex + 1);
  }
  if (normalized.toLowerCase().startsWith("projects/")) {
    return normalized;
  }
  return normalized;
}

function artifactDisplayPath(path) {
  const display = shortPath(path);
  const outputMatch = display.match(/\/(?:outputs|dry_run_outputs)\/[^/]+\/(.+)$/);
  if (outputMatch) {
    return outputMatch[1];
  }
  const latestMatch = display.match(/\/latest\/(.+)$/);
  if (latestMatch) {
    return latestMatch[1];
  }
  return display;
}

function inputDisplayPath(path) {
  const display = shortPath(path);
  const inputMatch = display.match(/\/inputs\/(.+)$/);
  if (inputMatch) {
    return `inputs/${inputMatch[1]}`;
  }
  if (display.toLowerCase().startsWith("inputs/")) {
    return display;
  }
  return display;
}

function inputDisplayLabel(name) {
  if (name === "source_extracted.md") {
    return "初稿PDF提取文本";
  }
  if (name === "requirements.md") {
    return "修改要求";
  }
  if (name === "requirements.pdf") {
    return "修改要求PDF原文";
  }
  if (name === "source.pdf") {
    return "初稿PDF原文";
  }
  if (name === "meeting_notes.pdf") {
    return "会议纪要PDF原文";
  }
  return name;
}

function formatBytes(size) {
  const value = Number(size || 0);
  if (value >= 1024 * 1024) {
    return `${(value / 1024 / 1024).toFixed(1)} MB`;
  }
  if (value >= 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${value} B`;
}

function warningText(code) {
  if (code === "empty") {
    return "提取文本为空";
  }
  if (code === "long") {
    return "内容较长，可能增加耗时或占用更多上下文";
  }
  if (code === "very_long") {
    return "内容很长，后续建议分段处理";
  }
  return code;
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
  detailButton.dataset.projectId = project.project_id;
  detailButton.textContent = "详情";
  detailButton.addEventListener("click", () => loadProjectDetail(project.project_id));

  actions.append(detailButton);
  item.append(title, meta, actions);
  return item;
}

function projectMatchesSearch(project, query) {
  if (!query) {
    return true;
  }
  const searchable = [
    project.title,
    project.project_id,
    project.created_date,
    project.latest_status,
    project.latest_mode,
    project.latest_version ? `v${project.latest_version}` : ""
  ].filter(Boolean).join(" ").toLowerCase();
  return searchable.includes(query.toLowerCase());
}

function projectSortKey(project) {
  return `${project.created_date || ""} ${project.project_id || ""}`;
}

function sortProjects(projects) {
  const mode = projectSortEl.value;
  return [...projects].sort((left, right) => {
    if (mode === "oldest") {
      return projectSortKey(left).localeCompare(projectSortKey(right), "zh-Hans");
    }
    if (mode === "name") {
      const leftName = left.title || left.project_id || "";
      const rightName = right.title || right.project_id || "";
      return leftName.localeCompare(rightName, "zh-Hans");
    }
    return projectSortKey(right).localeCompare(projectSortKey(left), "zh-Hans");
  });
}

function renderProjectList() {
  projectsEl.innerHTML = "";
  const query = projectSearchEl.value.trim();
  const projects = sortProjects(
    loadedProjects.filter((project) => projectMatchesSearch(project, query))
  );
  for (const project of projects) {
    projectsEl.appendChild(renderProject(project));
  }
  updateProjectDetailButtons();
  if (loadedProjects.length === 0) {
    projectsEl.textContent = "暂无项目";
  } else if (projects.length === 0) {
    projectsEl.textContent = "没有匹配项目";
  }
}

async function loadProjects() {
  projectDetailEl.innerHTML = '<div class="empty-state">请选择一个项目查看详情。</div>';
  projectActionsEl.hidden = true;
  selectedProjectId = null;
  selectedBaseVersionPath = null;
  selectedBaseVersionName = null;
  try {
    const payload = await requestJson("/api/projects");
    loadedProjects = payload.projects;
    renderProjectList();
  } catch (error) {
    projectsEl.textContent = error.message;
  }
}

async function loadProjectDetail(projectId) {
  if (selectedProjectId === projectId) {
    clearProjectSelection();
    return;
  }
  try {
    const detail = await requestJson(`/api/projects/${projectId}`);
    selectedProjectId = projectId;
    selectedBaseVersionPath = null;
    selectedBaseVersionName = null;
    projectActionsEl.hidden = false;
    renderProjectDetail(detail);
    updateProjectDetailButtons();
  } catch (error) {
    projectDetailEl.textContent = error.message;
  }
}

function clearProjectSelection() {
  projectDetailEl.innerHTML = '<div class="empty-state">请选择一个项目查看详情。</div>';
  projectActionsEl.hidden = true;
  selectedProjectId = null;
  selectedBaseVersionPath = null;
  selectedBaseVersionName = null;
  updateProjectDetailButtons();
}

function updateProjectDetailButtons() {
  projectsEl.querySelectorAll("button[data-project-id]").forEach((button) => {
    button.textContent = button.dataset.projectId === selectedProjectId ? "折叠详情" : "详情";
  });
}

function renderProjectDetail(detail) {
  projectDetailEl.innerHTML = "";
  const summary = detail.summary;
  projectDetailEl.appendChild(createTextElement("h3", null, summary.title || summary.project_id));
  projectDetailEl.appendChild(
    createTextElement(
      "div",
      "item-meta",
      `${summary.project_id} | 最新 v${summary.latest_version || "-"} | ${summary.latest_status || "无状态"} | ${shortPath(summary.path)}`
    )
  );
  if (summary.path) {
    const actions = document.createElement("div");
    actions.className = "actions path-actions";
    actions.appendChild(createOpenButton(summary.path, "reveal", "打开项目位置"));
    projectDetailEl.appendChild(actions);
  }

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
    const versionMeta = createTextElement("div", "item-meta", shortPath(version.path));
    card.appendChild(versionMeta);
    const runSummary = renderRunSummary(version.run_summary);
    if (runSummary) {
      card.appendChild(runSummary);
    }
    if (version.path) {
      const actions = document.createElement("div");
      actions.className = "actions path-actions";
      actions.appendChild(createBaseVersionButton(version));
      actions.appendChild(createOpenButton(version.path, "reveal", "打开版本目录"));
      card.appendChild(actions);
    }
    card.appendChild(renderVersionArtifacts(version.artifacts));
    projectDetailEl.appendChild(card);
  }

  const inputNames = Object.keys(detail.inputs || {});
  if (inputNames.length > 0) {
    const inputs = document.createElement("div");
    inputs.className = "artifact-list";
    inputs.appendChild(createTextElement("strong", null, "输入文件"));
    for (const name of inputNames) {
      inputs.appendChild(createPathLine(inputDisplayLabel(name), detail.inputs[name], inputDisplayPath));
      const summary = detail.input_summaries ? detail.input_summaries[name] : null;
      if (summary) {
        inputs.appendChild(renderInputSummary(summary));
      }
    }
    projectDetailEl.appendChild(inputs);
  }
}

function renderInputSummary(summary) {
  const element = document.createElement("div");
  element.className = "input-summary";
  const parts = [
    `类型 ${summary.kind || "-"}`,
    `大小 ${formatBytes(summary.size_bytes)}`,
    `提取 ${summary.extracted_chars || 0} 字符`
  ];
  element.appendChild(createTextElement("span", null, parts.join(" | ")));
  const warnings = Array.isArray(summary.warnings) ? summary.warnings : [];
  for (const warning of warnings) {
    element.appendChild(createTextElement("span", "input-warning", warningText(warning)));
  }
  return element;
}

function renderRunSummary(summary) {
  if (!summary) {
    return null;
  }
  const parts = [];
  if (summary.actual_cycles !== null && summary.actual_cycles !== undefined) {
    const requested = summary.requested_cycles ?? "-";
    parts.push(`轮数 ${summary.actual_cycles}/${requested}`);
  } else if (summary.requested_cycles !== null && summary.requested_cycles !== undefined) {
    parts.push(`请求 ${summary.requested_cycles} 轮`);
  }
  if (summary.stopped_early === true) {
    parts.push("提前停止");
  } else if (summary.stopped_early === false) {
    parts.push("未提前停止");
  }
  if (summary.stop_reason) {
    parts.push(`原因 ${summary.stop_reason}`);
  }
  if (parts.length === 0) {
    return null;
  }
  return createTextElement("div", "run-summary", `运行摘要：${parts.join(" | ")}`);
}

function renderVersionArtifacts(artifacts) {
  const details = document.createElement("details");
  details.className = "version-artifacts";
  details.appendChild(createTextElement("summary", null, "版本详情"));
  details.appendChild(renderArtifacts(artifacts));
  return details;
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
      list.appendChild(createPathLine(label, path, artifactDisplayPath));
    }
  }
  if (list.childElementCount === 1) {
    list.appendChild(createTextElement("span", null, "暂无产物路径"));
  }
  return list;
}

function createPathLine(label, path, displayFormatter = shortPath) {
  const row = document.createElement("div");
  row.className = "path-row";
  row.appendChild(createTextElement("span", null, `${label}: `));
  const code = createTextElement("code", null, displayFormatter(path));
  code.title = path;
  row.appendChild(code);
  row.appendChild(createOpenButton(path, "open", "打开文件"));
  row.appendChild(createOpenButton(path, "reveal", "文件位置"));
  return row;
}

function createOpenButton(path, mode, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "secondary compact";
  button.textContent = label;
  button.addEventListener("click", () => openArtifact(path, mode));
  return button;
}

function createBaseVersionButton(version) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "secondary compact";
  button.textContent = "基于此版继续";
  button.addEventListener("click", () => chooseBaseVersion(version));
  return button;
}

function chooseBaseVersion(version) {
  selectedBaseVersionPath = version.path;
  selectedBaseVersionName = version.name;
  setText(runStatusEl, `继续基准：${version.name}`);
}

async function openArtifact(path, mode) {
  try {
    await requestJson("/api/artifacts/open", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({path, mode})
    });
  } catch (error) {
    projectDetailEl.appendChild(createTextElement("div", "status", error.message));
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

async function continueProject() {
  if (!selectedProjectId) {
    setText(runStatusEl, "请先选择项目");
    return;
  }
  try {
    if (!confirmContinueProject()) {
      setText(runStatusEl, "已取消继续修改");
      return;
    }
    const payload = await requestJson(`/api/projects/${selectedProjectId}/continue`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        feedback_text: document.querySelector("#continue-feedback-text").value,
        base_version_path: selectedBaseVersionPath,
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

function buildContinuePreview() {
  const feedback = document.querySelector("#continue-feedback-text").value.trim();
  const cycles = Number(document.querySelector("#continue-cycles").value || 2);
  const dryRun = document.querySelector("#continue-dry-run").checked;
  const baseVersion = selectedBaseVersionName || "最新版本";
  return [
    "请确认本次继续修改设置：",
    "",
    `继续项目：${selectedProjectId || "未选择"}`,
    `基准版本：${baseVersion}`,
    `反馈内容：${feedback ? "已填写" : "未填写"}`,
    `运行模式：${dryRun ? "dry-run 测试" : "真实模型"}`,
    `循环次数：${cycles}`,
    `writer 配置：${activeWriterProfileEl.textContent || "未加载"}`,
    `reviewer 配置：${activeReviewerProfileEl.textContent || "未加载"}`,
    "",
    "确认开始继续修改？"
  ].join("\n");
}

function confirmContinueProject() {
  return window.confirm(buildContinuePreview());
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
      const title = createTextElement("div", "item-title", `${profile.name} / ${profile.model}`);
      const capabilities = [
        profile.enable_search ? "search" : null,
        profile.vision ? "vision" : null,
        profile.function_calling ? "tools" : null,
        profile.json_output ? "json" : null,
        profile.structured_output ? "structured" : null
      ].filter(Boolean).join(", ") || "none";
      const meta = createTextElement(
        "div",
        "item-meta",
        `${profile.profile_id} | ${profile.provider} | ${profile.base_url || "no base_url"} | timeout ${profile.timeout_seconds}s | retries ${profile.max_retries} | ${profile.model_family} | ${capabilities}`
      );
      const actions = document.createElement("div");
      actions.className = "actions";
      const checkButton = document.createElement("button");
      checkButton.type = "button";
      checkButton.className = "secondary";
      checkButton.textContent = "检测此配置";
      checkButton.addEventListener("click", () => checkModelProfile(profile.profile_id));
      actions.appendChild(checkButton);
      actions.appendChild(createEditProfileButton(profile));
      actions.appendChild(createActivateProfileButton(profile.profile_id, "writer"));
      actions.appendChild(createActivateProfileButton(profile.profile_id, "reviewer"));
      actions.appendChild(createDeleteProfileButton(profile));
      item.append(title, meta, actions);
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
  startButton.disabled = requirementsEl.value.trim().length === 0 && requirementsFileEl.files.length === 0;
}

function inputSourceLabel(textElement, fileElement) {
  if (fileElement.files.length > 0) {
    return `文件：${fileElement.files[0].name}`;
  }
  return textElement.value.trim() ? "手动输入" : "未提供";
}

function buildStartPreview() {
  const sourceTextEl = document.querySelector("#source-text");
  const meetingNotesTextEl = document.querySelector("#meeting-notes-text");
  const cycles = Number(document.querySelector("#cycles").value || 2);
  const dryRun = document.querySelector("#dry-run").checked;
  return [
    "请确认本次运行设置：",
    "",
    `运行模式：${dryRun ? "dry-run 测试" : "真实模型"}`,
    `循环次数：${cycles}`,
    `修改要求：${inputSourceLabel(requirementsEl, requirementsFileEl)}`,
    `初稿：${inputSourceLabel(sourceTextEl, sourceFileEl)}`,
    `会议纪要：${inputSourceLabel(meetingNotesTextEl, meetingNotesFileEl)}`,
    `writer 配置：${activeWriterProfileEl.textContent || "未加载"}`,
    `reviewer 配置：${activeReviewerProfileEl.textContent || "未加载"}`,
    "",
    "确认开始运行？"
  ].join("\n");
}

function confirmStartProject() {
  return window.confirm(buildStartPreview());
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
    if (!confirmStartProject()) {
      setText(runStatusEl, "已取消运行");
      return;
    }
    const formData = new FormData();
    appendTextOrFile(formData, "requirements_text", requirementsEl, "requirements_file", requirementsFileEl);
    appendTextOrFile(formData, "source_text", document.querySelector("#source-text"), "source_file", sourceFileEl);
    appendTextOrFile(formData, "meeting_notes_text", document.querySelector("#meeting-notes-text"), "meeting_notes_file", meetingNotesFileEl);
    formData.append("cycles", String(Number(document.querySelector("#cycles").value || 2)));
    formData.append("dry_run", document.querySelector("#dry-run").checked ? "true" : "false");

    const payload = await requestJson("/api/projects/start-upload", {
      method: "POST",
      body: formData
    });
    setText(runStatusEl, "started");
    runEventsEl.innerHTML = "";
    pollRun(payload.run_id);
  } catch (error) {
    setText(runStatusEl, error.message);
  }
}

function appendTextOrFile(formData, textName, textElement, fileName, fileElement) {
  if (fileElement.files.length > 0) {
    formData.append(fileName, fileElement.files[0]);
    return;
  }
  formData.append(textName, textElement.value);
}

function createActivateProfileButton(profileId, role) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "secondary";
  button.textContent = `设为 ${role}`;
  button.addEventListener("click", () => activateModelProfile(profileId, role));
  return button;
}

function createEditProfileButton(profile) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "secondary";
  button.textContent = "编辑配置";
  button.addEventListener("click", () => editModelProfile(profile));
  return button;
}

function createDeleteProfileButton(profile) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "danger";
  button.textContent = "删除配置";
  button.addEventListener("click", () => deleteModelProfile(profile));
  return button;
}

function editModelProfile(profile) {
  editingProfileId = profile.profile_id;
  document.querySelector("#profile-name").value = profile.name || "";
  document.querySelector("#profile-model").value = profile.model || "";
  document.querySelector("#profile-provider").value = profile.provider || "";
  document.querySelector("#profile-base-url").value = profile.base_url || "";
  document.querySelector("#profile-api-key").value = profile.api_key || "";
  document.querySelector("#profile-enable-search").checked = Boolean(profile.enable_search);
  document.querySelector("#profile-vision").checked = Boolean(profile.vision);
  document.querySelector("#profile-function-calling").checked = Boolean(profile.function_calling);
  document.querySelector("#profile-json-output").checked = Boolean(profile.json_output);
  document.querySelector("#profile-structured-output").checked = Boolean(profile.structured_output);
  document.querySelector("#profile-timeout-seconds").value = profile.timeout_seconds || "";
  document.querySelector("#profile-max-retries").value = profile.max_retries ?? "";
  addProfileSectionEl.open = true;
  profileAdvancedSettingsEl.open = true;
}

async function saveModelProfile(event) {
  event.preventDefault();
  try {
    await requestJson("/api/model-profiles", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        profile_id: editingProfileId,
        name: document.querySelector("#profile-name").value,
        model: document.querySelector("#profile-model").value,
        provider: document.querySelector("#profile-provider").value,
        base_url: document.querySelector("#profile-base-url").value,
        api_key: document.querySelector("#profile-api-key").value,
        enable_search: document.querySelector("#profile-enable-search").checked,
        model_family: "unknown",
        vision: document.querySelector("#profile-vision").checked,
        function_calling: document.querySelector("#profile-function-calling").checked,
        json_output: document.querySelector("#profile-json-output").checked,
        structured_output: document.querySelector("#profile-structured-output").checked,
        timeout_seconds: Number(document.querySelector("#profile-timeout-seconds").value || 60),
        max_retries: Number(document.querySelector("#profile-max-retries").value || 1)
      })
    });
    editingProfileId = null;
    document.querySelector("#profile-form").reset();
    profileAdvancedSettingsEl.open = false;
    await loadModelProfiles();
    await loadActiveModelProfiles();
  } catch (error) {
    profilesEl.textContent = error.message;
  }
}

async function deleteModelProfile(profile) {
  const label = profile.name || profile.profile_id;
  if (!window.confirm(`确定删除模型配置“${label}”吗？`)) {
    return;
  }
  try {
    await requestJson(`/api/model-profiles/${profile.profile_id}`, {
      method: "DELETE"
    });
    connectionStatusEl.textContent = `已删除配置：${label}`;
    await loadModelProfiles();
    await loadActiveModelProfiles();
  } catch (error) {
    connectionStatusEl.textContent = error.message;
  }
}

async function loadActiveModelProfiles() {
  try {
    const [writer, reviewer] = await Promise.all([
      requestJson("/api/model-profiles/active/writer"),
      requestJson("/api/model-profiles/active/reviewer")
    ]);
    renderActiveModelProfile(activeWriterProfileEl, "writer", writer.profile);
    renderActiveModelProfile(activeReviewerProfileEl, "reviewer", reviewer.profile);
  } catch (error) {
    activeWriterProfileEl.textContent = error.message;
    activeReviewerProfileEl.textContent = error.message;
  }
}

function renderActiveModelProfile(element, role, profile) {
  if (!profile) {
    element.textContent = `${role}: 未设置`;
    return;
  }
  element.textContent = `${role}: ${profile.name} / ${profile.model} (${profile.profile_id})`;
}

async function activateModelProfile(profileId, role) {
  try {
    const payload = await requestJson(`/api/model-profiles/${profileId}/activate`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({role})
    });
    connectionStatusEl.textContent = `${payload.role}: ${payload.profile.name} / ${payload.profile.model}`;
    await loadActiveModelProfiles();
  } catch (error) {
    connectionStatusEl.textContent = error.message;
  }
}

async function checkModelProfile(profileId) {
  try {
    const payload = await requestJson(`/api/model-profiles/${profileId}/check`, {method: "POST"});
    const connection = payload.connection;
    connectionStatusEl.textContent = `${profileId}: ${connection.ok ? "OK" : "失败"} (${connection.message})`;
  } catch (error) {
    connectionStatusEl.textContent = error.message;
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
  loadActiveModelProfiles();
});
document.querySelector("#refresh-projects").addEventListener("click", loadProjects);
document.querySelector("#refresh-profiles").addEventListener("click", () => {
  loadModelProfiles();
  loadActiveModelProfiles();
});
document.querySelector("#profile-form").addEventListener("submit", saveModelProfile);
document.querySelector("#check-connections").addEventListener("click", checkConnections);
document.querySelector("#continue-project").addEventListener("click", continueProject);
document.querySelector("#decision-accept").addEventListener("click", () => applyDecision(selectedProjectId, "accept"));
document.querySelector("#decision-continue").addEventListener("click", () => applyDecision(selectedProjectId, "continue"));
document.querySelector("#decision-skip").addEventListener("click", () => applyDecision(selectedProjectId, "skip"));
document.querySelector("#decision-abandon").addEventListener("click", () => applyDecision(selectedProjectId, "abandon"));
document.querySelector("#delete-project").addEventListener("click", deleteProject);
projectSearchEl.addEventListener("input", renderProjectList);
projectSortEl.addEventListener("change", renderProjectList);
requirementsEl.addEventListener("input", updateStartButton);
requirementsFileEl.addEventListener("change", updateStartButton);
startButton.addEventListener("click", startProject);

updateStartButton();
loadProjects();
loadModelProfiles();
loadActiveModelProfiles();
