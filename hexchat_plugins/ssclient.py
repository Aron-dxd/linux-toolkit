import hexchat
import time
import threading
import zipfile
from pathlib import Path
from datetime import datetime
import subprocess
import shlex
import shutil
import tempfile

__module_name__ = "Search DCC Staged FZF"
__module_version__ = "2.9"
__module_description__ = "Stage search selections via fzf, review/edit, commit later"

# -----------------------------
# Paths and Constants
# -----------------------------
DOWNLOAD_DIR = Path.home() / "Downloads" / "ebooks"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

STATE_DIR = DOWNLOAD_DIR / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

SELECTIONS_FILE = STATE_DIR / "selections.txt"
STATE_FILE = STATE_DIR / "state.txt"
ZIP_WAIT_TIMEOUT = 30.0
ZIP_POLL_INTERVAL = 0.5

# -----------------------------
# Command: /ss — Search and Stage
# -----------------------------
def ss_cmd(word, word_eol, userdata):
    if len(word) < 2:
        hexchat.prnt("[Search DCC] Usage: /ss <query>")
        return hexchat.EAT_ALL

    query = " ".join(word[1:])
    existing_zips = set(DOWNLOAD_DIR.glob("*.zip"))

    hexchat.command(f"say @search {query}")
    hexchat.prnt(f"[Search DCC] Sent search: {query}")

    threading.Thread(
        target=wait_for_zip,
        args=(existing_zips,),
        daemon=True
    ).start()

    return hexchat.EAT_ALL

# -----------------------------
# Wait for zip
# -----------------------------
def wait_for_zip(existing):
    start = time.time()
    while time.time() - start < ZIP_WAIT_TIMEOUT:
        new_zips = set(DOWNLOAD_DIR.glob("*.zip")) - existing
        if new_zips:
            zip_path = next(iter(new_zips))
            try:
                with zipfile.ZipFile(zip_path, "r"):
                    handle_zip(zip_path)
                    return
            except zipfile.BadZipFile:
                pass
        time.sleep(ZIP_POLL_INTERVAL)

    hexchat.prnt("[Search DCC] No zip received (timeout).")

# -----------------------------
# Extract zip and launch fzf
# -----------------------------
def handle_zip(zip_path):
    extract_dir = DOWNLOAD_DIR / f"{zip_path.stem}_extracted"
    extract_dir.mkdir(exist_ok=True)

    with zipfile.ZipFile(zip_path) as z:
        z.extractall(extract_dir)

    txt_files = list(extract_dir.glob("*.txt"))
    if not txt_files:
        hexchat.prnt("[Search DCC] No .txt file found.")
        return

    launch_fzf(txt_files[0], zip_path, extract_dir)

# -----------------------------
# Launch fzf
# -----------------------------
def launch_fzf(txt_file, zip_path=None, extract_dir=None):
    lines = txt_file.read_text(
        encoding="utf-8",
        errors="ignore"
    ).splitlines()[6:]

    if not lines:
        hexchat.prnt("[Search DCC] No selectable entries.")
        return

    with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
        tmp.write("\n".join(lines) + "\n")
        input_path = tmp.name

    fzf_cmd = f"""
    cat {shlex.quote(input_path)} |
    fzf --multi --prompt="TAB mark / ENTER stage: " \
    >> {shlex.quote(str(SELECTIONS_FILE))}
    """

    subprocess.Popen([
        "kitty",
        "--class", "SearchDCC",
        "--title", "Search DCC",
        "-e", "sh", "-c", fzf_cmd
    ]).wait()

    Path(input_path).unlink(missing_ok=True)

    if zip_path and extract_dir:
        save_state(zip_path, extract_dir)

    hexchat.prnt("[Search DCC] Selections staged.")

