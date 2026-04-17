#!/usr/bin/env python3
"""Generate a commit title using Codex based on recent git history and current changes."""

import argparse
import re
import subprocess
import sys
from typing import List


DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_MAX_LEN = 72


def run_cmd(cmd: List[str], check: bool = True) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or f"command failed: {' '.join(cmd)}"
        raise RuntimeError(err)
    return proc.stdout


def in_git_repo() -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def get_history(limit: int) -> List[str]:
    out = run_cmd(["git", "log", f"-n{limit}", "--pretty=format:%s"], check=False)
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    return lines


def get_changes(staged: bool, include_patch: bool, patch_lines: int) -> str:
    base = ["git", "diff", "--cached"] if staged else ["git", "diff"]

    name_status = run_cmd(base + ["--name-status"], check=False).strip()
    stat = run_cmd(base + ["--stat"], check=False).strip()

    parts = []
    if name_status:
        parts.append("Name status:\n" + name_status)
    if stat:
        parts.append("Diff stat:\n" + stat)

    if include_patch:
        patch = run_cmd(base + [f"-U{patch_lines}"], check=False).strip()
        if patch:
            parts.append("Patch:\n" + patch)

    return "\n\n".join(parts).strip()


def get_best_changes(use_unstaged: bool, include_patch: bool, patch_lines: int) -> str:
    if use_unstaged:
        return get_changes(
            staged=False,
            include_patch=include_patch,
            patch_lines=patch_lines,
        )

    staged_changes = get_changes(
        staged=True,
        include_patch=include_patch,
        patch_lines=patch_lines,
    )
    if staged_changes:
        return staged_changes

    return get_changes(
        staged=False,
        include_patch=include_patch,
        patch_lines=patch_lines,
    )


def build_prompt(history: List[str], changes: str, max_len: int) -> str:
    history_text = "\n".join(f"- {line}" for line in history) if history else "- (no prior commits)"
    changes_text = changes if changes else "(no changes found)"

    return (
        "You generate git commit titles.\n"
        "Task: Infer the style from recent commit subjects and produce one title for the current changes.\n"
        f"Rules:\n"
        f"1) Output exactly one line\n"
        f"2) Maximum {max_len} characters\n"
        "3) No surrounding quotes\n"
        "4) No trailing period\n"
        "5) Match dominant style from history (prefixes, casing, tense, tone)\n"
        "\n"
        "Recent commit subjects:\n"
        f"{history_text}\n"
        "\n"
        "Current changes:\n"
        f"{changes_text}\n"
    )


def sanitize_title(text: str, max_len: int) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("empty output from codex")

    title = lines[0]
    if len(lines) > 1:
        raise ValueError("codex output was not single-line")

    title = re.sub(r"\s+", " ", title).strip().strip('"\'')
    if title.endswith("."):
        title = title[:-1].rstrip()

    if not title:
        raise ValueError("empty title after sanitization")
    if len(title) > max_len:
        raise ValueError(f"title exceeds {max_len} characters")
    if "\n" in title:
        raise ValueError("title contains newline")

    return title


def build_codex_cmd(prompt: str, model: str, oss: bool, ephemeral: bool, cd: str) -> List[str]:
    cmd = ["codex", "exec"]
    if ephemeral:
        cmd.append("--ephemeral")
    if model:
        cmd.extend(["-m", model])
    if oss:
        cmd.append("--oss")
    if cd:
        cmd.extend(["-C", cd])
    cmd.append(prompt)
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a commit title using codex exec and git context."
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Codex model name")
    parser.add_argument("--oss", action="store_true", help="Use OSS provider via codex --oss")
    parser.add_argument(
        "--history-limit",
        type=int,
        default=30,
        help="Number of recent commit subjects to infer style",
    )
    parser.add_argument(
        "--max-len",
        type=int,
        default=DEFAULT_MAX_LEN,
        help="Maximum commit title length",
    )
    parser.add_argument(
        "--include-patch",
        action="store_true",
        help="Include textual patch in prompt (higher token usage)",
    )
    parser.add_argument(
        "--patch-lines",
        type=int,
        default=0,
        help="Context lines for patch when --include-patch is used",
    )
    parser.add_argument(
        "--unstaged",
        action="store_true",
        help="Use unstaged diff instead of staged diff",
    )
    parser.add_argument(
        "--ephemeral",
        action="store_true",
        default=True,
        help="Run codex in ephemeral mode (default: enabled)",
    )
    parser.add_argument(
        "--no-ephemeral",
        dest="ephemeral",
        action="store_false",
        help="Disable codex ephemeral mode",
    )
    parser.add_argument(
        "--fallback",
        default="chore: update files",
        help="Fallback title if codex output fails validation",
    )
    parser.add_argument(
        "--print-prompt",
        action="store_true",
        help="Print prompt to stderr for debugging",
    )

    args = parser.parse_args()

    if not in_git_repo():
        print("error: not inside a git repository", file=sys.stderr)
        return 2

    history = get_history(args.history_limit)
    changes = get_best_changes(
        use_unstaged=args.unstaged,
        include_patch=args.include_patch,
        patch_lines=args.patch_lines,
    )

    if not changes:
        print("error: no staged or unstaged changes found", file=sys.stderr)
        return 2

    prompt = build_prompt(history, changes, args.max_len)
    if args.print_prompt:
        print(prompt, file=sys.stderr)

    cmd = build_codex_cmd(
        prompt=prompt,
        model=args.model,
        oss=args.oss,
        ephemeral=args.ephemeral,
        cd=".",
    )

    try:
        raw = run_cmd(cmd)
        title = sanitize_title(raw, args.max_len)
    except Exception as exc:
        print(f"warning: {exc}; using fallback", file=sys.stderr)
        title = args.fallback[: args.max_len].rstrip(".")

    print(title)
    return 0


if __name__ == "__main__":
    sys.exit(main())
