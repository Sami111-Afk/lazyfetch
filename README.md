# lazyfetch

A minimal, fully customizable system fetch tool for Linux with support for rendering any image directly in the terminal using colored Unicode half-blocks.

![preview placeholder](https://placehold.co/800x300/1a1a2e/00ffcc?text=lazyfetch+preview)

---

## Features

- **Image rendering** — display any PNG/JPG as colored pixel art next to your system info
- **Transparent PNG support** — alpha channel is handled correctly, no black backgrounds
- **First-run setup wizard** — guided setup on first launch
- **Interactive settings menu** — change everything with `lazyfetch --settings`
- **Startup toggle** — enable/disable auto-run on terminal open, directly from the menu
- **Configurable info items** — choose what to show and in what order
- **TOML config** — clean, human-readable configuration file
- **No heavy dependencies** — just Python + Pillow + psutil

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/savusamuel95-sys/lazyfetch.git ~/lazyfetch
```

### 2. Install dependencies

```bash
pip install Pillow psutil
```

> On Arch Linux / systems with PEP 668:
> ```bash
> pip install Pillow psutil --break-system-packages
> ```

### 3. Run

```bash
python ~/lazyfetch/lazyfetch.py
```

On first launch, a setup wizard will guide you through picking an image and enabling startup.

---

## Usage

```bash
# Normal run (reads from config)
python ~/lazyfetch/lazyfetch.py

# Override image on the fly
python ~/lazyfetch/lazyfetch.py --image ~/Pictures/avatar.png

# Change image width
python ~/lazyfetch/lazyfetch.py --width 20

# Skip the image
python ~/lazyfetch/lazyfetch.py --no-image

# Open settings menu
python ~/lazyfetch/lazyfetch.py --settings
```

---

## Settings menu

```
  lazyfetch — settings

  1) Change image       ~/Pictures/avatar.png
  2) Image width        28 chars
  3) Label color        cyan
  4) Run on startup     enabled
  5) Info items         os, kernel, wm, cpu, ram, uptime, shell
  6) Exit
```

Everything is saved automatically to `~/.config/lazyfetch/config.toml`.

---

## Configuration

The config file lives at `~/.config/lazyfetch/config.toml`.

```toml
[image]
path = "~/Pictures/avatar.png"   # path to your image (PNG, JPG, etc.)
width = 28                        # width in terminal characters

[display]
items = ["os", "kernel", "wm", "cpu", "ram", "uptime", "shell"]
gap = 3                           # spaces between image and info
label_color = "cyan"              # color for labels
```

### Available info items

| Key        | Shows                        |
|------------|------------------------------|
| `os`       | OS name from /etc/os-release |
| `kernel`   | Kernel version               |
| `wm`       | Window manager / DE          |
| `cpu`      | CPU model name               |
| `ram`      | Used / Total RAM             |
| `uptime`   | System uptime                |
| `shell`    | Current shell                |
| `terminal` | Terminal emulator            |
| `packages` | Package count                |

### Available colors

`black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`,
`bright_red`, `bright_green`, `bright_yellow`, `bright_blue`, `bright_magenta`, `bright_cyan`, `bright_white`

---

## How image rendering works

Images are rendered using the Unicode half-block character `▀` combined with 24-bit ANSI true color codes. Each character represents two pixels — the top pixel sets the foreground color and the bottom pixel sets the background. Transparent pixels (PNG alpha) are skipped so your terminal background shows through naturally.

---

## Requirements

- Python 3.11+ (or 3.9+ with `pip install tomli`)
- [Pillow](https://python-pillow.org/)
- [psutil](https://github.com/giampaolo/psutil)
- A terminal with true color support (most modern terminals)

---

## License

MIT
