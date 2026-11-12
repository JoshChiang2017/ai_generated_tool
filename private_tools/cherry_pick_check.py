#!/usr/bin/env python3
"""
List commits that are not aligned between two branches (e.g. master vs. a release branch).

Commits are considered aligned when:
  * their patch content is identical on both sides (git --cherry-pick / patch-id), or
  * one side's commit message contains "(cherry picked from commit <hash>)" pointing to the other.

Commits recorded in the config file are treated as "don't care" and hidden
(unless -a/--all is given).

Config file format (YAML, '#' comments allowed):
    "816ee803":
      reason: RC integration
Abbreviated hashes are allowed (prefix match).

Usage:
    python cherry_pick_check.py <repo_path> <branch1> <branch2> [-c config_file] [-a] [-m]
    (config_file defaults to cherry_pick_check.yaml next to this script)
"""

import os
import re
import json
import sys
import argparse
import subprocess
from typing import Dict, List, Optional

import yaml

# Edit-mode key -> reason
PRESET_REASONS = {
    'r': 'RC integration',
    't': 'Tag operation',
    'k': 'Kernel update',
}

DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cherry_pick_check.yaml')

CHERRY_RE =re.compile(r'\(cherry picked from commit ([0-9a-fA-F]{7,40})\)')
FIELD_SEP = '\x1f'
RECORD_SEP = '\x1e'


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------
def run_git(repo: str, args: List[str]) -> str:
    result = subprocess.run(
        ['git'] + args,
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8',
        errors='replace',
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def get_diff_commits(repo: str, branch1: str, branch2: str) -> List[Dict]:
    """Return commits existing on only one side (patch-id equivalent commits removed)."""
    fmt = FIELD_SEP.join(['%m', '%H', '%h', '%ad', '%an', '%s', '%B']) + RECORD_SEP
    out = run_git(repo, [
        'log', '--left-right', '--cherry-pick', '--no-merges', '--date=short',
        f'--pretty=format:{fmt}', f'{branch1}...{branch2}',
    ])
    commits = []
    for rec in out.split(RECORD_SEP):
        rec = rec.strip('\n')
        if not rec:
            continue
        mark, full, short, date, author, subject, body = rec.split(FIELD_SEP, 6)
        commits.append({
            'side': branch1 if mark == '<' else branch2,
            'mark': mark,
            'hash': full,
            'short': short,
            'date': date,
            'author': author,
            'subject': subject,
            'body': body,
            'picked_from': [h.lower() for h in CHERRY_RE.findall(body)],
        })
    return commits


def remove_cherry_picked_pairs(commits: List[Dict]) -> List[Dict]:
    """Drop pairs linked by 'cherry picked from commit X' (e.g. picked with conflicts)."""
    by_side = {'<': [c for c in commits if c['mark'] == '<'],
               '>': [c for c in commits if c['mark'] == '>']}
    aligned = set()
    for c in commits:
        other = by_side['>' if c['mark'] == '<' else '<']
        for src in c['picked_from']:
            for o in other:
                if o['hash'].startswith(src):
                    aligned.add(c['hash'])
                    aligned.add(o['hash'])
    return [c for c in commits if c['hash'] not in aligned]


def show_commit(repo: str, commit_hash: str) -> str:
    return run_git(repo, ['show', '--no-patch', '--no-color', '--date=iso', commit_hash])


# ---------------------------------------------------------------------------
# Config file
# ---------------------------------------------------------------------------
def load_config(path: str) -> Dict[str, str]:
    """Load {hash: {reason: ...}} from YAML. BaseLoader keeps every scalar a string,
    so all-digit short hashes are not turned into integers."""
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.load(f, Loader=yaml.BaseLoader) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping of <hash>: {{reason: ...}}")
    entries: Dict[str, str] = {}
    for key, value in data.items():
        reason = value.get('reason', '') if isinstance(value, dict) else (value or '')
        entries[str(key).strip().lower()] = reason
    return entries


def append_config(path: str, commit: Dict, reason: str) -> None:
    """Append one entry as text so existing content and comments stay untouched."""
    needs_newline = False
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, 'rb') as f:
            f.seek(-1, os.SEEK_END)
            needs_newline = f.read(1) != b'\n'
    with open(path, 'a', encoding='utf-8') as f:
        if needs_newline:
            f.write('\n')
        # json.dumps yields a valid YAML double-quoted string (handles ':', '#', quotes)
        f.write(f"\"{commit['hash']}\":\n  reason: {json.dumps(reason, ensure_ascii=False)}\n")


