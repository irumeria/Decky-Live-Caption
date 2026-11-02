import type { Config } from "./types";

export type Region = "ocr" | "subtitle";
export type Edge = "left" | "right" | "top" | "bottom";

export function edges(config: Config, region: Region) {
  const [x, y, width, height] = region === "ocr"
    ? [config.roi_x, config.roi_y, config.roi_width, config.roi_height]
    : [config.subtitle_left, config.subtitle_top, config.subtitle_width, config.subtitle_height];
  return { left: Math.round(x * 100), right: Math.round((x + width) * 100),
    top: Math.round(y * 100), bottom: Math.round((y + height) * 100) };
}

export function changeEdge(config: Config, region: Region, edge: Edge, percent: number): Partial<Config> {
  const box = { ...edges(config, region), [edge]: percent };
  // An edge changes only itself. The opposite edge stays fixed.
  return region === "ocr"
    ? { roi_x: box.left / 100, roi_y: box.top / 100,
      roi_width: (box.right - box.left) / 100, roi_height: (box.bottom - box.top) / 100 }
    : { subtitle_left: box.left / 100, subtitle_top: box.top / 100,
      subtitle_width: (box.right - box.left) / 100, subtitle_height: (box.bottom - box.top) / 100 };
}

export function edgeLimits(config: Config, region: Region, edge: Edge): [number, number] {
  const box = edges(config, region);
  const gap = region === "ocr" ? 1 : 5;
  switch (edge) {
    case "left": return [0, box.right - gap];
    case "right": return [box.left + gap, 100];
    case "top": return [region === "subtitle" ? Math.max(0, box.bottom - 40) : 0,
      Math.min(box.bottom - gap, region === "subtitle" ? 85 : 99)];
    case "bottom": return [box.top + gap,
      region === "subtitle" ? Math.min(100, box.top + 40) : 100];
  }
}
