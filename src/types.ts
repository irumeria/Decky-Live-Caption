export interface Config {
  python: string; model_dir: string;
  source_language: string; target_language: string;
  translator: "source" | "hymt";
  hymt_server: string; hymt_model: string; hymt_gpu_layers: number; hymt_threads: number;
  fps: number; stable_ms: number; min_confidence: number;
  roi_x: number; roi_y: number; roi_width: number; roi_height: number;
  font_size: number; subtitle_top: number; subtitle_height: number; show_source: boolean;
  subtitle_left: number; subtitle_width: number; subtitle_opacity: number;
}
export interface Status {
  running: boolean; phase: string; error: string;
  source: string; translation: string; revision: number;
  cache_hits: number; ocr_ms: number; translation_ms: number;
}
export interface Download {
  phase: "idle" | "downloading" | "verifying" | "installing" | "ready" | "error" | "cancelled";
  active: boolean; file: string; received: number; total: number; error: string;
  paths: Partial<Config>;
}
export interface State { config: Config; status: Status; download: Download }
