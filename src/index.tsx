import { definePlugin, routerHook } from "@decky/api";
import { ButtonItem, DropdownItem, PanelSection, PanelSectionRow, SliderField,
  TextField, ToggleField, staticClasses } from "@decky/ui";
import { useState } from "react";
import { FaClosedCaptioning } from "react-icons/fa";
import { compositionAvailable } from "./Composition";
import { Subtitle } from "./Subtitle";
import { beginPolling, editConfig, endPolling, manageDownload,
  toggleCapture, useBackend } from "./store";
import { changeEdge, edgeLimits, edges } from "./regions";
import type { Edge, Region } from "./regions";
import type { Config } from "./types";

function Content() {
  const { state, error, draft, saving, settingsMessage } = useBackend();
  const [busy, setBusy] = useState(false);
  if (!state || !draft) return <PanelSection title="Live Caption">
    <PanelSectionRow>{error || "正在连接插件后端…"}</PanelSectionRow>
  </PanelSection>;
  const change = <K extends keyof Config>(key: K, value: Config[K]) => {
    editConfig({ [key]: value });
  };
  const field = (key: keyof Config, label: string) => <PanelSectionRow key={key}>
    <TextField label={label} value={String(draft[key])}
      onChange={(event) => change(key, event.target.value)} />
  </PanelSectionRow>;
  const slider = (key: keyof Config, label: string, min: number, max: number, step: number) =>
    <PanelSectionRow key={key}><SliderField label={label} value={Number(draft[key])}
      min={min} max={max} step={step} showValue onChange={(value) => change(key, value)} />
    </PanelSectionRow>;

  const boundary = (region: Region, edge: Edge, label: string) => {
    const [min, max] = edgeLimits(draft, region, edge);
    return <PanelSectionRow key={`${region}-${edge}`}>
      <SliderField label={`${label}（%）`} value={edges(draft, region)[edge]}
        min={min} max={max} step={1} showValue
        onChange={(value) => editConfig(changeEdge(draft, region, edge, value))} />
    </PanelSectionRow>;
  };

  return <>
    <PanelSection title={"Live Caption · Alpha"}>
      <PanelSectionRow>{"状态："}{state.status.phase}</PanelSectionRow>
      {(error || state.status.error) && <PanelSectionRow>{error || state.status.error}</PanelSectionRow>}
      {!compositionAvailable && <PanelSectionRow>
        {"当前 Steam UI 无法提供被动字幕层。请勿启动，需更新适配。"}
      </PanelSectionRow>}
      <PanelSectionRow><ButtonItem disabled={busy || saving || !compositionAvailable} onClick={async () => {
        setBusy(true); try { await toggleCapture(); } finally { setBusy(false); }
      }}>{state.status.running ? "停止识别" : "开始自动识别"}</ButtonItem></PanelSectionRow>
      <PanelSectionRow>{`OCR ${state.status.ocr_ms.toFixed(0)} ms · 翻译 ${state.status.translation_ms.toFixed(0)} ms · 缓存 ${state.status.cache_hits}`}</PanelSectionRow>
      <PanelSectionRow>{"修改后自动保存并应用，无需点保存。连续调整结束约 0.6 秒后生效。识别会短暂重启，不退出游戏。"}</PanelSectionRow>
      {settingsMessage && <PanelSectionRow>{settingsMessage}</PanelSectionRow>}
    </PanelSection>
    <PanelSection title={"识别区域"}>
      <PanelSectionRow>{"左右从屏幕左侧计算，上下从屏幕顶部计算。0% 是左/上边缘，100% 是右/下边缘。"}</PanelSectionRow>
      {boundary("ocr", "left", "左边界")}
      {boundary("ocr", "right", "右边界")}
      {boundary("ocr", "top", "上边界")}
      {boundary("ocr", "bottom", "下边界")}
    </PanelSection>
    <PanelSection title={"字幕条"}>
      {boundary("subtitle", "left", "左边界")}
      {boundary("subtitle", "right", "右边界")}
      {boundary("subtitle", "top", "上边界")}
      {boundary("subtitle", "bottom", "下边界")}
      {slider("subtitle_opacity", "背景不透明度（0 为透明）", 0, 1, 0.05)}
      {slider("font_size", "字号", 14, 48, 1)}
      <PanelSectionRow><ToggleField label={"同时显示原文"} checked={draft.show_source}
        onChange={(value) => change("show_source", value)} /></PanelSectionRow>
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
        editConfig({ ...state.download.paths, translator: "hymt" });
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
