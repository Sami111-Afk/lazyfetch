# 🦥 lazyfetch

A minimal, high-performance, and fully customizable system fetch tool for Linux. Render any image as high-fidelity terminal pixel art or use elegant ASCII logos, all with zero complex dependencies.

![preview placeholder](https://placehold.co/800x400/1a1a2e/00ffcc?text=lazyfetch+v2.0+preview)

---

## ✨ Features

- **🖼️ Image Rendering** — Display any PNG/JPG/WebP as colored Unicode half-block pixel art.
- **🧹 Auto-Background Removal** — Automatically detect and strip solid backgrounds from images for a clean, transparent look.
- **🐧 Smart ASCII Fallback** — No image? No problem. `lazyfetch` detects your distro and shows a beautiful, color-matched ASCII logo.
- **📊 Comprehensive Info** — OS, Kernel, WM, CPU, **GPU**, **Disk**, **RAM**, **Resolution**, **Battery**, **Local IP**, and more.
- **🛠️ Interactive Setup & TUI** — No more editing config files by hand. Use the built-in interactive menu with **checkboxes** and **color previews**.
- **📏 Layout Protection** — Smart truncation prevents long info lines from breaking your beautiful layout or overlapping images.
- **🎨 Color Palettes** — Built-in standard and bright ANSI color bars for that classic fetch aesthetic.
- **⚡ Fast & Light** — Written in Python with minimal dependencies (`Pillow`, `psutil`).

---

## 🚀 Installation

### 1. Clone the repository
```bash
git clone https://github.com/savusamuel95-sys/lazyfetch.git ~/lazyfetch
```

### 2. Install dependencies
```bash
pip install Pillow psutil
```
*(On Arch Linux, use `--break-system-packages` if needed or install via `pacman -S python-pillow python-psutil`)*

### 3. Run it
```bash
python ~/lazyfetch/lazyfetch.py
```

---

## 🎮 Usage

```bash
# Standard run
python ~/lazyfetch/lazyfetch.py

# Open the Epic TUI Settings Menu
python ~/lazyfetch/lazyfetch.py --settings

# Override image and width on the fly
python ~/lazyfetch/lazyfetch.py --image ~/Pictures/logo.png --width 30

# Force ASCII mode
python ~/lazyfetch/lazyfetch.py --no-image
```

---

## ⚙️ Configuration

While you can change everything via `--settings`, the config is stored at `~/.config/lazyfetch/config.toml`:

```toml
[image]
path = "~/Pictures/avatar.png"
width = 28
clean_background = true   # Magic background removal!

[display]
items = ["os", "kernel", "wm", "cpu", "gpu", "ram", "disk", "uptime", "colors"]
gap = 3
label_color = "cyan"

[labels]
os = "Distro"             # Custom label overrides
cpu = "Chip"
```

---

## 🛠️ Available Info Items

| Key | Description |
| :--- | :--- |
| `os` | OS Pretty Name |
| `gpu` | GPU Model (lspci) |
| `res` | Screen Resolution |
| `disk` | Disk usage (root) |
| `packages` | Multi-manager count (Pacman, Flatpak, Snap, etc.) |
| `ip` | Local Network IP |
| `battery` | Charge % and status |
| `colors` | ANSI color palette |

---

## 📜 License
MIT — Created by [savusamuel95-sys](https://github.com/savusamuel95-sys)
