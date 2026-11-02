# Security

Do not put credentials, unpublished game content, or identity files in public reports.
For sensitive reports, contact the repository maintainer through a private channel.

The plugin runs without root privileges. OCR runs in a separate process, but this process is not a security sandbox.
Load Screen AI libraries only from a trusted source. A native library has the permissions of the plugin user.

Source-only mode makes no translation requests.
Hy-MT2 mode sends text only to an authenticated loopback service on the device.
The download button retrieves pinned files from Hugging Face and GitHub after a user action.
The installer checks file sizes and SHA-256 hashes before installation. It does not execute downloaded shell scripts.

Do not grant world-write access to input devices. This version does not read input devices.
Do not reset a game prefix or change system packages to install this plugin.
