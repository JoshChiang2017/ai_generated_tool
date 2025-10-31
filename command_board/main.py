import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, List, Tuple
import argparse
from action_logger import get_logger

try:
    from core import CommandBuilder
except ImportError:
    CommandBuilder = None  # type: ignore

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'command_config.json')

def resolve_log_path(settings: Dict[str, Any]) -> str:
    """Anchor log file to script directory if relative."""
    script_dir = os.path.dirname(__file__)
    raw = settings.get('logFile') if isinstance(settings, dict) else None
    if not raw:
        return os.path.join(script_dir, 'command_board_actions.log')
    if os.path.isabs(raw):
        return raw
    return os.path.join(script_dir, raw)

class CommandBoardApp(tk.Tk):
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        settings = config.get('settings', {})
        self.title(settings.get('windowTitle', 'Command Board'))
        self.config_data = config
        self.button_width = settings.get('buttonWidth', 30)
        self.close_on_action = settings.get('closeOnAction', True)
        log_file = resolve_log_path(settings)
        self.logger = get_logger(log_file)
        self.logger.log('APP_START', 'Application initialized', status='INFO')
        self._build_ui()

    def _build_ui(self):
        # Removed top-level reload/open controls per user request
        spacer = ttk.Frame(self)
        spacer.pack(fill='x', padx=8, pady=(4,0))

        # Notebook for groups
        notebook = ttk.Notebook(self)
        notebook.pack(fill='both', expand=True, padx=8, pady=8)

        for group in self.config_data.get('groups', []):
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=group.get('name', 'Group'))
            desc = group.get('description')
            if desc:
                ttk.Label(frame, text=desc, foreground='#555').pack(anchor='w', padx=6, pady=(6,2))
            # Scrollable canvas if many buttons
            canvas = tk.Canvas(frame)
            scrollbar = ttk.Scrollbar(frame, orient='vertical', command=canvas.yview)
            inner = ttk.Frame(canvas)
            inner.bind('<Configure>', lambda e, c=canvas: c.configure(scrollregion=c.bbox('all')))
            canvas.create_window((0,0), window=inner, anchor='nw')
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            subgroups = group.get('subgroups')
            if subgroups:
                for sg in subgroups:
                    sg_name = sg.get('name', 'subgroup')
                    header = ttk.Label(inner, text=sg_name, font=('Segoe UI', 10, 'bold'))
                    header.pack(anchor='w', padx=6, pady=(12,4))
                    for cmd in sg.get('commands', []):
                        if not cmd.get('enabled', True):
                            continue
                        label = cmd.get('label', 'Unnamed')
                        actions = cmd.get('actions', [])
                        row = ttk.Frame(inner)
                        row.pack(anchor='w', fill='x', padx=12, pady=3)
                        ttk.Label(row, text=label, width=self.button_width, anchor='w').pack(side='left')
                        for act in actions:
                            act_name = act.get('name', 'action')
                            btn = ttk.Button(row, text=act_name, width=6,
                                             command=lambda a=act, base=cmd, lab=(group.get('name','Group'), sg_name, label, act_name): self.execute_action(base, a, lab))
                            btn.pack(side='left', padx=(6 if act is actions[0] else 2,2))
            else:
                for cmd in group.get('commands', []):
                    if not cmd.get('enabled', True):
                        continue
                    label = cmd.get('label', 'Unnamed')
                    actions = cmd.get('actions', [])
                    row = ttk.Frame(inner)
                    row.pack(anchor='w', fill='x', padx=6, pady=4)
                    ttk.Label(row, text=label, width=self.button_width, anchor='w').pack(side='left')
                    for act in actions:
                        act_name = act.get('name', 'action')
                        btn = ttk.Button(row, text=act_name, width=6,
                                         command=lambda a=act, base=cmd, lab=(group.get('name','Group'), None, label, act_name): self.execute_action(base, a, lab))
                        btn.pack(side='left', padx=(6 if act is actions[0] else 2,2))

    def execute_action(self, base_cmd: Dict[str, Any], action: Dict[str, Any], label_tuple=None):
        path = base_cmd.get('path')
        act_name = action.get('name', 'action')
        self.logger.log('BUTTON_CLICK', f'{label_tuple} -> {act_name}', status='INFO')
        # Git Bash action
        if act_name == 'bash' or action.get('type') == 'git-bash':
            result = self.open_git_bash(base_cmd, label_tuple)
            if result and self.close_on_action:
                self.logger.log('APP_CLOSE', 'Auto-close after bash action', status='INFO')
                self.after(100, self.destroy)
            return result
        exe = action.get('executable')
        args_template = action.get('argsTemplate', '')
        if not exe or not path:
            self.logger.log('EXECUTE', f'MISSING executable/path {action}', status='ERROR')
            messagebox.showerror('Error', f'Missing executable/path for action {act_name}')
            return
        final_args = args_template.format(path=path)
        full_cmd = f"{exe} {final_args}".strip()
        try:
            subprocess.Popen(full_cmd, shell=True)
            self.logger.log('EXECUTE', f'{full_cmd}', status='OK')
            if self.close_on_action:
                self.logger.log('APP_CLOSE', 'Auto-close after execute action', status='INFO')
                self.after(100, self.destroy)
        except FileNotFoundError:
            self.logger.log('EXECUTE', f'Executable not found: {exe}', status='ERROR')
            messagebox.showerror('Execution Failed', f'Executable not found: {exe}')
        except Exception as e:
            self.logger.log('EXECUTE', f'{full_cmd} ERROR {e}', status='ERROR')
            messagebox.showerror('Execution Failed', str(e))

    # Removed reload_config and open_config per user request

    def open_git_bash(self, cmd: Dict[str, Any], label_tuple=None):
        path = cmd.get('path')
        if not path:
            self.logger.log('GIT_BASH', 'Missing path', status='ERROR')
            messagebox.showerror('Git Bash', 'Missing path for Git Bash launch')
            return False
        git_bash_exe = self._resolve_git_bash()
        if not git_bash_exe:
            self.logger.log('GIT_BASH', 'Executable not found', status='ERROR')
            messagebox.showerror('Git Bash', 'Could not locate Git Bash executable. Set settings.gitBashExecutable or install Git for Windows.')
            return False
        try:
            # Prefer direct invocation without shell; Git Bash supports --cd argument.
            cmd_line = [git_bash_exe, f'--cd={path}']
            subprocess.Popen(cmd_line)
            self.logger.log('GIT_BASH', f'{git_bash_exe} --cd={path}', status='OK')
            return True
        except Exception as e:
            self.logger.log('GIT_BASH', f'ERROR {e}', status='ERROR')
            messagebox.showerror('Git Bash Launch Failed', str(e))
            return False

    def _resolve_git_bash(self) -> str:
        # Priority: config setting -> common install paths
        setting_path = self.config_data.get('settings', {}).get('gitBashExecutable')
        candidates = []
        if setting_path:
            candidates.append(setting_path)
        candidates.extend([
            r"C:\Program Files\Git\git-bash.exe",
            r"C:\Program Files (x86)\Git\git-bash.exe"
        ])
        for c in candidates:
            if c and os.path.exists(c):
                return c
        return ''


