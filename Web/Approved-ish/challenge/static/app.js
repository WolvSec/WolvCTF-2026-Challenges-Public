"use strict";
const $ = (id) => document.getElementById(id);
let catalog = [];

async function api(path, method = "GET", body) {
  const options = {method, credentials: "same-origin"};
  if (body !== undefined) {
    options.headers = {"Content-Type": "application/json"};
    options.body = JSON.stringify(body);
  }
  const response = await fetch(`/api${path}`, options);
  const data = await response.json();
  $("activity").textContent = `${method} /api${path} → ${response.status}\n${JSON.stringify(data, null, 2)}`;
  if (!response.ok) throw new Error(data.message || data.error);
  return data;
}

function report(message, error = false) {
  $("notice").textContent = message;
  $("notice").className = error ? "error" : "";
}

async function action(fn) {
  try { await fn(); } catch (error) { report(error.message, true); }
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function button(text, fn, secondary = true) {
  const node = element("button", text, secondary ? "secondary" : "");
  node.type = "button";
  node.addEventListener("click", () => action(fn));
  return node;
}

function targets(selected) {
  const select = element("select");
  for (const shard of catalog) {
    const option = element("option", `${shard.id}${shard.restricted ? " (restricted)" : ""}`);
    option.value = shard.id;
    option.selected = shard.id === selected;
    select.append(option);
  }
  return select;
}

function download(name, data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: "application/json"}));
  const link = element("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function refresh() {
  const previousActivity = $("activity").textContent;
  const me = await api("/me");
  $("workspace-id").textContent = me.workspace_id;
  $("expiry").textContent = `Expires ${new Date(me.expires * 1000).toLocaleString()}`;
  $("start").hidden = true;
  $("refresh").hidden = false;
  $("desk").hidden = false;
  catalog = (await api("/shards")).shards;
  $("shards").replaceChildren();
  for (const shard of catalog) {
    const card = element("div", undefined, "card");
    card.append(element("span", shard.restricted ? "CURATOR ONLY" : "MEMBER ACCESS", `badge${shard.restricted ? " restricted" : ""}`),
      element("h3", shard.name), element("p", shard.id),
      button("Read data", async () => { await api(`/shards/${shard.id}`); report("Shard retrieved."); }));
    $("shards").append(card);
  }
  $("new-target").replaceChildren(...targets().children);
  $("new-target").value = (catalog.find((shard) => !shard.restricted) || catalog[0]).id;
  const aliases = (await api("/aliases")).aliases;
  $("aliases").replaceChildren();
  $("alias-options").replaceChildren();
  for (const alias of aliases) {
    const row = element("div", undefined, "row");
    const select = targets(alias.target_shard_id);
    select.setAttribute("aria-label", `Target for alias ${alias.id}`);
    const controls = element("div", undefined, "inline");
    controls.append(select, button("Update", async () => {
      await api(`/aliases/${alias.id}`, "PATCH", {target_shard_id: select.value});
      await refresh(); report("Alias updated.");
    }));
    row.append(element("code", alias.id), element("p", alias.locked ? "Locked for release" : "Editable"), controls);
    $("aliases").append(row);
    const label = element("label", undefined, "choice");
    const checkbox = element("input"); checkbox.type = "checkbox"; checkbox.value = alias.id;
    label.append(checkbox, document.createTextNode(`${alias.id.slice(0, 8)}… → ${alias.target_shard_id}`));
    $("alias-options").append(label);
  }
  $("manifests").replaceChildren();
  for (const manifest of (await api("/manifests")).manifests) {
    const row = element("div", undefined, "row");
    const controls = element("div", undefined, "actions");
    controls.append(
      button("Preview", async () => { await api(`/manifests/${manifest.id}/preview`); report("Preview ready."); }),
      button("Submit for review", async () => {
        await api(`/manifests/${manifest.id}/approve`, "POST"); await refresh(); report("Manifest approved.");
      }),
      button("Approval", async () => { await api(`/manifests/${manifest.id}/approval`); report("Approval record retrieved."); }),
      button("Download snapshot", async () => {
        const data = await api(`/manifests/${manifest.id}/snapshot`, "POST");
        download(`snapshot-${manifest.id}.json`, data); report("Snapshot downloaded.");
      }, false));
    row.append(element("code", manifest.id),
      element("p", `Version ${manifest.version} · ${manifest.alias_ids.length} reference(s) · ${manifest.approved ? "Approved" : "Draft"}`), controls);
    $("manifests").append(row);
  }
  $("activity").textContent = previousActivity;
}

$("start").addEventListener("click", () => action(async () => {
  await api("/session", "POST"); await refresh(); report("Workspace ready. Start with an alias from the catalog.");
}));
$("refresh").addEventListener("click", () => action(async () => { await refresh(); report("Workspace refreshed."); }));
$("alias-form").addEventListener("submit", (event) => {
  event.preventDefault(); action(async () => {
    await api("/aliases", "POST", {target_shard_id: $("new-target").value});
    await refresh(); report("Alias created.");
  });
});
$("manifest-form").addEventListener("submit", (event) => {
  event.preventDefault(); action(async () => {
    const alias_ids = Array.from($("alias-options").querySelectorAll("input:checked"), (input) => input.value);
    await api("/manifests", "POST", {alias_ids}); await refresh(); report("Manifest created. Preview or submit it for review.");
  });
});
$("backup").addEventListener("click", () => action(async () => {
  const backup = await api("/aliases/backup");
  $("backup-json").value = JSON.stringify(backup, null, 2); report("Backup exported to the editor.");
}));
$("restore").addEventListener("click", () => action(async () => {
  await api("/aliases/restore", "POST", JSON.parse($("backup-json").value));
  await refresh(); report("Alias backup restored.");
}));
refresh().then(() => report("Welcome back. Your workspace is ready.")).catch(() => {
  $("activity").textContent = "Create a workspace to begin.";
});
