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

SELECTIONS_FILE = STATE_DIR / "selections.txt"  # staged selections
STATE_FILE = STATE_DIR / "state.txt"           # tracks zips and extracted dirs
ZIP_WAIT_TIMEOUT = 30.0
ZIP_POLL_INTERVAL = 0.5

# -----------------------------
# Command: /ss — Search and Stage
# Sends a search query, waits for new zip, launches FZF
# -----------------------------
def ss_cmd(word, word_eol, userdata):
    if len(word) < 2:
        hexchat.prnt("[Search DCC] Usage: /ss <query>")
        return hexchat.EAT_ALL

    query = " ".join(word[1:])
    existing_zips = set(DOWNLOAD_DIR.glob("*.zip"))

    hexchat.command(f"say @search {query}")
    hexchat.prnt(f"[Search DCC] Sent search: {query}")

    # Wait for zip in a background thread
    threading.Thread(target=wait_for_zip, args=(existing_zips,), daemon=True).start()
    return hexchat.EAT_ALL

# -----------------------------
# Wait for a new zip file to appear in DOWNLOAD_DIR
# -----------------------------
def wait_for_zip(existing):
    start = time.time()
    while time.time() - start < ZIP_WAIT_TIMEOUT:
        new_zips = set(DOWNLOAD_DIR.glob("*.zip")) - existing
        if new_zips:
            zip_path = next(iter(new_zips))
            try:
                # Ensure zip is valid before processing
                with zipfile.ZipFile(zip_path, "r"):
                    handle_zip(zip_path)
                    return
            except zipfile.BadZipFile:
                pass
        time.sleep(ZIP_POLL_INTERVAL)
    hexchat.prnt("[Search DCC] No zip received (timeout).")

# -----------------------------
# Extract zip and handle txt files inside
# -----------------------------
def handle_zip(zip_path):
    extract_dir = DOWNLOAD_DIR / f"{zip_path.stem}_extracted"
    extract_dir.mkdir(exist_ok=True)

    with zipfile.ZipFile(zip_path) as z:
        z.extractall(extract_dir)

    # Pick the first txt file for FZF selection
    txt_files = list(extract_dir.glob("*.txt"))
    if not txt_files:
        hexchat.prnt("[Search DCC] No .txt file found.")
        return

    launch_fzf(txt_files[0], zip_path, extract_dir)

# -----------------------------
# Launch fzf interface to stage selections
# -----------------------------
def launch_fzf(txt_file, zip_path=None, extract_dir=None):
    # Skip header lines (first 6) to show only meaningful entries
    lines = txt_file.read_text(encoding="utf-8", errors="ignore").splitlines()[6:]
    if not lines:
        hexchat.prnt("[Search DCC] No selectable entries.")
        return

    input_data = "\n".join(lines)
    fzf_cmd = f"""
    printf "%s" {shlex.quote(input_data)} |
    fzf --multi --prompt="TAB mark / ENTER stage: " \
    > {shlex.quote(str(SELECTIONS_FILE))}
    """

    # Open Kitty terminal for interactive selection
    subprocess.Popen([
        "kitty", "--class", "SearchDCC", "--title", "Search DCC",
        "-e", "sh", "-c", fzf_cmd
    ]).wait()

    if zip_path and extract_dir:
        save_state(zip_path, extract_dir)  # track extracted files for cleanup

    hexchat.prnt("[Search DCC] Selections staged.")

# -----------------------------
# Command: /se — Review/Edit staged selections
# Launches FZF for editing previously staged entries
# -----------------------------
def se_cmd(word, word_eol, userdata):
    if not SELECTIONS_FILE.exists():
        hexchat.prnt("[Search DCC] No staged selections.")
        return hexchat.EAT_ALL

    selections = SELECTIONS_FILE.read_text().splitlines()
    if not selections:
        hexchat.prnt("[Search DCC] Selections file empty.")
        return hexchat.EAT_ALL

    # Temporary file for FZF editing
    with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
        tmp.write("\n".join(selections))
        tmp_path = tmp.name

    out_file = tmp_path + ".out"
    fzf_cmd = f"""
    cat {shlex.quote(tmp_path)} | \
    fzf --multi --prompt="Review staged selections: " \
        > {shlex.quote(out_file)}
    """

    subprocess.Popen([
        "kitty", "--class", "SearchDCC", "--title", "Review Selections",
        "-e", "sh", "-c", fzf_cmd
    ]).wait()

    # Apply changes safely
    if Path(out_file).exists():
        new_selections = Path(out_file).read_text().splitlines()
        if new_selections:
            SELECTIONS_FILE.write_text("\n".join(new_selections) + "\n")
            hexchat.prnt(f"[Search DCC] Updated staged selections ({len(new_selections)} entries).")
        else:
            hexchat.prnt("[Search DCC] No changes made; staged selections remain unchanged.")

# -----------------------------
# Command: /sd — Commit and send staged selections
# Sends selections to chat, logs history, cleans up files
# -----------------------------
def sd_cmd(word, word_eol, userdata):
    if not SELECTIONS_FILE.exists():
        hexchat.prnt("[Search DCC] No staged selections.")
        return hexchat.EAT_ALL

    selections = SELECTIONS_FILE.read_text().splitlines()
    if not selections:
        hexchat.prnt("[Search DCC] Selection file empty.")
        return hexchat.EAT_ALL

    timestamp = datetime.now().strftime("[%d-%m ~ %I:%M %p]").lower()

    # Load existing history
    history_file = STATE_DIR / "history.txt"
    history_lines = history_file.read_text().splitlines() if history_file.exists() else []

    # Prepend new selections; keep latest 50 entries
    new_history = [f"{timestamp} {line}" for line in reversed(selections)]
    combined_history = (new_history + history_lines)[:50]
    history_file.write_text("\n".join(combined_history) + "\n", encoding="utf-8")

    # Send staged selections to chat with delay to avoid flooding
    for line in selections:
        hexchat.command(f"say {line}")
        time.sleep(0.4)

    cleanup_all()
    hexchat.prnt("[Search DCC] Download batch completed and logged in history.")
    return hexchat.EAT_ALL

# -----------------------------
# Command: /sc — Discard staged selections
# Cleans up all staged selections and temporary files
# -----------------------------
def sc_cmd(word, word_eol, userdata):
    cleanup_all()
    hexchat.prnt("[Search DCC] Staged selections discarded.")
    return hexchat.EAT_ALL

# -----------------------------
# Track state of zip/extracted directories
# -----------------------------
def save_state(zip_path, extract_dir):
    with open(STATE_FILE, "a") as f:
        f.write(f"ZIP|{zip_path}\n")
        f.write(f"DIR|{extract_dir}\n")

# -----------------------------
# Cleanup all staged selections and temporary files
# -----------------------------
def cleanup_all():
    if STATE_FILE.exists():
        for line in STATE_FILE.read_text().splitlines():
            try:
                kind, path = line.split("|", 1)
                p = Path(path)
                if p.exists():
                    shutil.rmtree(p) if kind == "DIR" else p.unlink()
            except Exception:
                pass

    SELECTIONS_FILE.unlink(missing_ok=True)
    STATE_FILE.unlink(missing_ok=True)

# -----------------------------
# Register HexChat commands
# -----------------------------
hexchat.hook_command("ss", ss_cmd)
hexchat.hook_command("se", se_cmd)
hexchat.hook_command("sd", sd_cmd)
hexchat.hook_command("sc", sc_cmd)

hexchat.prnt("[Search DCC] Loaded: /ss /se /sd /sc")
