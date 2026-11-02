#!/usr/bin/env python3
"""Unprivileged Linux worker. Pixels stay in memory and never cross the Decky RPC boundary."""

import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent / "vendor"))

from caption.config import Config  # noqa: E402

WIDTH, HEIGHT = 1280, 800  # RGB rows are aligned to four bytes at this width.


def find_gamescope_node(objects):
    for obj in objects:
        if obj.get("type") != "PipeWire:Interface:Node":
            continue
        props = obj["info"]["props"]
        if props.get("node.name") == "gamescope" and props.get("media.class") == "Video/Source":
            return int(obj["id"])
    raise RuntimeError("No Gamescope video source. Start a game in Steam Game Mode")


def capture_command(node_id, fps):
    return [
        "gst-launch-1.0",
        "-q",
        "pipewiresrc",
        f"path={node_id}",
        "do-timestamp=true",
        "!",
        "videorate",
        "drop-only=true",
        "!",
        f"video/x-raw,framerate={fps}/1",
        "!",
        "videoconvert",
        "!",
        "videoscale",
        "!",
        f"video/x-raw,format=RGB,width={WIDTH},height={HEIGHT},pixel-aspect-ratio=1/1",
        "!",
        "fdsink",
        "fd=1",
        "sync=false",
    ]


async def run(config, emit):
    from PIL import Image
    from providers.chromescreenai_protos.chrome_screen_ai_pb2 import VisualAnnotation
    from providers.chromescreenai_subprocess import ScreenAIEngine

    dump = await asyncio.create_subprocess_exec(
        "pw-dump", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
    )
    data, _ = await asyncio.wait_for(dump.communicate(), 10)
    if dump.returncode:
        raise RuntimeError("pw-dump failed to connect to the user PipeWire session")
    node_id = find_gamescope_node(json.loads(data))
    engine = ScreenAIEngine(config.model_dir)
    rect = (
        round(config.roi_x * WIDTH),
        round(config.roi_y * HEIGHT),
        round((config.roi_x + config.roi_width) * WIDTH),
        round((config.roi_y + config.roi_height) * HEIGHT),
    )
    capture = await asyncio.create_subprocess_exec(
        *capture_command(node_id, config.fps),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    frames = asyncio.Queue(maxsize=1)

    async def receive():
        while True:
            raw = await capture.stdout.readexactly(WIDTH * HEIGHT * 3)
            if frames.full():
                frames.get_nowait()  # OCR can be slower than capture. Keep only the latest frame.
            frames.put_nowait(raw)

    def recognize(raw):
        image = Image.frombytes("RGB", (WIDTH, HEIGHT), raw).crop(rect).convert("RGBA")
        digest = hashlib.sha256(image.tobytes()).digest()
        return image, digest

    def ocr(image):
        result = engine.perform(image.tobytes(), image.width, image.height)
        if result is None:
            raise RuntimeError("Screen AI PerformOCR returned null")
        annotation = VisualAnnotation()
        annotation.ParseFromString(result)
        # Preserve the engine's reading order. Do not apply English-letter filters to Japanese.
        return "\n".join(
            line.utf8_string.strip()
            for line in annotation.lines
            if line.utf8_string.strip() and line.confidence >= config.min_confidence
        )

    receiver = asyncio.create_task(receive())
    previous_digest, previous_text = None, ""
    try:
        while True:
            next_frame = asyncio.create_task(frames.get())
            done, _ = await asyncio.wait(
                {receiver, next_frame}, timeout=10, return_when=asyncio.FIRST_COMPLETED
            )
            if receiver in done or not done:
                next_frame.cancel()
                if receiver in done:
                    await receiver  # Propagate short reads and child failure.
                raise RuntimeError("No game frame received for 10 seconds")
            raw = next_frame.result()
            started = time.monotonic()
            image, digest = await asyncio.to_thread(recognize, raw)
            if digest != previous_digest:
                previous_text = await asyncio.to_thread(ocr, image)
                previous_digest = digest
            emit(
                {
                    "type": "text",
                    "text": previous_text,
                    "ocr_ms": round((time.monotonic() - started) * 1000, 2),
                }
            )
    finally:
        receiver.cancel()
        if capture.returncode is None:
            capture.terminate()
        await capture.wait()


def main():
    config = Config.parse(json.loads(sys.stdin.readline()))
    # Native libraries can print to stdout. Keep those messages out of the JSON protocol.
    output = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", buffering=1)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())

    def emit(message):
        output.write(json.dumps(message, ensure_ascii=False) + "\n")

    try:
        asyncio.run(run(config, emit))
    except Exception as error:
        emit({"type": "error", "message": f"{type(error).__name__}: {error}"})
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