def load_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f'Config file not found: {path}')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def iter_commands(config: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    out: List[Tuple[str, Dict[str, Any]]] = []
    for group in config.get('groups', []):
        gname = group.get('name', 'Group')
        subgroups = group.get('subgroups')
        if subgroups:
            for sg in subgroups:
                sgname = sg.get('name', 'subgroup')
                for cmd in sg.get('commands', []):
                    if not cmd.get('enabled', True):
                        continue
                    label = cmd.get('label', 'Unnamed')
                    for act in cmd.get('actions', []):
                        act_name = act.get('name', 'action')
                        full_label = f"{gname}/{sgname}/{label}/{act_name}"
                        out.append((full_label, {'_base': cmd, '_action': act}))
        else:
            for cmd in group.get('commands', []):
                if not cmd.get('enabled', True):
                    continue
                label = cmd.get('label', 'Unnamed')
                for act in cmd.get('actions', []):
                    act_name = act.get('name', 'action')
                    full_label = f"{gname}/{label}/{act_name}"
                    out.append((full_label, {'_base': cmd, '_action': act}))
    return out

def build_command_string(cmd_def: Dict[str, Any]) -> str:
    if CommandBuilder:
        builder = CommandBuilder(cmd_def)
        return builder.build()
    exe = cmd_def.get('executable')
    path = cmd_def.get('path')
    template = cmd_def.get('argsTemplate', '')
    if not exe or not path:
        raise ValueError('Executable or path missing')
    return f"{exe} {template.format(path=path)}".strip()

def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Command Board GUI / CLI')
    parser.add_argument('config', nargs='?', default=None, help='Path to config JSON file')
    parser.add_argument('-l', '--list', action='store_true', help='List all commands and exit')
    parser.add_argument('-r', '--run', metavar='LABEL', help='Run a command by its label')
    parser.add_argument('-d', '--dry-run', action='store_true', help='Show command string without executing')
    parser.add_argument('-c', '--auto-close', action='store_true', help='Auto-close GUI after successful action (override config)')
    return parser.parse_args(argv[1:])

def main(argv: List[str]):
    args = parse_args(argv)
    config_path = args.config or CONFIG_FILE
    try:
        config = load_config(config_path)
    except Exception as e:
        print(f'Failed to load config: {e}', file=sys.stderr)
        sys.exit(1)

    if args.list:
        print('Available commands:')
        for label, pair in iter_commands(config):
            base = pair.get('_base', {})
            action = pair.get('_action', {})
            path = base.get('path')
            if action.get('type') == 'git-bash' or action.get('name') == 'bash':
                cmd_str = f'git-bash --cd={path}'
            else:
                try:
                    cmd_str = build_command_string({'executable': action.get('executable'), 'argsTemplate': action.get('argsTemplate'), 'path': path})
                except Exception as e:
                    cmd_str = f'<invalid: {e}>'
            print(f' - {label}: {cmd_str}')
        return
    if args.run:
        target_label = args.run.strip()
        matches = [c for c in iter_commands(config) if c[0] == target_label]
        if not matches:
            print(f'No command with label "{target_label}" found.', file=sys.stderr)
            sys.exit(2)
        label, pair = matches[0]
        base = pair.get('_base', {})
        action = pair.get('_action', {})
        path = base.get('path')
        if action.get('type') == 'git-bash' or action.get('name') == 'bash':
            cmd_str = f'git-bash --cd={path}'
            if args.dry_run:
                print(f'DRY RUN: {cmd_str}')
                logger = get_logger(resolve_log_path(config.get('settings', {})))
                logger.log('CLI_DRY_RUN', f'{label} -> {cmd_str}', status='INFO')
                return
            gb_exe = CommandBoardApp(config)._resolve_git_bash()
            if not gb_exe:
                print('Git Bash executable not found', file=sys.stderr)
                sys.exit(3)
            try:
                subprocess.Popen([gb_exe, f'--cd={path}'])
                print(f'Executed: {cmd_str}')
                logger = get_logger(resolve_log_path(config.get('settings', {})))
                logger.log('CLI_EXECUTE', f'{label} -> {cmd_str}', status='OK')
            except Exception as e:
                print(f'Execution failed: {e}', file=sys.stderr)
                logger = get_logger(resolve_log_path(config.get('settings', {})))
                logger.log('CLI_EXECUTE', f'{label} ERROR {e}', status='ERROR')
                sys.exit(3)
            return
        cmd_str = build_command_string({'executable': action.get('executable'), 'argsTemplate': action.get('argsTemplate'), 'path': path})
        if args.dry_run:
            print(f'DRY RUN: {cmd_str}')
            logger = get_logger(resolve_log_path(config.get('settings', {})))
            logger.log('CLI_DRY_RUN', f'{label} -> {cmd_str}', status='INFO')
            return
        try:
            subprocess.Popen(cmd_str, shell=True)
            print(f'Executed: {cmd_str}')
            logger = get_logger(resolve_log_path(config.get('settings', {})))
            logger.log('CLI_EXECUTE', f'{label} -> {cmd_str}', status='OK')
        except Exception as e:
            print(f'Execution failed: {e}', file=sys.stderr)
            logger = get_logger(resolve_log_path(config.get('settings', {})))
            logger.log('CLI_EXECUTE', f'{label} ERROR {e}', status='ERROR')
            sys.exit(3)
        return

    # If auto-close flag provided, force closeOnAction true
    if getattr(args, 'auto_close', False):
        config.setdefault('settings', {})['closeOnAction'] = True
    app = CommandBoardApp(config)
    app.mainloop()

if __name__ == '__main__':
    main(sys.argv)