# -----------------------------
# /se — Review selections
# -----------------------------
def se_cmd(word, word_eol, userdata):
    if not SELECTIONS_FILE.exists():
        hexchat.prnt("[Search DCC] No staged selections.")
        return hexchat.EAT_ALL

    selections = SELECTIONS_FILE.read_text().splitlines()
    if not selections:
        hexchat.prnt("[Search DCC] Selections file empty.")
        return hexchat.EAT_ALL

    with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
        tmp.write("\n".join(selections))
        tmp_path = tmp.name

    out_file = tmp_path + ".out"
    fzf_cmd = f"""
    cat {shlex.quote(tmp_path)} |
    fzf --multi --prompt="Review staged selections: " \
    > {shlex.quote(out_file)}
    """

    subprocess.Popen([
        "kitty",
        "--class", "SearchDCC",
        "--title", "Review Selections",
        "-e", "sh", "-c", fzf_cmd
    ]).wait()

    if Path(out_file).exists():
        new = Path(out_file).read_text().splitlines()
        if new:
            SELECTIONS_FILE.write_text("\n".join(new) + "\n")
            hexchat.prnt(f"[Search DCC] Updated staged selections ({len(new)} entries).")
        else:
            hexchat.prnt("[Search DCC] No changes made.")

# -----------------------------
# /sd — Send + background cleanup (non-blocking)
# -----------------------------
def sd_cmd(word, word_eol, userdata):
    if not SELECTIONS_FILE.exists():
        hexchat.prnt("[Search DCC] No staged selections.")
        return hexchat.EAT_ALL

    selections = SELECTIONS_FILE.read_text().splitlines()
    if not selections:
        hexchat.prnt("[Search DCC] Selection file empty.")
        return hexchat.EAT_ALL

    def send_worker():
        timestamp = datetime.now().strftime("[%d-%m ~ %I:%M %p]").lower()

        # Update history
        history_file = STATE_DIR / "history.txt"
        history_lines = history_file.read_text().splitlines() if history_file.exists() else []
        new_history = [f"{timestamp} {line}" for line in reversed(selections)]
        combined = (new_history + history_lines)[:50]
        history_file.write_text("\n".join(combined) + "\n")

        # Send selections
        for line in selections:
            hexchat.command(f"say {line}")
            time.sleep(0.5)

        # Cleanup in background
        cleanup_background()
        hexchat.prnt("[Search DCC] Download batch completed and logged in history.")

    threading.Thread(target=send_worker, daemon=True).start()

    return hexchat.EAT_ALL

# -----------------------------
# /sc — Discard + background cleanup
# -----------------------------
def sc_cmd(word, word_eol, userdata):
    cleanup_background()
    hexchat.prnt("[Search DCC] Staged selections discarded.")
    return hexchat.EAT_ALL

# -----------------------------
# State tracking
# -----------------------------
def save_state(zip_path, extract_dir):
    with open(STATE_FILE, "a") as f:
        f.write(f"ZIP|{zip_path}\n")
        f.write(f"DIR|{extract_dir}\n")

# -----------------------------
# Cleanup logic (blocking)
# -----------------------------
def cleanup_all():
    if STATE_FILE.exists():
        for line in STATE_FILE.read_text().splitlines():
            try:
                kind, path = line.split("|", 1)
                p = Path(path)
                if p.exists():
                    if kind == "DIR":
                        shutil.rmtree(p)
                    else:
                        p.unlink()
            except Exception:
                pass

    SELECTIONS_FILE.unlink(missing_ok=True)
    STATE_FILE.unlink(missing_ok=True)

# -----------------------------
# Cleanup wrapper (non-blocking)
# -----------------------------
def cleanup_background():
    def worker():
        cleanup_all()
        hexchat.prnt("[Search DCC] Cleanup completed in background.")
    threading.Thread(target=worker, daemon=True).start()

# -----------------------------
# Register commands
# -----------------------------
hexchat.hook_command("ss", ss_cmd)
hexchat.hook_command("se", se_cmd)
hexchat.hook_command("sd", sd_cmd)
hexchat.hook_command("sc", sc_cmd)

hexchat.prnt("[Search DCC] Loaded: /ss /se /sd /sc")
