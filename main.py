import sys
from pathlib import Path

import decky

# Decky loads main.py by path. Include the bundled package independently of its working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from caption.service import Service  # noqa: E402


class Plugin:
    async def _main(self):
        self.service = Service(
            Path(__file__).parent, decky.DECKY_PLUGIN_SETTINGS_DIR, decky.DECKY_PLUGIN_RUNTIME_DIR,
            Path.home() / "homebrew/data/DeckyLiveCaption",
        )

    async def get_state(self):
        return self.service.snapshot()

    async def save_config(self, config):
        return await self.service.configure(config)

    async def start(self):
        return await self.service.start()

    async def stop(self):
        return await self.service.stop()

    async def set_menu_open(self, opened):
        return self.service.set_menu_open(opened)

    async def download_models(self):
        self.service.installer.start()
        return self.service.snapshot()

    async def cancel_download(self):
        self.service.installer.cancelled.set()
        return self.service.snapshot()

    async def _unload(self):
        await self.service.stop()
        await self.service.installer.close()
