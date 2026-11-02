import { compositionAvailable, NotificationComposition } from "./Composition";
import { useBackend } from "./store";

export function Subtitle() {
  const { state, error } = useBackend();
  if (!state || error || !state.status.running || !compositionAvailable) return null;
  const { config, status } = state;
  const source = config.show_source || config.translator === "source" ? status.source : "";
  if (!source && !status.translation) return null;
  return <>
    <NotificationComposition />
    <div aria-live="off" style={{
      position: "fixed", top: `${config.subtitle_top * 100}%`,
      left: `${config.subtitle_left * 100}%`, width: `${config.subtitle_width * 100}%`,
      height: `${config.subtitle_height * 100}%`, boxSizing: "border-box",
      pointerEvents: "none", userSelect: "none", zIndex: 9999, overflow: "hidden",
      display: "flex", alignItems: "flex-start", justifyContent: "center",
    }}>
      <div style={{
        maxHeight: "100%", overflow: "hidden", boxSizing: "border-box", padding: "6px 12px",
        background: `rgba(0,0,0,${config.subtitle_opacity})`,
        borderRadius: 6, color: "white", textAlign: "center",
        whiteSpace: "pre-wrap", overflowWrap: "anywhere", fontSize: config.font_size,
        lineHeight: 1.3, fontFamily: "sans-serif", pointerEvents: "none",
      }}>
        {source && <div style={{ opacity: 0.85, fontSize: "1em" }}>
          {source}
        </div>}
        {status.translation && <div>{status.translation}</div>}
      </div>
    </div>
  </>;
}
