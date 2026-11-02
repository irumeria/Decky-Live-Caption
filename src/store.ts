import { callable } from "@decky/api";
import { Router } from "@decky/ui";
import { useSyncExternalStore } from "react";
import type { Config, State } from "./types";

const getState = callable<[], State>("get_state");
const startCapture = callable<[], State>("start");
const stopCapture = callable<[], State>("stop");
const configure = callable<[Config], State>("save_config");
const setMenuOpen = callable<[boolean], State>("set_menu_open");
const downloadModels = callable<[], State>("download_models");
const cancelDownload = callable<[], State>("cancel_download");
let snapshot: { state: State | null; error: string } = { state: null, error: "" };
const listeners = new Set<() => void>();
let disposed = false;
let timer: ReturnType<typeof setTimeout> | undefined;
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
  snapshot = { state, error };
  listeners.forEach((listener) => listener());
}

export function useBackend() {
  return useSyncExternalStore((listener) => {
    listeners.add(listener);
    return () => { listeners.delete(listener); };
  }, () => snapshot);
}

export async function saveConfig(config: Config) {
  const request = ++version;
  actionError = "";
  try {
    const state = await configure(config);
    ownerApp = null;
    if (version === request) update(state);
    return state.config;
  } catch (error) {
    if (version === request) {
      actionError = String(error);
      update(snapshot.state);
    }
    throw error;
  }
}

export async function manageDownload(cancel = false) {
  actionError = "";
  try { update(await (cancel ? cancelDownload() : downloadModels())); }
  catch (error) { actionError = String(error); update(snapshot.state); }
}

export async function toggleCapture() {
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
      let state = await getState();
      if (request !== version || disposed) return;
      if (state.status.running) {
        let opened: boolean;
        try { opened = menuOpen(); }
        catch (error) {
          state = await stopCapture();
          ownerApp = null;
          throw error;
        }
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
  listeners.clear();
  // The Python _unload hook also stops the process group if the frontend disappears.
  void stopCapture().catch(() => { /* The backend can already be unloaded. */ });
}
