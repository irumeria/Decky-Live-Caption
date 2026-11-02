import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import ts from "typescript";

function render(state, bridgeError = "") {
  const code = ts.transpileModule(readFileSync("src/Subtitle.tsx", "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exports = {};
  const jsx = (type, props) => ({ type, props });
  runInNewContext(code, { exports, require(name) {
    if (name === "react/jsx-runtime") return { jsx, jsxs: jsx, Fragment: "fragment" };
    if (name === "./Composition") return { compositionAvailable: true,
      NotificationComposition: "passive-notification" };
    if (name === "./store") return { useBackend: () => ({ state, error: bridgeError }) };
    throw new Error(`Unexpected import: ${name}`);
  } });
  return exports.Subtitle();
}

const state = {
  config: { show_source: true, translator: "hymt", subtitle_top: 0.02,
    subtitle_height: 0.22, font_size: 18, subtitle_left: 0.1,
    subtitle_width: 0.8, subtitle_opacity: 0.4 },
  status: { running: true, source: "こんにちは", translation: "你好" },
};

test("subtitle uses passive text only, not a frozen screenshot or input surface", () => {
  const result = render(state);
  const json = JSON.stringify(result);
  assert.match(json, /こんにちは/);
  assert.match(json, /你好/);
  assert.match(json, /passive-notification/);
  assert.match(json, /"pointerEvents":"none"/);
  assert.doesNotMatch(json, /"type":"(?:img|canvas|button|input)"/);
});

test("stopped sessions and bridge errors cannot leave stale captions", () => {
  assert.equal(render({ ...state, status: { ...state.status, running: false } }), null);
  assert.equal(render(state, "connection lost"), null);
});

test("React receives dialogue as text, never injected HTML", () => {
  const result = render({ ...state, status: { ...state.status,
    translation: '<img src=x onerror="alert(1)">' } });
  assert.doesNotMatch(JSON.stringify(result), /dangerouslySetInnerHTML/);
});

test("source and translation use the same configured font size", () => {
  const result = render(state);
  const box = result.props.children[1].props.children;
  assert.equal(box.props.style.fontSize, state.config.font_size);
  const [source, translation] = box.props.children;
  assert.equal(source.props.style.fontSize, "1em");
  assert.equal(translation.props.style?.fontSize, undefined);
});

test("subtitle position, width, and background opacity use configuration", () => {
  const overlay = render(state).props.children[1];
  assert.equal(overlay.props.style.left, "10%");
  assert.equal(overlay.props.style.width, "80%");
  assert.equal(overlay.props.style.top, "2%");
  assert.equal(overlay.props.children.props.style.background, "rgba(0,0,0,0.4)");
});
