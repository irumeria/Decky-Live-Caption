import type { Config } from "./types";

// This state belongs to the plugin, not a QAM component that Steam can unmount.
export class SettingsDraft {
  config: Config | null = null;
  dirty = false;
  revision = 0;

  receive(config: Config) {
    if (!this.dirty) this.config = config;
  }

  edit(patch: Partial<Config>) {
    if (this.config === null) throw new Error("设置尚未加载");
    this.config = { ...this.config, ...patch };
    this.dirty = true;
    this.revision++;
  }

  saved(config: Config, revision: number) {
    // A save response can arrive after the user moves another slider.
    if (revision === this.revision) {
      this.config = config;
      this.dirty = false;
    }
  }
}
