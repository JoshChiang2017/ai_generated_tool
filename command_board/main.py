import json
import os
import subprocess
import sys
import shutil
import tkinter as tk
from tkinter import ttk, messagebox
# Removed unused import (test)
from typing import Dict, Any, List, Tuple, Set
import argparse
from action_logger import get_logger

# Tooltip helper (re-added)
class _Tooltip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind('<Enter>', self._show)
        widget.bind('<Leave>', self._hide)

    def _show(self, _event=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 6
        y = self.widget.winfo_rooty() + 4
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f'+{x}+{y}')
        lbl = tk.Label(tw, text=self.text, background='#ffffe0', borderwidth=1, relief='solid', font=('Segoe UI', 9))
        lbl.pack(ipadx=4, ipady=2)

    def _hide(self, _event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None

def create_tooltip(widget, text: str):
    _Tooltip(widget, text)

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
        # Top control bar (Test button moved right & de-emphasized)
        control_bar = ttk.Frame(self)
        control_bar.pack(fill='x', padx=8, pady=(6, 0))
        # Left spacer (remove window title from body)
        ttk.Frame(control_bar).pack(side='left', padx=4)
        # Right side container
        right_box = ttk.Frame(control_bar)
        right_box.pack(side='right')
        test_btn = ttk.Button(right_box, text='⚙', width=3, command=self.run_tests)
        test_btn.pack(side='right', padx=(4,0))
        # Tooltip for test button
        create_tooltip(test_btn, 'TEST')

        # === Notebook Style Enhancement for clearer tab separation ===
        style = ttk.Style(self)
        current_theme = style.theme_use()
        # Configure custom notebook & tab style
        style.configure('CB.TNotebook', tabmargins=(8, 4, 8, 0))  # left/top/right/bottom extra spacing
        style.configure('CB.TNotebook.Tab', padding=(14, 6), borderwidth=1)
        # Use map to differentiate selected vs unselected
        style.map('CB.TNotebook.Tab',
                  background=[('selected', '#ffffff'), ('!selected', '#e6e6e6')],
                  foreground=[('selected', '#000000'), ('!selected', '#444444')])

        # Notebook for groups with custom style
        notebook = ttk.Notebook(self, style='CB.TNotebook')
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
            # Enable mouse wheel scrolling (Windows & cross-platform normalization)
            def _on_mousewheel(event, c=canvas):
                # Windows event.delta is +/-120 multiples
                delta = event.delta
                if delta == 0:
                    return
                # Negative goes down
                c.yview_scroll(int(-1*(delta/120)), 'units')
            # Windows / general '<MouseWheel>'
            canvas.bind_all('<MouseWheel>', _on_mousewheel)
            # Linux (X11) button-4/5
            canvas.bind_all('<Button-4>', lambda e, c=canvas: c.yview_scroll(-1, 'units'))
            canvas.bind_all('<Button-5>', lambda e, c=canvas: c.yview_scroll(1, 'units'))
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
        exe = resolve_executable(action, self.config_data, self.logger)
        args_template = action.get('argsTemplate', '')
        needs_path = '{path}' in args_template
        if not exe or (needs_path and not path):
            self.logger.log('EXECUTE', f'MISSING executable/path {action}', status='ERROR')
            messagebox.showerror('Error', f'Missing executable/path for action {act_name}')
            return
        final_args = args_template.format(path=path) if args_template else ''
        # Quote exe if contains spaces
        quoted_exe = f'"{exe}"' if ' ' in exe and not exe.startswith('"') else exe
        full_cmd = f"{quoted_exe} {final_args}".strip()
        try:
            # Use list form if no template shell expansions needed
            if ' ' in final_args or '%' in final_args:
                subprocess.Popen(full_cmd, shell=True)
            else:
                subprocess.Popen([exe] + ([final_args] if final_args else []))
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

    # ===================== Validation / Test Button =====================
    def run_tests(self):
        report = validate_config(self.config_data, logger=self.logger)
        self.logger.log('CONFIG_TEST', 'started', status='INFO')
        missing_paths = report['missing_paths']
        missing_execs = report['missing_executables']
        total_cmds = report['total_commands']
        total_actions = report['total_actions']
        # Log each missing item individually for easier grep
        # Already logged each check; still log aggregate missing items for quick grep
        for p in sorted(missing_paths):
            self.logger.log('CONFIG_TEST_PATH_MISSING', p, status='WARN')
        for e in sorted(missing_execs):
            self.logger.log('CONFIG_TEST_EXEC_MISSING', e, status='WARN')
        lines: List[str] = []
        lines.append(f'Total commands: {total_cmds}')
        lines.append(f'Total actions: {total_actions}')
        lines.append(f'Missing paths: {len(missing_paths)}')
        for p in sorted(missing_paths):
            lines.append(f'  PATH ! {p}')
        lines.append(f'Missing executables: {len(missing_execs)}')
        for e in sorted(missing_execs):
            lines.append(f'  EXEC ! {e}')
        summary = '\n'.join(lines)
        status = 'OK' if not missing_paths and not missing_execs else 'WARN'
        self.logger.log('CONFIG_TEST_RESULT', summary.replace('\n', ' | '), status=status)
        if not missing_paths and not missing_execs:
            messagebox.showinfo('Config Test', 'All OK!\n\n' + summary)
        else:
            # Show detailed window
            win = tk.Toplevel(self)
            win.title('Config Test Report')
            txt = tk.Text(win, width=100, height=30)
            txt.pack(fill='both', expand=True)
            txt.insert('1.0', summary)
            txt.config(state='disabled')
            ttk.Button(win, text='Close', command=win.destroy).pack(pady=6)


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

def _collect_executable(action: Dict[str, Any]) -> str:
    exe = action.get('executable') or action.get('executableAlias')
    return exe or ''

def validate_config(config: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """Validate paths and executables referenced in config without creating GUI.
    Optionally logs each check (success or failure) if logger provided.
    Returns dict with sets of missing items and counts.
    Rules:
      - A command path must exist (file or directory) unless empty.
      - Executable is checked via shutil.which; special cases:
          * explorer: assumed available on Windows.
          * *.bat / *.cmd or absolute path: if not in PATH but file exists at given path treat OK.
    Log events:
      CONFIG_TEST_PATH_CHECK: <label> | <expanded-path> | OK/MISSING
      CONFIG_TEST_EXEC_CHECK: <exe> | <location or reason> | OK/MISSING
    """
    missing_paths: Set[str] = set()
    missing_execs: Set[str] = set()
    seen_execs: Set[str] = set()
    total_commands = 0
    total_actions = 0
    for label, pair in iter_commands(config):
        total_actions += 1
        base = pair.get('_base', {})
        action = pair.get('_action', {})
        path = base.get('path')
        if path:
            expanded = os.path.expandvars(path)
            exists = os.path.exists(expanded)
            if not exists:
                missing_paths.add(f'{label} -> {expanded}')
                if logger:
                    logger.log('CONFIG_TEST_PATH_CHECK', f'{label} | {expanded} | MISSING', status='WARN')
            else:
                if logger:
                    logger.log('CONFIG_TEST_PATH_CHECK', f'{label} | {expanded} | OK', status='OK')
        else:
            # If no base path, attempt to detect a direct absolute path inside argsTemplate (e.g. explorer C:\foo\bar\)
            tmpl = action.get('argsTemplate', '') or ''
            if tmpl and '{path}' not in tmpl:
                # Heuristic: take first token that looks like an absolute Windows path
                # Simple pattern: starts with drive letter and \\ or contains \\ after drive.
                token = tmpl.strip().split()[0]
                candidate = token
                if len(candidate) > 2 and candidate[1] == ':' and ('\\' in candidate or '/' in candidate):
                    expanded = os.path.expandvars(candidate)
                    if not os.path.exists(expanded):
                        missing_paths.add(f'{label} -> {expanded} (argsTemplate)')
                        if logger:
                            logger.log('CONFIG_TEST_PATH_CHECK', f'{label} | {expanded} (tmpl) | MISSING', status='WARN')
                    else:
                        if logger:
                            logger.log('CONFIG_TEST_PATH_CHECK', f'{label} | {expanded} (tmpl) | OK', status='OK')
        exe = _collect_executable(action)
        # Resolve alias to real path if alias provided
        if exe and action.get('executableAlias') and 'aliases' in config:
            real = config.get('aliases', {}).get(action.get('executableAlias'))
            if real:
                if logger:
                    logger.log('CONFIG_TEST_ALIAS_RESOLVE', f"{action.get('executableAlias')} -> {real}", status='OK')
                exe = real
            else:
                if logger:
                    logger.log('ALIAS_MISSING', action.get('executableAlias'), status='WARN')
        if exe and exe not in seen_execs:
            seen_execs.add(exe)
            if exe.lower() == 'explorer':
                if logger:
                    logger.log('CONFIG_TEST_EXEC_CHECK', f'{exe} | OK (assumed)', status='OK')
            else:
                found = shutil.which(exe)
                if not found:
                    # Absolute path or relative file existence check
                    if os.path.isabs(exe) and os.path.exists(exe):
                        if logger:
                            logger.log('CONFIG_TEST_EXEC_CHECK', f'{exe} | (absolute) | OK', status='OK')
                    elif exe.lower().endswith(('.bat', '.cmd')):
                        candidates = [os.path.join(os.getcwd(), exe), os.path.join(os.path.dirname(__file__), exe)]
                        if any(os.path.exists(c) for c in candidates):
                            if logger:
                                logger.log('CONFIG_TEST_EXEC_CHECK', f'{exe} | {candidates} | OK', status='OK')
                        else:
                            missing_execs.add(exe)
                            if logger:
                                logger.log('CONFIG_TEST_EXEC_CHECK', f'{exe} | MISSING', status='WARN')
                    else:
                        missing_execs.add(exe)
                        if logger:
                            logger.log('CONFIG_TEST_EXEC_CHECK', f'{exe} | MISSING', status='WARN')
                else:
                    if logger:
                        logger.log('CONFIG_TEST_EXEC_CHECK', f'{exe} | {found} | OK', status='OK')
    base_signatures: Set[str] = set()
    for group in config.get('groups', []):
        subgroups = group.get('subgroups')
        if subgroups:
            for sg in subgroups:
                for cmd in sg.get('commands', []):
                    if not cmd.get('enabled', True):
                        continue
                    sig = f"{cmd.get('label')}|{cmd.get('path')}"
                    base_signatures.add(sig)
        else:
            for cmd in group.get('commands', []):
                if not cmd.get('enabled', True):
                    continue
                sig = f"{cmd.get('label')}|{cmd.get('path')}"
                base_signatures.add(sig)
    total_commands = len(base_signatures)
    return {
        'missing_paths': missing_paths,
        'missing_executables': missing_execs,
        'total_commands': total_commands,
        'total_actions': total_actions,
    }

def resolve_git_bash_executable(config: Dict[str, Any]) -> str:
    """Deprecated: kept for backward compatibility, now unused."""
    return ''

def build_command_string(cmd_def: Dict[str, Any]) -> str:
    """Build command allowing optional path when template lacks {path}."""
    if CommandBuilder:
        return CommandBuilder(cmd_def).build()
    exe = cmd_def.get('executable') or cmd_def.get('executableAlias')
    template = cmd_def.get('argsTemplate', '') or ''
    path = cmd_def.get('path')
    if not exe:
        raise ValueError('Executable missing')
    if '{path}' in template and not path:
        raise ValueError('Path placeholder present but path missing')
    args = template.format(path=path) if template else ''
    return f"{exe} {args}".strip()

def resolve_executable(action: Dict[str, Any], config: Dict[str, Any], logger=None) -> str:
    """Return executable path resolving alias if present."""
    exe = action.get('executable')
    alias = action.get('executableAlias')
    if alias:
        real = config.get('aliases', {}).get(alias)
        if real:
            if logger:
                logger.log('ALIAS_RESOLVE', f'{alias} -> {real}', status='INFO')
            exe = real
        else:
            if logger:
                logger.log('ALIAS_MISSING', alias, status='WARN')
    return exe or ''

def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Command Board GUI / CLI')
    parser.add_argument('config', nargs='?', default=None, help='Path to config JSON file')
    parser.add_argument('-l', '--list', action='store_true', help='List all commands and exit')
    parser.add_argument('-r', '--run', metavar='LABEL', help='Run a command by its label')
    parser.add_argument('-d', '--dry-run', action='store_true', help='Show command string without executing')
    parser.add_argument('-o', '--one-shot', action='store_true', help='Close GUI after first successful action (override config)')
    parser.add_argument('-t', '--test-config', action='store_true', help='Validate config (paths & executables) and exit')
    parser.add_argument('-x', '--auto-exit', metavar='SECONDS', type=int, help='Auto-exit GUI after SECONDS (forces non-blocking usage)')
    return parser.parse_args(argv[1:])

def main(argv: List[str]):
    args = parse_args(argv)
    config_path = args.config or CONFIG_FILE
    try:
        config = load_config(config_path)
    except Exception as e:
        print(f'Failed to load config: {e}', file=sys.stderr)
        sys.exit(1)

    if getattr(args, 'test_config', False):
        # Perform validation only (CLI mode) with logging
        logger = get_logger(resolve_log_path(config.get('settings', {})))
        logger.log('CONFIG_TEST', 'cli started', status='INFO')
        report = validate_config(config, logger=logger)
        missing_paths = report['missing_paths']
        missing_execs = report['missing_executables']
        total_cmds = report['total_commands']
        total_actions = report['total_actions']
        for p in sorted(missing_paths):
            logger.log('CONFIG_TEST_PATH_MISSING', p, status='WARN')
        for e in sorted(missing_execs):
            logger.log('CONFIG_TEST_EXEC_MISSING', e, status='WARN')
        print('CONFIG VALIDATION SUMMARY')
        print(f'  Total commands : {total_cmds}')
        print(f'  Total actions  : {total_actions}')
        print(f'  Missing paths  : {len(missing_paths)}')
        for p in sorted(missing_paths):
            print(f'    PATH ! {p}')
        print(f'  Missing execs  : {len(missing_execs)}')
        for e in sorted(missing_execs):
            print(f'    EXEC ! {e}')
        if not missing_paths and not missing_execs:
            print('Result: OK')
            logger.log('CONFIG_TEST_RESULT', 'OK', status='OK')
            sys.exit(0)
        else:
            print('Result: WARN (issues found)')
            logger.log('CONFIG_TEST_RESULT', f'WARN paths={len(missing_paths)} execs={len(missing_execs)}', status='WARN')
            sys.exit(4)
            sys.exit(4)

    if args.list:
        print('Available commands:')
        for label, pair in iter_commands(config):
            base = pair.get('_base', {})
            action = pair.get('_action', {})
            path = base.get('path')
            resolved_exe = resolve_executable(action, config)
            try:
                cmd_str = build_command_string({'executable': resolved_exe, 'argsTemplate': action.get('argsTemplate'), 'path': path})
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
        exe = resolve_executable(action, config)
        template = action.get('argsTemplate')
        cmd_str = build_command_string({'executable': exe, 'argsTemplate': template, 'path': path})
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

    # If one-shot provided, force closeOnAction true
    if getattr(args, 'one_shot', False):
        config.setdefault('settings', {})['closeOnAction'] = True
    app = CommandBoardApp(config)
    if getattr(args, 'auto_exit', None):
        seconds = max(0, args.auto_exit)
        ms = seconds * 1000
        app.logger.log('APP_AUTO_EXIT_SCHEDULED', f'exiting in {seconds}s', status='INFO')
        app.after(ms, lambda: (app.logger.log('APP_AUTO_EXIT', 'auto exit trigger', status='INFO'), app.destroy()))
    app.mainloop()

if __name__ == '__main__':
    main(sys.argv)
