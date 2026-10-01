# Running LM-Pocket on a machine without internet

**Honest status for v0.1:** your *data* opens anywhere; the *app* needs a Python runtime on the host. LM-Pocket v0.1 is **not** "plug into any computer and go" yet.

## What a new offline machine needs

| Requirement | Why |
|---|---|
| Python **3.11–3.14** already installed (or `uv` with a cached Python) | v0.1 does not bundle an interpreter. |
| The **wheelhouse** for that OS + CPU + Python version, on the USB | Some dependencies are compiled (SQLCipher, cryptography, argon2, pydantic-core). Wheels are platform-specific. |
| A browser | The UI is `http://127.0.0.1:<port>`. |
| An MCP client (optional) | Claude Desktop, Cursor, Gemini CLI, LM Studio… Only needed for the MCP part of the demo. |

Nothing else: no network, no account, no service.

## USB layout

```text
USB/
├── LM-Pocket/                 # your encrypted pocket (data)
└── app/
    └── wheelhouse/
        ├── macos-arm64-cp312/
        ├── linux-x86_64-cp312/
        └── windows-amd64-cp312/
```

## Preparing the wheelhouse (on a machine with internet)

```bash
scripts/make-wheelhouse.sh /Volumes/USB/app/wheelhouse 3.12
```

It builds the `lm-pocket` wheel and downloads binary wheels of every dependency for each target platform with `pip download --only-binary=:all: --platform … --python-version …`. Repeat for each Python version you expect to meet (3.12 is the default target).

## Installing on the offline machine

```bash
python3 -m venv ~/.lm-pocket-venv
~/.lm-pocket-venv/bin/pip install --no-index --find-links /Volumes/USB/app/wheelhouse/macos-arm64-cp312 lm-pocket
~/.lm-pocket-venv/bin/lm-pocket open /Volumes/USB/LM-Pocket
```

(Windows: `py -3.12 -m venv`, then `Scripts\pip.exe` and `Scripts\lm-pocket.exe`.)

The venv lives on the host and contains only code, never your memory.

## Not supported in v0.1

- A host with no Python and no `uv`.
- A Python version or platform the wheelhouse was not built for.

Planned: a standalone Python runtime per OS on the USB so the app itself becomes portable (ROADMAP → Later).
