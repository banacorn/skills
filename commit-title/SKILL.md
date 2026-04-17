---
name: commit-title
description: Generate a one-line git commit title from the current repository's staged or unstaged changes, then offer Accept and commit, Revise, or Cancel actions.
model: haiku
allowed-tools: Bash(python3 *), Bash(git status *), Bash(git add *), Bash(git commit *)
---

# Commit Title

Generate one git commit title for the current repository, then ask the user what to do with it.

Run:

```bash
python3 "$HOME/.claude/skills/commit-title/scripts/generate_commit_title.py"
```

After the script prints a title, use `AskUserQuestion` with previews to present exactly these three single-select choices to the user:

1. Accept and commit
2. Revise
3. Cancel

Question configuration:

- question: `Generated commit title -- what would you like to do?`
- header: `Commit`
- multiSelect: `false`
- option 1 label: `Accept and commit`, description: `Stage all changes and commit with this title`, preview: the generated title text
- option 2 label: `Revise`, description: `Revise the generated title`
- option 3 label: `Cancel`, description: `Stop without committing`

Use a preview on the `Accept and commit` option so the generated title appears in the artifacts UI preview pane before the user decides. Do not use `multiSelect: true`; previews only work for single-select questions. Do not invent unsupported per-option fields.

Action behavior:

- `Accept and commit`: run `git add .` and then `git commit -m "<generated title>"`.
- `Revise`: check `annotations["Generated commit title -- what would you like to do?"].notes`. If non-empty, treat the note as the revision instruction directly. If empty, ask the user `What would you like to change?` before revising. Then generate a new title incorporating the feedback and show the same three choices again.
- `Cancel`: stop without running git commands.

If the artifacts UI is unavailable, ask the user to choose by typing `1`, `2`, or `3`.

Default behavior:

- Uses staged changes, falling back to unstaged changes when nothing is staged.
- Infers style from recent commit subjects.
- Calls `codex exec --ephemeral -m gpt-5.4-mini`.
- Prints the title on stdout.
