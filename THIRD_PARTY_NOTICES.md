# Third-party notices

## Decky Translator

Source: https://github.com/cat-in-a-box/Decky-Translator

Commit: `4358712ac2f0fb211462a573f554396d572e2095`

License: GPL-3.0. The full license is in `LICENSE`.

The following files are verbatim copies from `py_modules/providers/`:

- `runtime/vendor/providers/chromescreenai_subprocess.py`
- `runtime/vendor/providers/chromescreenai_protos/chrome_screen_ai_pb2.py`

The project uses the `ScreenAIEngine` adapter, not the upstream screenshot overlay or game-pause functions.
The generated protobuf file also carries Chromium copyright and BSD terms. See `licenses/CHROMIUM-BSD.txt`.

## LiveTranslator-kun

Source: https://github.com/neatsorg/livetranslate-decky

Commit: `bd8f9f49697267e86b61380d89203da8b82c781d`

License: GPL-3.0. The full license is in `LICENSE`.

`src/Composition.tsx` adapts its Steam UI composition-hook discovery.
This adaptation only requests notification composition. It does not request the input-taking overlay state.
Its Gamescope/PipeWire capture design informed the independently written capture worker.
No container installer or input-device permission changes were imported.

## Chromium Screen AI

Source: https://source.chromium.org/chromium/chromium/src/+/main:services/screen_ai/

The Screen AI library and models are not included in this repository or its installation archive.
The user supplies an existing local resource directory. Those resources retain their own distribution terms.

## Tencent Hy-MT2

Authors: Tencent Hy / Hunyuan team and contributors.

Source: https://huggingface.co/tencent/Hy-MT2-1.8B-GGUF

Revision: `1cd5208700acedef4ef93019b6cfc148b8522d45`

File: `Hy-MT2-1.8B-Q4_K_M.gguf`. License: Apache-2.0, as stated in the upstream model card.

SHA-256: `dc5f44fcf1fa496ee7ad725982c0c8c553a4de00259b53af84c4b89fb0c06699`

The download button retrieves this model from its upstream repository. This project does not bundle the weights.
The model remains under its own license, not the plugin license.

## llama.cpp

Authors: ggml-org and contributors. License: MIT.

Source and license: https://github.com/ggml-org/llama.cpp/tree/b10175

Release: https://github.com/ggml-org/llama.cpp/releases/tag/b10175

File: `llama-b10175-bin-ubuntu-vulkan-x64.tar.gz`

SHA-256: `74906d104aed776d4e3b387cb4efd67e450530ed602df40676108018937f44ae`

The download button installs the upstream portable Vulkan runtime. No runtime binaries are bundled in the plugin archive.

## Documentation screenshot

`docs/images/gameplay.png` shows the plugin over *終わる世界とバースデイ*, a game by コットンソフト (Cotton Software).
Game artwork and dialogue belong to their respective rights holders. They are not covered by the plugin GPL license.
The screenshot illustrates the plugin and does not include game executables, assets, or saved games.

## Frontend dependencies

Decky supplies the React, Decky API, and Decky UI modules at runtime.
The build configuration follows https://github.com/SteamDeckHomebrew/decky-plugin-template.

The bundle uses react-icons (MIT) and the Font Awesome 5 closed-captioning icon (CC BY 4.0).
Icon source: https://fontawesome.com/ . Attribution: Font Awesome, Fonticons, Inc.
License: https://creativecommons.org/licenses/by/4.0/ . The icon geometry is unchanged.
The react-icons license is in `licenses/REACT-ICONS.txt`.
The tslib license is in `licenses/TSLIB-0BSD.txt`.

The build lockfile records exact dependency versions. Python dependencies and models are not bundled.
