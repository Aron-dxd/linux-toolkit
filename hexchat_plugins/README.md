# DCC Search, Stage and Download Plugin

**Version:** 3.0  
**Description:** Stage search results from HexChat DCC transfers using FZF, review and edit selections, commit to chat, maintain a history of downloads, and perform strict verification.

---

## Features

- **`/ss <query>`** — Search via DCC bot, wait for ZIP, and stage results in FZF.
- **`/se`** — Review and edit staged selections before committing.
- **`/sd`** — Commit staged selections: send to chat, log in history, and cleanup temporary files.
- **`/sv`** — Perform strict verification of downloads of last session.
- **`/sc`** — Discard all staged selections and cleanup.

**Additional Features:**

- `history.txt` stores history with session ID.
- Uses **Kitty** + **FZF** for interactive selection.

---

## Installation

1. Copy `ssclient.py` to HexChat’s addons folder:

```bash
~/.config/hexchat/addons/
```

2. Ensure the following are installed and available in your `PATH`:

- [Kitty Terminal](https://sw.kovidgoyal.net/kitty/)
- [FZF](https://github.com/junegunn/fzf)

3. Start HexChat and load the python file:
```
py load ssclient.py
```
You should see `[Search DCC] ver 3.0 loaded with commands /ss /se /sd /sv /sc`

---

## Usage

### Stage a Search

```text
/ss <query>
```

Example:

```text
/ss moby dick
```

### Review/Edit Staged Selections

```text
/se
```

### Commit to Chat, Log History and clear zip and extracted folders

```text
/sd
```

### Perform strict verification of last session downloads

```text
/sv
```

### Discard Staged Selections along with zip files and extracted folders

```text
/sc
```

---

## File Locations

- **Downloads:** `~/Downloads/ebooks/`
- **State files:** `~/Downloads/ebooks/state/`

  - `selections.txt` → Staged selections
  - `state.txt` → Tracks ZIPs and extracted directories
  - `history.txt` → Contains committed entries separated with session ID

---

## Hyprland Window Rules

To make FZF windows float and size nicely, add these to your `hyprland.conf`:

```text
windowrule {
  name = windowrule-SearchDCC
  float = on
  size = (monitor_w*0.85) (monitor_h*0.45)
  move = ((monitor_w*0.075)) ((monitor_h*0.05))
  center = 0
  match:class = ^(SearchDCC)$
}
```

> Adjust size and move parameters as needed.
> `class = ^(SearchDCC)$` ensures only the FZF windows created by the plugin are affected.

---

## Notes

- The plugin uses **Kitty** by default. You can change the terminal in the code if desired.
- Handles one new ZIP at a time; multiple simultaneous transfers may open multiple windows.
- Works with the latest HexChat versions on Linux.