def lookup_reason(config: Dict[str, str], commit_hash: str) -> Optional[str]:
    for key, reason in config.items():
        if commit_hash.lower().startswith(key):
            return reason
    return None


# ---------------------------------------------------------------------------
# Single-key input
# ---------------------------------------------------------------------------
def getch() -> str:
    if not sys.stdin.isatty():  # piped input: read a line, use its first char
        line = sys.stdin.readline()
        if not line:
            raise EOFError
        return line[0] if line.strip() else '\n'
    try:
        import msvcrt  # Windows
        ch = msvcrt.getwch()
        if ch in ('\x00', '\xe0'):  # special key prefix, swallow next code
            msvcrt.getwch()
            return ''
    except ImportError:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    if ch == '\x03':
        raise KeyboardInterrupt
    return ch


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def print_table(commits: List[Dict], branch1: str, branch2: str) -> None:
    for mark, side in (('<', branch1), ('>', branch2)):
        rows = [c for c in commits if c['mark'] == mark]
        if not rows:
            continue
        print(f"\n=== Only in {side} ({len(rows)}) ===")
        for c in rows:
            reason = c.get('reason')
            tag = f"  [{reason}]" if reason is not None else ''
            print(f"  {c['short']}  {c['date']}  {c['author'][:16]:<16}  {c['subject']}{tag}")


def edit_mode(repo: str, commits: List[Dict], config_path: str) -> None:
    todo = [c for mark in ('<', '>') for c in commits if c['mark'] == mark and c.get('reason') is None]
    if not todo:
        print("Nothing to mark.")
        return
    prompt = '  '.join([f"({k.upper()}) {v}" for k, v in PRESET_REASONS.items()]
                       + ['(O) Other', '(S/Enter) Skip']) + '  > '
    print(f"\n{len(todo)} unmarked commit(s). Press Ctrl+C to quit at any time.")
    for i, c in enumerate(todo, 1):
        print('\n' + '=' * 78)
        print(f"[{i}/{len(todo)}]  only in: {c['side']}")
        print('=' * 78)
        print(show_commit(repo, c['hash']).rstrip())
        print('-' * 78)
        while True:
            print(prompt, end='', flush=True)
            ch = getch().lower()
            print(ch)
            if ch in PRESET_REASONS:
                reason = PRESET_REASONS[ch]
            elif ch == 'o':
                reason = input("Reason: ").strip()
                if not reason:
                    print("Empty reason, try again.")
                    continue
            elif ch in ('s', '\r', '\n'):
                print("Skipped.")
                break
            else:
                continue
            append_config(config_path, c, reason)
            c['reason'] = reason
            print(f"Marked {c['short']} as: {reason}")
            break
    print("\nAll commits processed.")


# ---------------------------------------------------------------------------
def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except AttributeError:
            pass

    parser = argparse.ArgumentParser(
        description='List commits not aligned between two branches, ignoring ones recorded in a config file.')
    parser.add_argument('path', help='Git repository path')
    parser.add_argument('branch1', help='First branch (e.g. master)')
    parser.add_argument('branch2', help='Second branch')
    parser.add_argument('-c', '--config', default=DEFAULT_CONFIG,
                        help='Config YAML file (created if missing). '
                             f'Default: {os.path.basename(DEFAULT_CONFIG)} next to this script')
    parser.add_argument('-a', '--all', action='store_true', help='Also list commits recorded in config, with reason')
    parser.add_argument('-m', '--modify', action='store_true', help='Interactively mark unaligned commits')
    args = parser.parse_args()

    repo = os.path.abspath(args.path)
    try:
        commits = remove_cherry_picked_pairs(get_diff_commits(repo, args.branch1, args.branch2))
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1

    try:
        config = load_config(args.config)
    except (yaml.YAMLError, ValueError) as e:
        print(f"Failed to parse config {args.config}:\n{e}", file=sys.stderr)
        return 1
    for c in commits:
        c['reason'] = lookup_reason(config, c['hash'])

    shown = commits if args.all else [c for c in commits if c['reason'] is None]
    ignored = len(commits) - len([c for c in commits if c['reason'] is None])
    print(f"Repo: {repo}")
    print(f"Config: {os.path.abspath(args.config)}")
    print(f"Compare: {args.branch1} <-> {args.branch2}   unaligned: {len(commits)}   "
          f"recorded in config: {ignored}   shown: {len(shown)}")
    if shown:
        print_table(shown, args.branch1, args.branch2)
    else:
        print("\nAll commits are aligned (or recorded in config).")

    if args.modify:
        try:
            edit_mode(repo, commits, args.config)
        except (KeyboardInterrupt, EOFError):
            print("\nAborted. Marks made so far have been saved.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
