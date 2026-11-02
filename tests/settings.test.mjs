import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import ts from "typescript";

function load(name, mocks = {}) {
  const exports = {};
  const code = ts.transpileModule(readFileSync(`src/${name}.ts`, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  runInNewContext(code, { exports, ...mocks, require(id) {
    if (id in mocks) return mocks[id];
    if (id === "./settings") return load("settings");
    throw new Error(`Unexpected dependency ${id}`);
  } });
  return exports;
}

const config = { roi_x: 0.05, roi_y: 0.39, roi_width: 0.9, roi_height: 0.13,
  subtitle_left: 0.05, subtitle_top: 0.02, subtitle_width: 0.9, subtitle_height: 0.22 };

test("moving one edge preserves the opposite edge", () => {
  const { edges, changeEdge } = load("regions");
  let value = { ...config };
  for (const [edge, percent] of [["bottom", 90], ["top", 76], ["left", 20], ["right", 93]]) {
    const before = edges(value, "ocr");
    value = { ...value, ...changeEdge(value, "ocr", edge, percent) };
    for (const other of ["left", "right", "top", "bottom"]) {
      assert.equal(edges(value, "ocr")[other], other === edge ? percent : before[other]);
    }
  }
  assert.equal(value.roi_width, 0.73);
  assert.equal(value.roi_height, 0.14);
});

test("edge controls constrain crossing and subtitle height", () => {
  const { edgeLimits } = load("regions");
  assert.deepEqual(Array.from(edgeLimits(config, "ocr", "left")), [0, 94]);
  assert.deepEqual(Array.from(edgeLimits(config, "ocr", "bottom")), [40, 100]);
  assert.deepEqual(Array.from(edgeLimits(config, "subtitle", "bottom")), [7, 42]);
});

test("backend polling and panel remount cannot discard an unsaved draft", () => {
  const { SettingsDraft } = load("settings");
  const settings = new SettingsDraft();
  settings.receive(config);
  settings.edit({ roi_y: 0.76, roi_height: 0.14 });
  settings.receive(config);
  assert.equal(settings.config.roi_y, 0.76);
  assert.equal(settings.dirty, true);
  const oldRevision = settings.revision;
  settings.edit({ roi_x: 0.2 });
  settings.saved(config, oldRevision);
  assert.equal(settings.config.roi_x, 0.2);
  assert.equal(settings.dirty, true);
  settings.saved(settings.config, settings.revision);
  assert.equal(settings.dirty, false);
});

const flush = () => new Promise(resolve => setImmediate(resolve));

function harness() {
  const menu = { m_eOpenSideMenu: 2 };
  const router = { MainRunningApp: { appid: 42 },
    WindowStore: { GamepadUIMainWindowInstance: { m_MenuStore: menu } } };
  const calls = [];
  const server = { config: { ...config }, status: { running: false }, download: {} };
  let timerId = 0;
  const timers = new Map();
  let rejectSave = false;
  let gate = null;
  const copy = () => structuredClone(server);
  const store = load("store", {
    "@decky/ui": { Router: router },
    react: { useSyncExternalStore: (_subscribe, snapshot) => snapshot() },
    "@decky/api": { callable: name => async (...args) => {
      calls.push(name);
      if (name === "save_config") {
        if (gate) await gate;
        if (rejectSave) throw new Error("Regions overlap");
        server.config = structuredClone(args[0]);
        server.status.running = false;
      }
      if (name === "start") server.status.running = true;
      if (name === "stop") server.status.running = false;
      return copy();
    } },
    setTimeout: (callback, delay) => { timers.set(++timerId, { callback, delay }); return timerId; },
    clearTimeout: id => { timers.delete(id); },
  });
  const fire = async delay => {
    const [id, timer] = [...timers].find(([, value]) => value.delay === delay);
    timers.delete(id);
    await timer.callback(); await flush();
  };
  return { store, server, menu, router, calls,
    reject: value => { rejectSave = value; }, gate: value => { gate = value; },
    poll: () => fire(500), autosave: () => fire(600),
    savesPending: () => [...timers.values()].filter(x => x.delay === 600).length };
}

test("slider edits save automatically while the panel stays open", async () => {
  const h = harness();
  h.store.beginPolling(); await flush();
  await h.store.toggleCapture();
  h.store.editConfig({ roi_y: 0.7 });
  h.store.editConfig({ roi_y: 0.76, roi_height: 0.14 });
  assert.equal(h.savesPending(), 1);
  assert.equal(h.calls.filter(x => x === "save_config").length, 0);
  await h.autosave();
  assert.equal(h.calls.filter(x => x === "save_config").length, 1);
  assert.equal(h.server.config.roi_y, 0.76);
  assert.equal(h.server.status.running, true);
  assert.equal(h.store.useBackend().dirty, false);
  h.store.endPolling();
});

test("closing the panel persists edits and resumes the same game", async () => {
  const h = harness();
  h.store.beginPolling(); await flush();
  await h.store.toggleCapture();
  h.store.editConfig({ roi_y: 0.76, roi_height: 0.14 });
  h.menu.m_eOpenSideMenu = 0;
  await h.poll();
  assert.equal(h.server.config.roi_y, 0.76);
  assert.equal(h.server.status.running, true);
  h.menu.m_eOpenSideMenu = 2;
  await h.poll();
  assert.equal(h.store.useBackend().draft.roi_y, 0.76);
  assert.equal(h.store.useBackend().dirty, false);
  h.store.endPolling();
});

test("invalid saves preserve edits and do not retry every poll", async () => {
  const h = harness();
  h.store.beginPolling(); await flush();
  h.store.editConfig({ roi_y: 0.1 });
  h.reject(true);
  h.menu.m_eOpenSideMenu = 0;
  await h.poll(); await h.poll();
  assert.equal(h.calls.filter(x => x === "save_config").length, 1);
  assert.equal(h.store.useBackend().draft.roi_y, 0.1);
  assert.equal(h.store.useBackend().dirty, true);
  assert.match(h.store.useBackend().error, /Regions overlap/);
  h.reject(false);
  h.store.editConfig({ roi_y: 0.76 });
  await h.poll();
  assert.equal(h.server.config.roi_y, 0.76);
  h.store.endPolling();
});

test("an edit during save survives the response, and a game switch prevents resume", async () => {
  const h = harness();
  h.store.beginPolling(); await flush();
  await h.store.toggleCapture();
  let release;
  h.gate(new Promise(resolve => { release = resolve; }));
  h.store.editConfig({ roi_y: 0.76 });
  const saving = h.store.applyDraft();
  await flush();
  h.store.editConfig({ roi_x: 0.2 });
  h.router.MainRunningApp.appid = 99;
  release(); await saving;
  assert.equal(h.store.useBackend().draft.roi_x, 0.2);
  assert.equal(h.store.useBackend().dirty, true);
  assert.equal(h.server.status.running, false);
  h.store.endPolling();
});

test("unloading during a save cannot restart an orphaned capture", async () => {
  const h = harness();
  h.store.beginPolling(); await flush();
  await h.store.toggleCapture();
  let release;
  h.gate(new Promise(resolve => { release = resolve; }));
  h.store.editConfig({ roi_y: 0.76 });
  const saving = h.store.applyDraft();
  await flush();
  h.store.endPolling();
  release(); await saving;
  assert.equal(h.calls.filter(x => x === "start").length, 1);
  assert.equal(h.server.status.running, false);
  assert.equal(h.savesPending(), 0);
});
