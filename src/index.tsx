import { definePlugin, routerHook } from "@decky/api";
import { ButtonItem, DropdownItem, PanelSection, PanelSectionRow, SliderField,
  TextField, ToggleField, staticClasses } from "@decky/ui";
import { useEffect, useState } from "react";
import { FaClosedCaptioning } from "react-icons/fa";
import { compositionAvailable } from "./Composition";
import { Subtitle } from "./Subtitle";
import { beginPolling, endPolling, manageDownload, saveConfig, toggleCapture, useBackend } from "./store";
import type { Config } from "./types";

function Content() {
  const { state, error } = useBackend();
  const [draft, setDraft] = useState<Config | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState("");
  useEffect(() => { if (state && draft === null) setDraft(state.config); }, [state, draft]);
  if (!state || !draft) return <PanelSection title="Live Caption">
    <PanelSectionRow>{error || "正在连接插件后端…"}</PanelSectionRow>
  </PanelSection>;
  const change = <K extends keyof Config>(key: K, value: Config[K]) => {
    setDraft({ ...draft, [key]: value }); setSaved("");
  };
  const field = (key: keyof Config, label: string) => <PanelSectionRow key={key}>
    <TextField label={label} value={String(draft[key])}
      onChange={(event) => change(key, event.target.value)} />
  </PanelSectionRow>;
  const slider = (key: keyof Config, label: string, min: number, max: number, step: number) =>
    <PanelSectionRow key={key}><SliderField label={label} value={Number(draft[key])}
      min={min} max={max} step={step} showValue onChange={(value) => change(key, value)} />
    </PanelSectionRow>;

  return <>
    <PanelSection title={"Live Caption · Alpha"}>
      <PanelSectionRow>{"状态："}{state.status.phase}</PanelSectionRow>
      {(error || state.status.error) && <PanelSectionRow>{error || state.status.error}</PanelSectionRow>}
      {!compositionAvailable && <PanelSectionRow>
        {"当前 Steam UI 无法提供被动字幕层。请勿启动，需更新适配。"}
      </PanelSectionRow>}
      <PanelSectionRow><ButtonItem disabled={busy || !compositionAvailable} onClick={async () => {
        setBusy(true); try { await toggleCapture(); } finally { setBusy(false); }
      }}>{state.status.running ? "停止识别" : "开始自动识别"}</ButtonItem></PanelSectionRow>
      <PanelSectionRow>{`OCR ${state.status.ocr_ms.toFixed(0)} ms · 翻译 ${state.status.translation_ms.toFixed(0)} ms · 缓存 ${state.status.cache_hits}`}</PanelSectionRow>
      <PanelSectionRow>{"保存会停止当前会话；启动使用已保存配置。退出或切换游戏会自动停止。"}</PanelSectionRow>
    </PanelSection>
    <PanelSection title={"OCR 运行环境"}>
      {field("python", "独立 Python 路径")}
      {field("model_dir", "Screen AI resources 目录")}
      {slider("fps", "采样次数 / 秒", 1, 4, 1)}
      {slider("stable_ms", "文字稳定等待 / ms", 250, 2000, 250)}
    </PanelSection>
    <PanelSection title={"翻译"}>
      <PanelSectionRow>{"Hy-MT2 1.8B Q4_K_M · Tencent · Apache-2.0。下载模型及 llama.cpp Vulkan 运行时约 1.17 GB，需 1.6 GiB 可用空间。仅点击后联网下载。"}</PanelSectionRow>
      <PanelSectionRow><ButtonItem disabled={busy || state.download.active} onClick={async () => {
        setBusy(true); try { await manageDownload(); } finally { setBusy(false); }
      }}>{"下载离线翻译模型与运行时"}</ButtonItem></PanelSectionRow>
      {state.download.phase !== "idle" && <PanelSectionRow>
        {`${state.download.phase} · ${state.download.file} · ${(state.download.received / 1e6).toFixed(1)} / ${(state.download.total / 1e6).toFixed(1)} MB`}
      </PanelSectionRow>}
      {state.download.error && <PanelSectionRow>{state.download.error}</PanelSectionRow>}
      {state.download.active && <PanelSectionRow><ButtonItem onClick={() => manageDownload(true)}>
        {"取消下载"}
      </ButtonItem></PanelSectionRow>}
      {state.download.phase === "ready" && <PanelSectionRow><ButtonItem onClick={() => {
        setDraft({ ...draft, ...state.download.paths, translator: "hymt" });
        setSaved("已填入下载路径，请保存配置");
      }}>{"使用已下载的模型"}</ButtonItem></PanelSectionRow>}
      <PanelSectionRow><DropdownItem label={"后端"} selectedOption={draft.translator}
        rgOptions={[{ label: "仅识别（不联网）", data: "source" },
          { label: "Hy-MT2（Deck 本机离线）", data: "hymt" }]}
        onChange={(option) => change("translator", option.data)} /></PanelSectionRow>
      {field("source_language", "原文语言，例如 Japanese")}
      {field("target_language", "目标语言，例如 Simplified Chinese")}
      {field("hymt_server", "本地 llama-server 路径")}
      {field("hymt_model", "本地 Hy-MT2 GGUF 路径")}
      {slider("hymt_gpu_layers", "GPU 层数（0 为 CPU）", 0, 99, 1)}
      {slider("hymt_threads", "本地推理 CPU 线程", 1, 8, 1)}
    </PanelSection>
    <PanelSection title={"识别区域（屏幕比例）"}>
      {slider("roi_x", "左边界", 0, 0.9, 0.05)}
      {slider("roi_y", "上边界", 0, 0.9, 0.05)}
      {slider("roi_width", "宽度", 0.1, 1, 0.05)}
      {slider("roi_height", "高度", 0.05, 0.8, 0.05)}
    </PanelSection>
    <PanelSection title={"字幕条"}>
      {slider("subtitle_left", "字幕左边界", 0, 0.95, 0.01)}
      {slider("subtitle_top", "字幕上边界", 0, 0.8, 0.05)}
      {slider("subtitle_width", "字幕宽度", 0.05, 1, 0.01)}
      {slider("subtitle_height", "字幕最大高度", 0.05, 0.4, 0.05)}
      {slider("subtitle_opacity", "背景不透明度（0 为透明）", 0, 1, 0.05)}
      {slider("font_size", "字号", 14, 48, 1)}
      <PanelSectionRow><ToggleField label={"同时显示原文"} checked={draft.show_source}
        onChange={(value) => change("show_source", value)} /></PanelSectionRow>
      <PanelSectionRow><ButtonItem disabled={busy} onClick={async () => {
        setBusy(true);
        try { setDraft(await saveConfig(draft)); setSaved("配置已保存"); }
        catch { setSaved(""); /* The store exposes backend validation errors. */ }
        finally { setBusy(false); }
      }}>{"保存配置"}</ButtonItem></PanelSectionRow>
      {saved && <PanelSectionRow>{saved}</PanelSectionRow>}
    </PanelSection>
  </>;
}

export default definePlugin(() => {
  beginPolling();
  routerHook.addGlobalComponent("DeckyLiveCaptionSubtitle", Subtitle);
  return {
    name: "Decky Live Caption",
    titleView: <div className={staticClasses.Title}>Live Caption</div>,
    content: <Content />, icon: <FaClosedCaptioning />,
    onDismount() {
      endPolling();
      routerHook.removeGlobalComponent("DeckyLiveCaptionSubtitle");
    },
  };
});
