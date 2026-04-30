#!/usr/bin/env python3
import os
import sys
import platform
import subprocess
import time
import json
import argparse
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
    "image": {"path": "", "width": 28},
    "display": {
        "items": ["os", "kernel", "wm", "cpu", "ram", "uptime", "shell"],
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
    content = f"""[image]
path = "{config["image"]["path"]}"
width = {config["image"]["width"]}

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

def image_to_blocks(path, width):
    try:
        img = Image.open(path).convert("RGBA")
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
    for cmd, name in [
        (["pacman", "-Qq", "--color=never"], "pacman"),
        (["dpkg", "--get-selections"], "dpkg"),
        (["rpm", "-qa"], "rpm"),
    ]:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return f"{len(result.stdout.strip().splitlines())} ({name})"
        except FileNotFoundError:
            continue
    return "Unknown"


INFO_GETTERS = {
    "os":       ("OS",       get_os),
    "kernel":   ("Kernel",   get_kernel),
    "wm":       ("WM",       get_wm),
    "cpu":      ("CPU",      get_cpu),
    "ram":      ("RAM",      get_ram),
    "uptime":   ("Uptime",   get_uptime),
    "shell":    ("Shell",    get_shell),
    "terminal": ("Terminal", get_terminal),
    "packages": ("Packages", get_packages),
}


# ─── Rendering ────────────────────────────────────────────────────────────────

def col(text, name):
    return f"{ANSI_COLORS.get(name, '')}{text}{RESET}"


def bold(text):
    return f"{BOLD}{text}{RESET}"


def build_info_lines(items, label_color):
    user = os.environ.get("USER", "user")
    host = platform.node()
    lines = [
        bold(col(f"{user}@{host}", label_color)),
        col("─" * (len(user) + len(host) + 1), label_color),
    ]
    for key in items:
        if key not in INFO_GETTERS:
            continue
        label, getter = INFO_GETTERS[key]
        lines.append(f"{bold(col(label + ':', label_color))} {getter()}")
    return lines


def render(image_lines, img_width, info_lines, gap):
    gap_str = " " * gap
    blank = " " * img_width
    rows = max(len(image_lines), len(info_lines))
    print()
    for i in range(rows):
        img = image_lines[i] if i < len(image_lines) else blank
        info = info_lines[i] if i < len(info_lines) else ""
        print(f" {img}{gap_str}{info}")
    print()


# ─── File picker ─────────────────────────────────────────────────────────────

def pick_image_path():
    """Try GUI file picker, fall back to manual input."""
    pickers = [
        ["kdialog", "--getopenfilename", str(Path.home()), "image/png image/jpeg image/jpg image/webp"],
        ["zenity", "--file-selection", "--title=Select image", f"--filename={Path.home()}/"],
        ["yad", "--file-selection", "--title=Select image"],
    ]

    for cmd in pickers:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                path = result.stdout.strip()
                if path:
                    return path
        except FileNotFoundError:
            continue

    # No GUI picker available — manual input
    print(f"  {col('(no GUI picker found, type path manually)', 'yellow')}")
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
        label_color = config["display"].get("label_color", "cyan")
        items = config["display"].get("items", [])

        print(f"\n  {bold(col('lazyfetch', 'bright_cyan'))} — settings\n")
        print(f"  {col('1)', 'bright_cyan')} Change image       {col(img_path, 'white')}")
        print(f"  {col('2)', 'bright_cyan')} Image width        {col(str(img_width) + ' chars', 'white')}")
        print(f"  {col('3)', 'bright_cyan')} Label color        {col(label_color, label_color)}")
        print(f"  {col('4)', 'bright_cyan')} Run on startup     {col('enabled' if startup else 'disabled', 'bright_green' if startup else 'red')}")
        print(f"  {col('5)', 'bright_cyan')} Info items         {col(', '.join(items), 'white')}")
        print(f"  {col('6)', 'bright_cyan')} Exit\n")
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
            print(f"  Available: {', '.join(ANSI_COLORS.keys())}")
            c = ask("Color", label_color)
            if c in ANSI_COLORS:
                config["display"]["label_color"] = c
                save_config(config)
                print("  Saved.")
            else:
                print("  Invalid color.")

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
            print(f"  Available: {', '.join(available)}")
            print(f"  Current:   {', '.join(items)}")
            raw = ask("New list (comma separated)", ", ".join(items))
            new_items = [i.strip() for i in raw.split(",") if i.strip() in available]
            if new_items:
                config["display"]["items"] = new_items
                save_config(config)
                print("  Saved.")
            else:
                print("  No valid items entered.")

        elif choice == "6":
            break


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
    items = config["display"].get("items", list(INFO_GETTERS.keys()))
    gap = config["display"].get("gap", 3)
    label_color = config["display"].get("label_color", "cyan")

    image_lines, img_w = [], width
    if image_path and not args.no_image:
        image_lines, img_w = image_to_blocks(os.path.expanduser(image_path), width)

    render(image_lines, img_w, build_info_lines(items, label_color), gap)


if __name__ == "__main__":
    main()
