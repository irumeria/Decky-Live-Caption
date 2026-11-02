"""Session-owned, offline Hy-MT2 inference on the Deck loopback interface."""

import asyncio
import json
import os
import secrets
import socket
import urllib.error
import urllib.request
from pathlib import Path

from caption.process import terminate_group


def translation_payload(config, text):
    prompt = (
        f"Translate the following text into {config.target_language}. "
        "Note that you should only output the translated result "
        "without any additional explanation:\n" + text
    )
    return {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "top_p": 0.6,
        "top_k": 20,
        "repeat_penalty": 1.05,
        "seed": 0,
        "max_tokens": 512,
        "stream": False,
    }


def translation_result(response):
    choice = response["choices"][0]
    # A long OCR region can exhaust the output budget. Never show a truncated translation.
    if choice["finish_reason"] != "stop":
        raise RuntimeError("Hy-MT2 did not finish the translation")
    text = choice["message"]["content"]
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Hy-MT2 returned no translation")
    return text.strip()


class LocalHyMT:
    def __init__(self, config):
        self.config = config
        self.process = None
        self.api_key = secrets.token_urlsafe(32)
        self.url = ""

    def _request(self, path, payload=None, timeout=1):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            self.url + path,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        # Local inference must not inherit HTTP_PROXY or send dialogue to a proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            return json.load(response)

    async def start(self):
        for path in (self.config.hymt_server, self.config.hymt_model):
            if not Path(path).is_file():
                raise FileNotFoundError(path)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env["LLAMA_API_KEY"] = self.api_key
        self.process = await asyncio.create_subprocess_exec(
            self.config.hymt_server,
            "-m",
            self.config.hymt_model,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "-ngl",
            str(self.config.hymt_gpu_layers),
            "-t",
            str(self.config.hymt_threads),
            "-tb",
            str(self.config.hymt_threads),
            "-c",
            "2048",
            "-np",
            "1",
            "--jinja",
            "--no-webui",
            "--log-disable",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        # Model loading precedes readiness. A refused connection or HTTP 503 is expected here only.
        deadline = asyncio.get_running_loop().time() + 45
        try:
            while asyncio.get_running_loop().time() < deadline:
                if self.process.returncode is not None:
                    raise RuntimeError(f"Hy-MT2 server exited ({self.process.returncode})")
                try:
                    health = await asyncio.to_thread(self._request, "/health")
                except urllib.error.HTTPError as error:
                    if error.code != 503:
                        raise
                except (urllib.error.URLError, TimeoutError):
                    pass
                else:
                    if health["status"] == "ok":
                        return
                    raise RuntimeError("Unexpected Hy-MT2 health response")
                await asyncio.sleep(0.1)
            raise TimeoutError("Hy-MT2 did not become ready within 45 seconds")
        except BaseException:
            await self.close()
            raise

    async def translate(self, text):
        response = await asyncio.to_thread(
            self._request, "/v1/chat/completions", translation_payload(self.config, text), 30
        )
        return translation_result(response)

    async def close(self):
        # Startup errors and the capture finalizer can both request cleanup.
        process, self.process = self.process, None
        if process is not None:
            await terminate_group(process)
