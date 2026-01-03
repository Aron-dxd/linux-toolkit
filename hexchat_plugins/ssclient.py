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
import re

__module_name__ = "[Search DCC]"
__module_version__ = "3.0"
__module_description__ = "Stage search selections, sessioned history, strict verification"

# -----------------------------
# Paths
# -----------------------------
DOWNLOAD_DIR = Path.home() / "Downloads" / "ebooks"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

STATE_DIR = DOWNLOAD_DIR / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

SELECTIONS_FILE = STATE_DIR / "selections.txt"
STATE_FILE = STATE_DIR / "state.txt"
HISTORY_FILE = STATE_DIR / "history.txt"

ZIP_WAIT_TIMEOUT = 30.0
ZIP_POLL_INTERVAL = 0.5

# -----------------------------
# Canonical comparison
# -----------------------------
def canon_compare(s: str) -> str:
    s = s.lower()
    s = Path(s).stem
    return re.sub(r"[^a-z0-9]", "", s)


# -----------------------------
# Extract requested filename from history line
# -----------------------------
def extract_requested_filename(line: str) -> str:
    line = line.strip()

    # remove INFO / HASH suffix
    line = re.split(r"\s+::(INFO|HASH)::", line)[0]

    # if pipe exists, filename is after it
    if "|" in line:
        line = line.split("|", 1)[1]

    # remove leading !bot + ids
    line = re.sub(r"^!\S+(?:\s+[%\w\-]+)*\s+", "", line)

    return line.strip()

# -----------------------------
# /ss — Search
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
# Wait for ZIP
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
# Handle ZIP
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
# /se — Review
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

    return hexchat.EAT_ALL

# -----------------------------
# /sd — Send (creates SESSION)
# -----------------------------
def sd_cmd(word, word_eol, userdata):
    if not SELECTIONS_FILE.exists():
        hexchat.prnt("[Search DCC] No staged selections.")
        return hexchat.EAT_ALL

    selections = SELECTIONS_FILE.read_text().splitlines()
    if not selections:
        hexchat.prnt("[Search DCC] Selection file empty.")
        return hexchat.EAT_ALL

    def worker():
        session_id = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        with open(HISTORY_FILE, "a") as f:
            f.write(f"=== SESSION {session_id} ===\n")
            for line in selections:
                f.write(f"{line}\n")
            f.write("=== END SESSION ===\n")

        for line in selections:
            hexchat.command(f"say {line}")
            time.sleep(0.5)

        cleanup_background()
        hexchat.prnt(f"[Search DCC] Session {session_id} sent.")

    threading.Thread(target=worker, daemon=True).start()
    return hexchat.EAT_ALL

# -----------------------------
# /sc — Discard staged selections & cleanup
# -----------------------------
def sc_cmd(word, word_eol, userdata):
    cleanup_background()
    hexchat.prnt("[Search DCC] All staged selections and temporary files discarded.")

# -----------------------------
# /sv — Verify latest session (STRICT)
# -----------------------------
def sv_cmd(word, word_eol, userdata):
    if not HISTORY_FILE.exists():
        hexchat.prnt("[Search DCC] No history found.")
        return hexchat.EAT_ALL

    lines = HISTORY_FILE.read_text().splitlines()

    sessions = []
    current = None

    for line in lines:
        if line.startswith("=== SESSION"):
            current = {"id": line.split()[2], "raw": []}
        elif line.startswith("=== END SESSION"):
            if current:
                sessions.append(current)
                current = None
        elif current:
            current["raw"].append(line)

    if not sessions:
        hexchat.prnt("[Search DCC] No sessions found.")
        return hexchat.EAT_ALL

    session = sessions[-1]

    VALID_EXT = {".pdf", ".epub", ".mobi", ".azw3"}

    downloaded = {}
    for f in DOWNLOAD_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in VALID_EXT:
            downloaded[canon_compare(f.name)] = f.name

    missing = []
    found = []

    for raw in session["raw"]:
        wanted = extract_requested_filename(raw)
        wanted_key = canon_compare(wanted)

        if wanted_key in downloaded:
            found.append((wanted, downloaded[wanted_key]))
        else:
            missing.append(wanted)

    hexchat.prnt(f"[Search DCC] Summary for session {session['id']}:")

    if not missing:
        hexchat.prnt(
            f"[Search DCC] ✅ All {len(session['raw'])} files from the latest session are downloaded!"
        )
        return hexchat.EAT_ALL

    hexchat.prnt(f"  ✅ Downloaded: {len(found)}")
    hexchat.prnt(f"  ❌ Missing: {len(missing)}")
    hexchat.prnt("━" * 50)

    for m in missing:
        hexchat.prnt(f" 📍 {m}")

    hexchat.prnt("━" * 50)
    return hexchat.EAT_ALL


# -----------------------------
# Cleanup
# -----------------------------
def save_state(zip_path, extract_dir):
    with open(STATE_FILE, "a") as f:
        f.write(f"ZIP|{zip_path}\n")
        f.write(f"DIR|{extract_dir}\n")

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

def cleanup_background():
    threading.Thread(target=cleanup_all, daemon=True).start()

# -----------------------------
# Register commands
# -----------------------------
hexchat.hook_command("ss", ss_cmd)
hexchat.hook_command("se", se_cmd)
hexchat.hook_command("sd", sd_cmd)
hexchat.hook_command("sv", sv_cmd)

hexchat.prnt(f"{__module_name__} v{__module_version__} loaded with commands /ss /se /sd /sc /sv")
