---
name: commit-title
description: Generate a one-line git commit title from the current repository's staged changes while matching recent commit style.
model: haiku
allowed-tools: Bash(python3 *)
---

# Commit Title

Generate exactly one git commit title for the current repository.

Run:

```bash
python3 "$HOME/.claude/skills/commit-title/scripts/generate_commit_title.py"
```

Default behavior:

- Uses staged changes, falling back to unstaged changes when nothing is staged.
- Infers style from recent commit subjects.
- Calls `codex exec --ephemeral -m gpt-5.4-mini`.
- Prints the title on stdout.
