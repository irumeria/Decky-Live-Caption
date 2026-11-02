import { callable } from "@decky/api";
import { Router } from "@decky/ui";
import { useSyncExternalStore } from "react";
import type { Config, State } from "./types";
import { SettingsDraft } from "./settings";

const getState = callable<[], State>("get_state");
const startCapture = callable<[], State>("start");
const stopCapture = callable<[], State>("stop");
const configure = callable<[Config], State>("save_config");
const setMenuOpen = callable<[boolean], State>("set_menu_open");
const downloadModels = callable<[], State>("download_models");
const cancelDownload = callable<[], State>("cancel_download");
const settings = new SettingsDraft();
let saving = false;
let settingsMessage = "";
let failedRevision: number | null = null;
let snapshot: { state: State | null; error: string; draft: Config | null;
  dirty: boolean; saving: boolean; settingsMessage: string } = {
  state: null, error: "", draft: null, dirty: false, saving: false, settingsMessage: "",
};
const listeners = new Set<() => void>();
let disposed = false;
let timer: ReturnType<typeof setTimeout> | undefined;
let saveTimer: ReturnType<typeof setTimeout> | undefined;
let version = 0;
let ownerApp: string | null = null;
let actionError = "";
let lastMenuOpen: boolean | null = null;

function menuOpen(): boolean {
  // The composed game capture includes the QAM and Steam menu. Do not translate those panels.
  const router = Router as unknown as { WindowStore: { GamepadUIMainWindowInstance?: {
    m_MenuStore?: { m_eOpenSideMenu?: number }
  } } };
  const menu = router.WindowStore.GamepadUIMainWindowInstance?.m_MenuStore?.m_eOpenSideMenu;
  if (typeof menu !== "number") throw new Error("无法读取 Steam 菜单状态，请更新插件适配。");
  return menu !== 0;
}

function appId(): string | null {
  const id = Router.MainRunningApp?.appid;
  return id == null ? null : String(id);
}

function update(state: State | null, error = actionError) {
  if (disposed) return;
  if (state) settings.receive(state.config);
  snapshot = { state, error, draft: settings.config, dirty: settings.dirty, saving, settingsMessage };
  listeners.forEach((listener) => listener());
}

export function useBackend() {
  return useSyncExternalStore((listener) => {
    listeners.add(listener);
    return () => { listeners.delete(listener); };
  }, () => snapshot);
}

export function editConfig(patch: Partial<Config>) {
  settings.edit(patch);
  actionError = "";
  settingsMessage = "待自动保存…";
  update(snapshot.state);
  scheduleSave();
}

function scheduleSave() {
  clearTimeout(saveTimer);
  // Slider drags emit many values. Apply the final value without restarting OCR for every pixel.
  saveTimer = setTimeout(() => { void applyDraft(); }, 600);
}

export async function applyDraft() {
  if (saving || !settings.dirty || !settings.config) return;
  clearTimeout(saveTimer);
  const request = ++version;
  const revision = settings.revision;
  const config = settings.config;
  const resumeApp = snapshot.state?.status.running ? ownerApp : null;
  saving = true;
  actionError = "";
  settingsMessage = "正在保存并应用…";
  update(snapshot.state);
  try {
    let state = await configure(config);
    // A plugin unload can complete while the backend is saving. Do not revive its worker.
    if (disposed || request !== version) return;
    settings.saved(state.config, revision);
    settingsMessage = settings.dirty ? "仍有新修改待保存" : "已保存并应用";
    if (version === request) update(state);
    // Saving stops the worker. Resume only the same game session, never another game.
    if (resumeApp !== null && appId() === resumeApp) {
      lastMenuOpen = menuOpen();
      await setMenuOpen(lastMenuOpen);
      if (disposed || request !== version) return;
      state = await startCapture();
      if (disposed) { await stopCapture(); return; }
    } else { ownerApp = null; }
    if (version === request) update(state);
  } catch (error) {
    if (version === request) {
      failedRevision = revision;
      actionError = String(error);
      settingsMessage = settings.dirty ? "保存失败；修改已保留，修正后会自动保存" : "配置已保存，但识别启动失败";
      update(snapshot.state);
    }
  } finally {
    saving = false;
    update(snapshot.state);
    if (!disposed && settings.dirty && failedRevision !== settings.revision) scheduleSave();
  }
}

export async function manageDownload(cancel = false) {
  actionError = "";
  try { update(await (cancel ? cancelDownload() : downloadModels())); }
  catch (error) { actionError = String(error); update(snapshot.state); }
}

export async function toggleCapture() {
  if (saving) return;
  if (settings.dirty) {
    await applyDraft();
    if (settings.dirty || actionError) return;
  }
  const request = ++version;
  actionError = "";
  try {
    if (snapshot.state?.status.running) {
      ownerApp = null;
      update(await stopCapture());
    } else {
      ownerApp = appId();
      if (!ownerApp) throw new Error("请先在游戏模式启动一个游戏。");
      lastMenuOpen = menuOpen();
      await setMenuOpen(lastMenuOpen);
      const state = await startCapture();
      if (version === request) update(state);
    }
  } catch (error) {
    ownerApp = null;
    if (version === request) {
      actionError = String(error);
      update(snapshot.state);
    }
  }
}

export function beginPolling() {
  disposed = false;
  async function poll() {
    const request = version;
    try {
      if (saving) return;
      let state = await getState();
      if (request !== version || disposed || saving) return;
      let opened: boolean;
      try { opened = menuOpen(); }
      catch (error) {
        if (state.status.running) await stopCapture();
        ownerApp = null;
        throw error;
      }
      // Closing QAM must not discard edits. Invalid input stays editable without retry loops.
      if (!opened && settings.dirty && failedRevision !== settings.revision) {
        await applyDraft();
        return;
      }
      if (state.status.running) {
        if (opened !== lastMenuOpen) {
          state = await setMenuOpen(opened);
          lastMenuOpen = opened;
        }
      }
      // A game exit, switch, or frontend reload must not continue capturing unrelated screens.
      if (state.status.running && (ownerApp === null || appId() !== ownerApp)) {
        state = await stopCapture();
        ownerApp = null;
      }
      if (request === version) update(state);
    } catch (error) {
      if (request === version) update(snapshot.state, String(error));
    } finally {
      if (!disposed) timer = setTimeout(poll, 500);
    }
  }
  void poll();
}

export function endPolling() {
  disposed = true;
  version++;
  clearTimeout(timer);
  clearTimeout(saveTimer);
  listeners.clear();
  // The Python _unload hook also stops the process group if the frontend disappears.
  void stopCapture().catch(() => { /* The backend can already be unloaded. */ });
}
