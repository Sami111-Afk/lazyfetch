#!/usr/bin/env python3
import os
import sys
import platform
import subprocess
import time
import json
import argparse
import re
from pathlib import Path

try:
    import psutil
    from PIL import Image
except ImportError:
    print("Missing dependencies. Run: pip install psutil Pillow")
    sys.exit(1)

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

RESET = "\033[0m"
BOLD = "\033[1m"

ANSI_COLORS = {
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bright_red": "\033[91m",
    "bright_green": "\033[92m",
    "bright_yellow": "\033[93m",
    "bright_blue": "\033[94m",
    "bright_magenta": "\033[95m",
    "bright_cyan": "\033[96m",
    "bright_white": "\033[97m",
}

DEFAULT_CONFIG = {
    "image": {"path": "", "width": 28, "clean_background": False},
    "display": {
        "items": ["os", "kernel", "wm", "cpu", "gpu", "ram", "disk", "uptime", "packages", "colors", "colors2"],
        "gap": 3,
        "label_color": "cyan",
    },
}

CONFIG_PATH = Path.home() / ".config" / "lazyfetch" / "config.toml"
SCRIPT_PATH = Path("~/lazyfetch/lazyfetch.py").expanduser()


# ─── Config ───────────────────────────────────────────────────────────────────

def load_config():
    if not CONFIG_PATH.exists() or tomllib is None:
        return DEFAULT_CONFIG
    with open(CONFIG_PATH, "rb") as f:
        user = tomllib.load(f)
    return {
        "image": {**DEFAULT_CONFIG["image"], **user.get("image", {})},
        "display": {**DEFAULT_CONFIG["display"], **user.get("display", {})},
    }


def save_config(config):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    items = json.dumps(config["display"]["items"])
    clean_bg = "true" if config["image"].get("clean_background") else "false"
    content = f"""[image]
path = "{config["image"]["path"]}"
width = {config["image"]["width"]}
clean_background = {clean_bg}

[display]
items = {items}
gap = {config["display"]["gap"]}
label_color = "{config["display"]["label_color"]}"
"""
    CONFIG_PATH.write_text(content)


# ─── Startup helpers ──────────────────────────────────────────────────────────

def detect_shell():
    try:
        ppid = os.getppid()
        with open(f"/proc/{ppid}/comm") as f:
            s = f.read().strip()
        if s in ("fish", "bash", "zsh"):
            return s
    except Exception:
        pass
    return os.path.basename(os.environ.get("SHELL", "bash"))


def is_startup_enabled():
    targets = [
        Path.home() / ".config/fish/functions/fish_greeting.fish",
        Path.home() / ".bashrc",
        Path.home() / ".zshrc",
    ]
    for f in targets:
        if f.exists() and "lazyfetch" in f.read_text():
            return True
    return False


def add_to_startup(shell):
    cmd = f"python {SCRIPT_PATH}"
    if shell == "fish":
        greeting = Path.home() / ".config/fish/functions/fish_greeting.fish"
        if greeting.exists():
            content = greeting.read_text()
            if "lazyfetch" in content:
                return
            # Insert before last 'end'
            lines = content.rstrip().splitlines()
            lines.insert(-1, f"    {cmd}")
            greeting.write_text("\n".join(lines) + "\n")
        else:
            greeting.parent.mkdir(parents=True, exist_ok=True)
            greeting.write_text(f"function fish_greeting\n    {cmd}\nend\n")
    else:
        rc = Path.home() / (f".{shell}rc")
        with open(rc, "a") as f:
            f.write(f"\n# lazyfetch\n{cmd}\n")


def remove_from_startup():
    targets = [
        Path.home() / ".config/fish/functions/fish_greeting.fish",
        Path.home() / ".bashrc",
        Path.home() / ".zshrc",
    ]
    for path in targets:
        if not path.exists():
            continue
        content = path.read_text()
        if "lazyfetch" not in content:
            continue
        lines = content.splitlines(keepends=True)
        new_lines = [l for l in lines if "lazyfetch" not in l]
        path.write_text("".join(new_lines))


# ─── Image rendering ──────────────────────────────────────────────────────────

def clean_background(img, threshold=20):
    """Automatically removes background by making the corner color transparent."""
    img = img.convert("RGBA")
    pix = img.load()
    width, height = img.size
    
    # Get background color from top-left corner
    bg_r, bg_g, bg_b, _ = pix[0, 0]
    
    # Create a new image for the result
    new_data = []
    for y in range(height):
        for x in range(width):
            r, g, b, a = pix[x, y]
            # Check if color is close to background color
            if abs(r - bg_r) < threshold and abs(g - bg_g) < threshold and abs(b - bg_b) < threshold:
                new_data.append((0, 0, 0, 0))
            else:
                new_data.append((r, g, b, a))
    
    img.putdata(new_data)
    return img


def image_to_blocks(path, width, clean=False):
    try:
        img = Image.open(path).convert("RGBA")
        if clean:
            img = clean_background(img)
    except Exception as e:
        print(f"Could not open image: {e}", file=sys.stderr)
        return [], width

    aspect = img.height / img.width
    pixel_w = width
    pixel_h = int(pixel_w * aspect * 2)
    if pixel_h % 2 != 0:
        pixel_h += 1

    img = img.resize((pixel_w, pixel_h), Image.LANCZOS)
    pixels = img.load()

    ALPHA = 128
    lines = []
    for y in range(0, pixel_h, 2):
        line = ""
        for x in range(pixel_w):
            tr, tg, tb, ta = pixels[x, y]
            br, bg, bb, ba = pixels[x, y + 1] if y + 1 < pixel_h else (0, 0, 0, 0)
            top, bot = ta >= ALPHA, ba >= ALPHA

            if not top and not bot:
                line += " "
            elif top and not bot:
                line += f"\033[38;2;{tr};{tg};{tb}m▀{RESET}"
            elif not top and bot:
                line += f"\033[38;2;{br};{bg};{bb}m▄{RESET}"
            else:
                line += f"\033[38;2;{tr};{tg};{tb}m\033[48;2;{br};{bg};{bb}m▀{RESET}"
        lines.append(line)

    return lines, pixel_w


# ─── System info ──────────────────────────────────────────────────────────────

def get_os():
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return platform.system()


def get_kernel():
    return platform.uname().release


def get_wm():
    for env, name in [("HYPRLAND_INSTANCE_SIGNATURE", "Hyprland"), ("SWAYSOCK", "Sway")]:
        if os.environ.get(env):
            return name
    for env in ("XDG_CURRENT_DESKTOP", "DESKTOP_SESSION"):
        val = os.environ.get(env)
        if val:
            return val
    try:
        procs = subprocess.run(["ps", "-e", "-o", "comm="], capture_output=True, text=True).stdout.split()
        for wm in ["hyprland", "sway", "i3", "bspwm", "openbox", "xfwm4", "kwin_wayland"]:
            if wm in procs:
                return wm.capitalize()
    except Exception:
        pass
    return "Unknown"


def get_cpu():
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip().replace("(R)", "").replace("(TM)", "").replace("  ", " ")
    except Exception:
        pass
    return platform.processor() or "Unknown"


def get_ram():
    mem = psutil.virtual_memory()
    return f"{mem.used / 1024**3:.1f}GB / {mem.total / 1024**3:.1f}GB"


def get_uptime():
    secs = int(time.time() - psutil.boot_time())
    h, rem = divmod(secs, 3600)
    m, _ = divmod(rem, 60)
    return f"{h}h {m}m" if h else f"{m}m"


def get_shell():
    try:
        ppid = os.getppid()
        with open(f"/proc/{ppid}/comm") as f:
            parent = f.read().strip()
        if parent in ("fish", "bash", "zsh", "sh"):
            return parent
    except Exception:
        pass
    return os.path.basename(os.environ.get("SHELL", "")) or "Unknown"


def get_terminal():
    for var in ("TERM_PROGRAM", "TERMINAL", "TERM"):
        val = os.environ.get(var)
        if val:
            return val
    return "Unknown"


def get_packages():
    counts = []
    managers = [
        (["pacman", "-Qq", "--color=never"], "pacman"),
        (["dpkg", "--get-selections"], "dpkg"),
        (["rpm", "-qa"], "rpm"),
        (["flatpak", "list"], "flatpak"),
        (["snap", "list"], "snap"),
    ]
    for cmd, name in managers:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                count = len(result.stdout.strip().splitlines())
                if name in ("flatpak", "snap"): count -= 1 # skip header
                if count > 0:
                    counts.append(f"{count} ({name})")
        except FileNotFoundError:
            continue
    return ", ".join(counts) if counts else "Unknown"


def get_gpu():
    try:
        result = subprocess.run(["lspci"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "VGA" in line or "3D" in line or "Display" in line:
                gpu = line.split(":", 2)[-1].strip()
                for p in ["Corporation", "Integrated Graphics Controller"]:
                    gpu = gpu.replace(p, "").strip()
                return gpu
    except Exception:
        pass
    return "Unknown"


def get_res():
    try:
        if os.environ.get("DISPLAY"):
            result = subprocess.run(["xrandr"], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if "*" in line:
                    return line.split()[0]
        for path in Path("/sys/class/drm").glob("card*-*/modes"):
            with open(path) as f:
                mode = f.readline().strip()
                if mode: return mode
    except Exception:
        pass
    return "Unknown"


def get_disk():
    try:
        usage = psutil.disk_usage("/")
        return f"{usage.used / 1024**3:.1f}GB / {usage.total / 1024**3:.1f}GB ({usage.percent}%)"
    except Exception:
        pass
    return "Unknown"


def get_battery():
    try:
        batt = psutil.sensors_battery()
        if batt:
            status = "Charging" if batt.power_plugged else "Discharging"
            return f"{batt.percent}% ({status})"
    except Exception:
        pass
    return None


def get_local_ip():
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass
    return "Unknown"


def get_colors():
    return "".join([f"\033[48;5;{i}m   " for i in range(8)]) + RESET


def get_colors_bright():
    return "".join([f"\033[48;5;{i}m   " for i in range(8, 16)]) + RESET


INFO_GETTERS = {
    "os":       ("OS",       get_os),
    "kernel":   ("Kernel",   get_kernel),
    "wm":       ("WM",       get_wm),
    "cpu":      ("CPU",      get_cpu),
    "gpu":      ("GPU",      get_gpu),
    "ram":      ("RAM",      get_ram),
    "disk":     ("Disk",     get_disk),
    "res":      ("Res",      get_res),
    "uptime":   ("Uptime",   get_uptime),
    "battery":  ("Battery",  get_battery),
    "shell":    ("Shell",    get_shell),
    "terminal": ("Terminal", get_terminal),
    "packages": ("Packages", get_packages),
    "ip":       ("Local IP", get_local_ip),
    "colors":   ("",         get_colors),
    "colors2":  ("",         get_colors_bright),
}


# ─── Rendering ────────────────────────────────────────────────────────────────

def col(text, name):
    return f"{ANSI_COLORS.get(name, '')}{text}{RESET}"


def bold(text):
    return f"{BOLD}{text}{RESET}"


def build_info_lines(items, label_color, custom_labels=None):
    if custom_labels is None:
        custom_labels = {}
        
    user = os.environ.get("USER", "user")
    host = platform.node()
    lines = [
        bold(col(f"{user}@{host}", label_color)),
        col("─" * (len(user) + len(host) + 1), label_color),
    ]
    for key in items:
        if key not in INFO_GETTERS:
            continue
        default_label, getter = INFO_GETTERS[key]
        val = getter()
        if val is None:
            continue
        
        label = custom_labels.get(key, default_label)
        
        if label:
            lines.append(f"{bold(col(label + ':', label_color))} {val}")
        else:
            lines.append(val)
    return lines


def strip_ansi(text):
    """Removes ANSI escape sequences to get the visible length of a string."""
    return re.sub(r'\033\[[0-9;]*m', '', text)


def get_terminal_width():
    try:
        return os.get_terminal_size().columns
    except Exception:
        return 80


def render(image_lines, img_width, info_lines, gap):
    gap_str = " " * gap
    blank = " " * img_width
    img_h = len(image_lines)
    info_h = len(info_lines)
    rows = max(img_h, info_h)
    
    term_w = get_terminal_width()
    # Max width for info text: term_w - img - gap - safety_margin
    max_info_w = term_w - img_width - gap - 4

    # Center info lines vertically relative to the image
    offset = (img_h - info_h) // 2 if img_h > info_h else 0

    print()
    for i in range(rows):
        img = image_lines[i] if i < img_h else blank
        
        info_idx = i - offset
        if 0 <= info_idx < info_h:
            info = info_lines[info_idx]
            # Truncate if visible length is too long
            visible_len = len(strip_ansi(info))
            if visible_len > max_info_w:
                # Simple truncation (might cut ANSI codes if not careful, 
                # but we'll just trim the content if it's too much)
                info = info[:max_info_w + (len(info) - visible_len)] + "..."
        else:
            info = ""
        
        print(f" {img}{gap_str}{info}")
    print()


def checkbox_menu(title, available, current):
    """Interactive menu to toggle items with checkboxes."""
    selected = list(current)
    while True:
        # Clear screen for a cleaner feel
        print("\033[H\033[J", end="")
        print(f"\n  {bold(title)}\n")
        
        for i, item in enumerate(available, 1):
            is_sel = item in selected
            char = col("󰄵", "bright_green") if is_sel else "󰄱"
            # Fallback if symbols aren't supported
            if os.environ.get("TERM") == "linux":
                char = "[x]" if is_sel else "[ ]"
            else:
                char = f"[{col('x', 'bright_green') if is_sel else ' '}]"
                
            label = INFO_GETTERS[item][0] or item
            print(f"  {col(str(i) + ')', 'bright_cyan')} {char} {item.ljust(10)} ({label})")
        
        print(f"\n  {col('0)', 'bright_cyan')} Save and exit")
        
        choice = ask("\n  Toggle number", "0")
        if choice == "0":
            return selected
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(available):
                item = available[idx]
                if item in selected:
                    selected.remove(item)
                else:
                    selected.append(item)
        except ValueError:
            pass


def color_menu(current):
    """Interactive menu to pick a color with previews."""
    available = list(ANSI_COLORS.keys())
    while True:
        print("\033[H\033[J", end="")
        print(f"\n  {bold('Select label color')}\n")
        
        for i, name in enumerate(available, 1):
            is_sel = name == current
            marker = col("󰄵", "bright_green") if is_sel else "  "
            # Fallback for marker
            if os.environ.get("TERM") == "linux":
                marker = ">" if is_sel else " "
                
            preview = col(name, name)
            print(f"  {col(str(i) + ')', 'bright_cyan')} {marker} {preview}")
        
        print(f"\n  {col('0)', 'bright_cyan')} Cancel")
        
        choice = ask("\n  Pick a number", "0")
        if choice == "0":
            return current
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(available):
                return available[idx]
        except ValueError:
            pass


# ─── File picker ─────────────────────────────────────────────────────────────

def detect_de():
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "hyprland"
    if os.environ.get("SWAYSOCK"):
        return "sway"
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "kde" in desktop:
        return "kde"
    if "gnome" in desktop:
        return "gnome"
    if "xfce" in desktop:
        return "xfce"
    return "unknown"


def _run_picker(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        path = r.stdout.strip()
        if r.returncode == 0 and path:
            return path
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _wofi_picker():
    """Fuzzy image picker using wofi or rofi — best for tiling WMs."""
    try:
        home = str(Path.home())
        find = subprocess.run(
            ["find", home, "-type", "f",
             "(", "-iname", "*.png", "-o", "-iname", "*.jpg",
             "-o", "-iname", "*.jpeg", "-o", "-iname", "*.webp", ")"],
            capture_output=True, text=True, timeout=8,
        )
        files = find.stdout.strip()
        if not files:
            return None

        for launcher, args in [
            ("wofi", ["--dmenu", "--prompt", "Select image:"]),
            ("rofi", ["-dmenu", "-p", "Select image:"]),
            ("bemenu", ["-p", "Select image:"]),
        ]:
            try:
                r = subprocess.run(
                    [launcher] + args,
                    input=files, capture_output=True, text=True,
                )
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout.strip()
            except FileNotFoundError:
                continue
    except subprocess.TimeoutExpired:
        pass
    return None


def _tkinter_picker():
    try:
        import tkinter as tk
        from tkinter import filedialog, ttk

        root = tk.Tk()
        root.withdraw()

        # Dark theme via option_add
        root.tk_setPalette(
            background="#1e1e2e",
            foreground="#cdd6f4",
            activeBackground="#313244",
            activeForeground="#cdd6f4",
            selectBackground="#45475a",
            selectForeground="#cdd6f4",
        )
        root.attributes("-topmost", True)

        path = filedialog.askopenfilename(
            parent=root,
            title="lazyfetch — select image",
            initialdir=str(Path.home()),
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"),
                ("All files", "*.*"),
            ],
        )
        root.destroy()
        return path or None
    except Exception:
        return None


def pick_image_path():
    de = detect_de()

    # DE-native pickers
    if de == "kde":
        path = _run_picker(["kdialog", "--getopenfilename", str(Path.home()),
                            "image/png image/jpeg image/jpg image/webp"])
        if path:
            return path

    if de in ("gnome", "xfce"):
        path = _run_picker(["zenity", "--file-selection", "--title=Select image",
                            f"--filename={Path.home()}/"])
        if path:
            return path

    # Tiling WM / Hyprland — fuzzy launcher picker
    if de in ("hyprland", "sway", "unknown"):
        path = _wofi_picker()
        if path:
            return path

    # Universal fallbacks
    for cmd in [
        ["kdialog", "--getopenfilename", str(Path.home()), "image/png image/jpeg"],
        ["zenity", "--file-selection", "--title=Select image"],
        ["yad", "--file-selection", "--title=Select image"],
    ]:
        path = _run_picker(cmd)
        if path:
            return path

    # Python built-in dialog
    path = _tkinter_picker()
    if path:
        return path

    # Manual fallback
    print(f"  {col('(no picker available, type path manually)', 'yellow')}")
    return ask("Image path")


def pick_image(current=""):
    print(f"\n  {col('1)', 'bright_cyan')} Browse with file picker")
    print(f"  {col('2)', 'bright_cyan')} Type path manually")
    print(f"  {col('3)', 'bright_cyan')} Disable image")
    if current:
        print(f"  {col('4)', 'bright_cyan')} Keep current  {col(current, 'white')}")
    print()
    print("  Choice: ", end="", flush=True)
    choice = input().strip()

    if choice == "1":
        return pick_image_path()
    elif choice == "2":
        return ask("Image path")
    elif choice == "3":
        return ""
    elif choice == "4" and current:
        return current
    return current


# ─── First-run setup ──────────────────────────────────────────────────────────

def ask(prompt, default=None):
    suffix = f" [{default}]" if default else ""
    print(f"  {prompt}{suffix}: ", end="", flush=True)
    answer = input().strip()
    return answer if answer else default


def first_run_setup():
    print(f"\n  Welcome to {bold(col('lazyfetch', 'bright_cyan'))}! Quick setup.\n")

    config = {
        "image": {"path": "", "width": 28},
        "display": {
            "items": ["os", "kernel", "wm", "cpu", "ram", "uptime", "shell"],
            "gap": 3,
            "label_color": "cyan",
        },
    }

    use_img = ask("Display an image? (y/n)", "n")
    if use_img.lower() == "y":
        path = pick_image()
        if path:
            config["image"]["path"] = path
        width = ask("Image width in chars", "28")
        if width and width.isdigit():
            config["image"]["width"] = int(width)

    startup = ask("\n  Run on every terminal open? (y/n)", "y")
    if startup.lower() == "y":
        shell = detect_shell()
        add_to_startup(shell)
        print(f"  Added to {shell} startup.")

    save_config(config)
    print(f"\n  Done! Use {bold('lazyfetch --settings')} to change settings anytime.\n")
    return config


# ─── Settings menu ────────────────────────────────────────────────────────────

def settings_menu():
    config = load_config()

    while True:
        startup = is_startup_enabled()
        img_path = config["image"].get("path") or "not set"
        img_width = config["image"].get("width", 28)
        clean_bg = config["image"].get("clean_background", False)
        label_color = config["display"].get("label_color", "cyan")
        items = config["display"].get("items", [])

        print(f"\n  {bold(col('lazyfetch', 'bright_cyan'))} — settings\n")
        print(f"  {col('1)', 'bright_cyan')} Change image       {col(img_path, 'white')}")
        print(f"  {col('2)', 'bright_cyan')} Image width        {col(str(img_width) + ' chars', 'white')}")
        print(f"  {col('3)', 'bright_cyan')} Label color        {col(label_color, label_color)}")
        print(f"  {col('4)', 'bright_cyan')} Run on startup     {col('enabled' if startup else 'disabled', 'bright_green' if startup else 'red')}")
        print(f"  {col('5)', 'bright_cyan')} Info items         {col(', '.join(items), 'white')}")
        print(f"  {col('6)', 'bright_cyan')} Clean background   {col('enabled' if clean_bg else 'disabled', 'bright_green' if clean_bg else 'red')}")
        print(f"  {col('7)', 'bright_cyan')} Exit\n")
        print("  Choice: ", end="", flush=True)

        choice = input().strip()

        if choice == "1":
            p = pick_image(current=config["image"].get("path", ""))
            config["image"]["path"] = p or ""
            save_config(config)
            print("  Saved.")

        elif choice == "2":
            w = ask("Width in chars", str(img_width))
            if w and w.isdigit():
                config["image"]["width"] = int(w)
                save_config(config)
                print("  Saved.")

        elif choice == "3":
            new_color = color_menu(label_color)
            if new_color:
                config["display"]["label_color"] = new_color
                save_config(config)
                print(f"  Color set to {col(new_color, new_color)}.")

        elif choice == "4":
            if startup:
                remove_from_startup()
                print("  Removed from startup.")
            else:
                shell = detect_shell()
                add_to_startup(shell)
                print(f"  Added to {shell} startup.")

        elif choice == "5":
            available = list(INFO_GETTERS.keys())
            new_items = checkbox_menu("Select info items", available, items)
            if new_items:
                config["display"]["items"] = new_items
                save_config(config)
                print("  Saved settings.")
            else:
                print("  No items selected.")

        elif choice == "6":
            config["image"]["clean_background"] = not clean_bg
            save_config(config)
            print("  Toggled background cleaning.")

        elif choice == "7":
            break


ASCII_LOGOS = {
    "arch": [
        "      /\\      ",
        "     /  \\     ",
        "    /    \\    ",
        "   /      \\   ",
        "  /   ,,   \\  ",
        " /   |  |   \\ ",
        "/___/    \\___\\",
    ],
    "ubuntu": [
        "         _          ",
        "     _--^ ^--_      ",
        "    /         \\     ",
        "   |           |    ",
        "    \\         /     ",
        "     °--_ _--°      ",
        "         °          ",
    ],
    "debian": [
        "  _____  ",
        " /  __ \\ ",
        "|  /    |",
        "|  \\___- ",
        " \\_      ",
        "   °     ",
    ],
    "fedora": [
        "      _______      ",
        "     /       \\     ",
        "    /    ____/___  ",
        "   /    /   /    \\ ",
        "  /    /   /     / ",
        "  \\____\\__/_____/  ",
    ],
    "generic": [
        "   _          ",
        "  | |         ",
        "  | |  _ _ __ ",
        "  | | | | '_ \\",
        "  | |__| | | |",
        "  |____|_|_| |_|",
    ]
}


def get_distro_id():
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="):
                    return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return "generic"


def get_ascii_logo(distro_id, label_color):
    logo = ASCII_LOGOS.get(distro_id, ASCII_LOGOS["generic"])
    color_code = ANSI_COLORS.get(label_color, "")
    colored_logo = [f"{color_code}{line}{RESET}" for line in logo]
    width = max(len(line) for line in logo) if logo else 0
    return colored_logo, width


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="lazyfetch — system info with image support")
    parser.add_argument("--image", "-i", help="Path to image file")
    parser.add_argument("--width", "-w", type=int, help="Image width in characters")
    parser.add_argument("--no-image", action="store_true", help="Skip image rendering")
    parser.add_argument("--settings", action="store_true", help="Open settings menu")
    args = parser.parse_args()

    if args.settings:
        settings_menu()
        return

    # First run
    if not CONFIG_PATH.exists():
        config = first_run_setup()
    else:
        config = load_config()

    image_path = args.image or config["image"].get("path", "")
    width = args.width or config["image"].get("width", 28)
    clean_bg = config["image"].get("clean_background", False)
    items = config["display"].get("items", list(INFO_GETTERS.keys()))
    gap = config["display"].get("gap", 3)
    label_color = config["display"].get("label_color", "cyan")

    image_lines, img_w = [], width
    if image_path and not args.no_image:
        expanded_path = os.path.expanduser(image_path)
        if os.path.exists(expanded_path):
            image_lines, img_w = image_to_blocks(expanded_path, width, clean=clean_bg)

    if not image_lines and not args.no_image:
        image_lines, img_w = get_ascii_logo(get_distro_id(), label_color)

    info_lines = build_info_lines(items, label_color, config.get("labels", {}))
    render(image_lines, img_w, info_lines, gap)


if __name__ == "__main__":
    main()
