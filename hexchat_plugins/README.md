# Search DCC Staged FZF

**Version:** 2.9  
**Description:** Stage search results from HexChat DCC transfers using FZF, review and edit selections, commit to chat, and maintain a history of downloads.

---

## Features

- **`/ss <query>`** — Search via DCC bot, wait for ZIP, and stage results in FZF.
- **`/se`** — Review and edit staged selections before committing.
- **`/sd`** — Commit staged selections: send to chat, log in history, and cleanup temporary files.
- **`/sc`** — Discard all staged selections and cleanup.

**Additional Features:**

- Maintains the last 50 entries in `history.txt`.
- Uses **Kitty** + **FZF** for interactive selection.

---

## Installation

1. Copy `search_dcc_staged_fzf.py` to HexChat’s addons folder:

```bash
~/.config/hexchat/addons/
```

2. Ensure the following are installed and available in your `PATH`:

- [Kitty Terminal](https://sw.kovidgoyal.net/kitty/)
- [FZF](https://github.com/junegunn/fzf)

3. Start HexChat. You should see:

```
[Search DCC] Loaded: /ss /se /sd /sc
```

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

### Commit to Chat and Log History

```text
/sd
```

### Discard Staged Selections

```text
/sc
```

---

## File Locations

- **Downloads:** `~/Downloads/ebooks/`
- **State files:** `~/Downloads/ebooks/state/`

  - `selections.txt` → Staged selections
  - `state.txt` → Tracks ZIPs and extracted directories
  - `history.txt` → Last 50 committed entries

---

## Hyprland Window Rules

To make FZF windows float and size nicely, add these to your `hyprland.conf`:

```text
windowrulev2 = float,class:^(SearchDCC)$
windowrulev2 = size 85% 45%,class:^(SearchDCC)$
windowrulev2 = move 7.5% 5%,class:^(SearchDCC)$
windowrulev2 = center 0,class:^(SearchDCC)$
```

> Adjust size and move parameters as needed.
> `class:^(SearchDCC)$` ensures only the plugin’s FZF windows are affected.

---

## Notes

- The plugin uses **Kitty** by default. You can change the terminal in the code if desired.
- Handles one new ZIP at a time; multiple simultaneous transfers may open multiple windows.
- Works with the latest HexChat versions on Linux.
