import json
import os
import subprocess
import sys
import shutil
import customtkinter as ctk
from tkinter import messagebox
from typing import Dict, Any, List, Tuple, Set
import argparse
from action_logger import get_logger

# Set appearance mode and color theme
ctk.set_appearance_mode("System")  # Modes: "System", "Dark", "Light"
ctk.set_default_color_theme("dark-blue")  # Themes: "blue", "green", "dark-blue"

# CustomTkinter has built-in tooltip support via CTkToolTip (optional)
# For now, we'll skip tooltips or use simple approach

try:
    from core import CommandBuilder
except ImportError:
    CommandBuilder = None  # type: ignore

def get_application_path():
    """Get the directory where the application/script is located."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - use exe directory
        return os.path.dirname(sys.executable)
    else:
        # Running as script - use script directory
        return os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(get_application_path(), 'command_config.json')

def resolve_log_path(settings: Dict[str, Any]) -> str:
    """Anchor log file to application directory if relative."""
    app_dir = get_application_path()
    raw = settings.get('logFile') if isinstance(settings, dict) else None
    if not raw:
        return os.path.join(app_dir, 'command_board_actions.log')
    if os.path.isabs(raw):
        return raw
    return os.path.join(app_dir, raw)

class CommandBoardApp(ctk.CTk):
    def __init__(self, config: Dict[str, Any], config_path: str = CONFIG_FILE):
        super().__init__()
        settings = config.get('settings', {})
        self.title(settings.get('windowTitle', 'Command Board'))
        self.config_data = config
        self.config_path = config_path
        self.button_width = settings.get('buttonWidth', 30)
        self.close_on_action = settings.get('closeOnAction', True)
        self.record_log = settings.get('recordLog', False)
        log_file = resolve_log_path(settings)
        self.logger = get_logger(log_file)
        if self.record_log:
            self.logger.log('APP_START', 'Application initialized', status='INFO')
        self._build_ui()
        # Apply window size: accepts WIDTHxHEIGHT (e.g. 1200x800). Fallback to default if invalid.
        win_size = settings.get('windowSize')
        applied = False
        if isinstance(win_size, str):
            candidate = win_size.strip().lower()
            import re
            m = re.match(r'^(\d{2,5})x(\d{2,5})$', candidate)
            if m:
                self.geometry(candidate)
                applied = True
                if self.record_log:
                    self.logger.log('WINDOW_SIZE', f'Applied custom {candidate}', status='OK')
            else:
                if self.record_log:
                    self.logger.log('WINDOW_SIZE', f'Invalid format {win_size}', status='WARN')
        if not applied:
            # Default comfortable size if user did not specify or format invalid
            self.geometry('1100x750')
            if self.record_log:
                if not win_size:
                    self.logger.log('WINDOW_SIZE', 'Applied default 1100x750 (no user setting)', status='INFO')
                else:
                    self.logger.log('WINDOW_SIZE', f'Fallback to default 1100x750 from {win_size}', status='INFO')


    def _build_ui(self):
        # Create tabview for groups (CustomTkinter uses CTkTabview instead of Notebook)
        tabview = ctk.CTkTabview(self)
        tabview.pack(fill='both', expand=True, padx=10, pady=10)
        # Configure tab button font size
        tabview._segmented_button.configure(font=ctk.CTkFont(size=16))

        for group in self.config_data.get('groups', []):
            group_name = group.get('name', 'Group')
            tab = tabview.add(group_name)
            
            # Use CTkScrollableFrame for scrollable content
            scroll_frame = ctk.CTkScrollableFrame(tab)
            scroll_frame.pack(fill='both', expand=True, padx=5, pady=5)
            
            desc = group.get('description')
            if desc:
                desc_label = ctk.CTkLabel(scroll_frame, text=desc, text_color="gray50")
                desc_label.pack(anchor='w', padx=10, pady=(5,10))
            
            subgroups = group.get('subgroups')
            if subgroups:
                for sg in subgroups:
                    sg_name = sg.get('name', 'subgroup')
                    # Subgroup header
                    header = ctk.CTkLabel(scroll_frame, text=sg_name, font=ctk.CTkFont(size=16, weight="bold"))
                    header.pack(anchor='w', padx=10, pady=(15,5))
                    
                    for cmd in sg.get('commands', []):
                        if not cmd.get('enabled', True):
                            continue
                        label = cmd.get('label', 'Unnamed')
                        actions = cmd.get('actions', [])
                        
                        # Command row frame
                        row = ctk.CTkFrame(scroll_frame, fg_color="transparent")
                        row.pack(anchor='w', fill='x', padx=15, pady=3)
                        
                        # Command label
                        cmd_label = ctk.CTkLabel(row, text=label, width=self.button_width*4, anchor='w')
                        cmd_label.pack(side='left', padx=(0,10))
                        
                        # Action buttons
                        for act in actions:
                            act_name = act.get('name', 'action')
                            btn = ctk.CTkButton(row, text=act_name, width=60,
                                              font=ctk.CTkFont(weight="bold", size=12),
                                              command=lambda a=act, base=cmd, lab=(group_name, sg_name, label, act_name): self.execute_action(base, a, lab))
                            btn.pack(side='left', padx=3)
            else:
                for cmd in group.get('commands', []):
                    if not cmd.get('enabled', True):
                        continue
                    label = cmd.get('label', 'Unnamed')
                    actions = cmd.get('actions', [])
                    
                    # Command row frame
                    row = ctk.CTkFrame(scroll_frame, fg_color="transparent")
                    row.pack(anchor='w', fill='x', padx=10, pady=3)
                    
                    # Command label
                    cmd_label = ctk.CTkLabel(row, text=label, width=self.button_width*4, anchor='w')
                    cmd_label.pack(side='left', padx=(0,10))
                    
                    # Action buttons
                    for act in actions:
                        act_name = act.get('name', 'action')
                        btn = ctk.CTkButton(row, text=act_name, width=60,
                                          font=ctk.CTkFont(weight="bold", size=12),
                                          command=lambda a=act, base=cmd, lab=(group_name, None, label, act_name): self.execute_action(base, a, lab))
                        btn.pack(side='left', padx=3)

        # Settings Tab
        settings_tab = tabview.add('Settings')
        settings_scroll = ctk.CTkScrollableFrame(settings_tab)
        settings_scroll.pack(fill='both', expand=True, padx=5, pady=5)
        
        
        # Advanced setting (Config Test)
        test_frame = ctk.CTkFrame(settings_scroll)
        test_frame.pack(fill='x', padx=10, pady=(0, 15))
        
        test_header = ctk.CTkLabel(test_frame, text='Advanced', font=ctk.CTkFont(size=16, weight="bold"))
        test_header.pack(anchor='w', padx=10, pady=(10, 5))
        
        test_btn = ctk.CTkButton(test_frame, text='Run Config Test', command=self.run_tests, width=150,
                                font=ctk.CTkFont(weight="bold"))
        test_btn.pack(anchor='w', padx=10, pady=(0, 5))
        
        test_desc = ctk.CTkLabel(test_frame, text='Validate paths and executables in configuration', 
                                text_color="gray50", font=ctk.CTkFont(size=14))
        test_desc.pack(anchor='w', padx=30, pady=(0, 10))
        
        # Configuration settings
        config_frame = ctk.CTkFrame(settings_scroll)
        config_frame.pack(fill='x', padx=10, pady=(0, 15))
        
        config_header = ctk.CTkLabel(config_frame, text='Configuration', font=ctk.CTkFont(size=16, weight="bold"))
        config_header.pack(anchor='w', padx=10, pady=(10, 10))
        
        # Record Log checkbox
        self.record_log_var = ctk.BooleanVar(value=self.record_log)
        log_cb = ctk.CTkCheckBox(config_frame, text='Enable logging', 
                                variable=self.record_log_var, command=self._toggle_record_log)
        log_cb.pack(anchor='w', padx=10, pady=5)
        
        # Close on Action checkbox
        self.close_on_action_var = ctk.BooleanVar(value=self.close_on_action)
        close_cb = ctk.CTkCheckBox(config_frame, text='One-shot mode (Close window after action)', 
                                   variable=self.close_on_action_var, command=self._toggle_close_on_action)
        close_cb.pack(anchor='w', padx=10, pady=(5, 10))

    def execute_action(self, base_cmd: Dict[str, Any], action: Dict[str, Any], label_tuple=None):
        """Execute an action with generic variable substitution.

        Reserved keys: name, executable, executableAlias, argsTemplate, enabled, actions, label.
        Any other key at command or action level becomes a variable usable in argsTemplate.
        Action-level keys override command-level keys.
        """
        act_name = action.get('name', 'action')
        if self.record_log:
            self.logger.log('BUTTON_CLICK', f'{label_tuple} -> {act_name}', status='INFO')
        exe = resolve_executable(action, self.config_data, self.logger if self.record_log else None)
        template = (action.get('argsTemplate') or '').strip()
        reserved = {'name','executable','executableAlias','argsTemplate','enabled','actions','label'}
        vars_ctx = {k: v for k, v in base_cmd.items() if k not in reserved}
        for k, v in action.items():
            if k not in reserved:
                vars_ctx[k] = v
        if not exe:
            if self.record_log:
                self.logger.log('EXECUTE', f'MISSING executable {action}', status='ERROR')
            messagebox.showerror('Error', f'Missing executable for action {act_name}')
            return
        try:
            if template:
                import re
                placeholders = set(re.findall(r'{([a-zA-Z0-9_]+)}', template))
                missing = [p for p in placeholders if p not in vars_ctx]
                if missing:
                    if self.record_log:
                        self.logger.log('EXECUTE', f'Missing vars {missing} for {act_name}', status='ERROR')
                    messagebox.showerror('Template Error', f'Missing variables: {", ".join(missing)}')
                    return
                final_args = template.format(**vars_ctx)
            else:
                final_args = ''
            quoted_exe = f'"{exe}"' if ' ' in exe and not exe.startswith('"') else exe
            full_cmd = f"{quoted_exe} {final_args}".strip()
            if final_args:
                subprocess.Popen(full_cmd, shell=True)
            else:
                subprocess.Popen([exe])
            if self.record_log:
                self.logger.log('EXECUTE', full_cmd, status='OK')
            if self.close_on_action:
                if self.record_log:
                    self.logger.log('APP_CLOSE', 'Auto-close after execute action', status='INFO')
                self.after(100, self.destroy)
        except Exception as e:
            if self.record_log:
                self.logger.log('EXECUTE', f'{act_name} ERROR {e}', status='ERROR')
            messagebox.showerror('Execution Failed', str(e))

    # Removed reload_config and open_config per user request

    def _toggle_record_log(self):
        """Toggle recordLog setting and save to config file."""
        self.record_log = self.record_log_var.get()
        if self.record_log:
            self.logger.log('SETTING_CHANGE', f'recordLog={self.record_log}', status='INFO')
        # Update config data
        if 'settings' not in self.config_data:
            self.config_data['settings'] = {}
        self.config_data['settings']['recordLog'] = self.record_log
        # Save to file
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            if self.record_log:
                self.logger.log('CONFIG_SAVE', f'Saved recordLog={self.record_log} to {self.config_path}', status='OK')
        except Exception as e:
            if self.record_log:
                self.logger.log('CONFIG_SAVE', f'Failed to save config: {e}', status='ERROR')
            messagebox.showerror('Save Error', f'Failed to save config: {e}')

    def _toggle_close_on_action(self):
        """Toggle closeOnAction setting and save to config file."""
        self.close_on_action = self.close_on_action_var.get()
        if self.record_log:
            self.logger.log('SETTING_CHANGE', f'closeOnAction={self.close_on_action}', status='INFO')
        # Update config data
        if 'settings' not in self.config_data:
            self.config_data['settings'] = {}
        self.config_data['settings']['closeOnAction'] = self.close_on_action
        # Save to file
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            if self.record_log:
                self.logger.log('CONFIG_SAVE', f'Saved closeOnAction={self.close_on_action} to {self.config_path}', status='OK')
        except Exception as e:
            if self.record_log:
                self.logger.log('CONFIG_SAVE', f'Failed to save config: {e}', status='ERROR')
            messagebox.showerror('Save Error', f'Failed to save config: {e}')

    # ===================== Validation / Test Button =====================
    def run_tests(self):
        report = validate_config(self.config_data, logger=self.logger if self.record_log else None)
        if self.record_log:
            self.logger.log('CONFIG_TEST', 'started', status='INFO')
        missing_paths = report['missing_paths']
        missing_execs = report['missing_executables']
        total_cmds = report['total_commands']
        total_actions = report['total_actions']
        # Log each missing item individually for easier grep
        # Already logged each check; still log aggregate missing items for quick grep
        if self.record_log:
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
        if self.record_log:
            self.logger.log('CONFIG_TEST_RESULT', summary.replace('\n', ' | '), status=status)
        if not missing_paths and not missing_execs:
            messagebox.showinfo('Config Test', 'All OK!\n\n' + summary)
        else:
            # Show detailed window using CustomTkinter
            win = ctk.CTkToplevel(self)
            win.title('Config Test Report')
            win.geometry('800x600')
            
            # Use CTkTextbox for CustomTkinter
            txt = ctk.CTkTextbox(win, width=780, height=540)
            txt.pack(fill='both', expand=True, padx=10, pady=(10, 5))
            txt.insert('1.0', summary)
            txt.configure(state='disabled')
            
            close_btn = ctk.CTkButton(win, text='Close', command=win.destroy, width=100,
                                     font=ctk.CTkFont(weight="bold"))
            close_btn.pack(pady=(5, 10))


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
    """Validate executables and path-like variables referenced in config.

    Any variable used inside argsTemplate placeholders is checked. If its value
    appears to be an absolute Windows path and doesn't exist, it's reported.
    Also retains heuristic for direct absolute path when no placeholders.
    """
    import re
    missing_paths: Set[str] = set()
    missing_execs: Set[str] = set()
    seen_execs: Set[str] = set()
    total_commands = 0
    total_actions = 0
    reserved = {'name','executable','executableAlias','argsTemplate','enabled','actions','label'}
    for label, pair in iter_commands(config):
        total_actions += 1
        base = pair.get('_base', {})
        action = pair.get('_action', {})
        template = (action.get('argsTemplate') or '').strip()
        vars_ctx = {k: v for k, v in base.items() if k not in reserved}
        for k, v in action.items():
            if k not in reserved:
                vars_ctx[k] = v
        placeholders = set(re.findall(r'{([a-zA-Z0-9_]+)}', template))
        for ph in placeholders:
            if ph not in vars_ctx:
                missing_paths.add(f'{label} -> <missing variable {ph}>')
                if logger:
                    logger.log('CONFIG_TEST_VAR_MISSING', f'{label} | {ph}', status='WARN')
                continue
            val = vars_ctx.get(ph)
            if isinstance(val, str) and len(val) > 2 and val[1] == ':' and ('\\' in val or '/' in val):
                expanded = os.path.expandvars(val)
                if not os.path.exists(expanded):
                    missing_paths.add(f'{label} -> {expanded}')
                    if logger:
                        logger.log('CONFIG_TEST_PATH_CHECK', f'{label} | {expanded} | MISSING', status='WARN')
                else:
                    if logger:
                        logger.log('CONFIG_TEST_PATH_CHECK', f'{label} | {expanded} | OK', status='OK')
        if template and not placeholders:
            first = template.split()[0]
            if len(first) > 2 and first[1] == ':' and ('\\' in first or '/' in first):
                expanded = os.path.expandvars(first)
                if not os.path.exists(expanded):
                    missing_paths.add(f'{label} -> {expanded} (direct)')
                    if logger:
                        logger.log('CONFIG_TEST_PATH_CHECK', f'{label} | {expanded} (direct) | MISSING', status='WARN')
                else:
                    if logger:
                        logger.log('CONFIG_TEST_PATH_CHECK', f'{label} | {expanded} (direct) | OK', status='OK')
        exe = _collect_executable(action)
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
                    sig = f"{cmd.get('label')}"
                    base_signatures.add(sig)
        else:
            for cmd in group.get('commands', []):
                if not cmd.get('enabled', True):
                    continue
                sig = f"{cmd.get('label')}"
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
    """Build command using generic variables with CommandBuilder."""
    if CommandBuilder:
        return CommandBuilder(dict(cmd_def)).build()
    exe = cmd_def.get('executable') or cmd_def.get('executableAlias')
    template = (cmd_def.get('argsTemplate') or '').strip()
    if not exe:
        raise ValueError('Executable missing')
    if not template:
        return exe.strip()
    import re
    vars_ctx = {k: v for k, v in cmd_def.items() if k not in {'executable','executableAlias','argsTemplate'}}
    placeholders = set(re.findall(r'{([a-zA-Z0-9_]+)}', template))
    missing = [p for p in placeholders if p not in vars_ctx]
    if missing:
        raise ValueError(f'Missing variables: {", ".join(missing)}')
    args = template.format(**vars_ctx)
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
        settings = config.get('settings', {})
        record_log = settings.get('recordLog', False)
        logger = get_logger(resolve_log_path(settings))
        if record_log:
            logger.log('CONFIG_TEST', 'cli started', status='INFO')
        report = validate_config(config, logger=logger if record_log else None)
        missing_paths = report['missing_paths']
        missing_execs = report['missing_executables']
        total_cmds = report['total_commands']
        total_actions = report['total_actions']
        if record_log:
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
            if record_log:
                logger.log('CONFIG_TEST_RESULT', 'OK', status='OK')
            sys.exit(0)
        else:
            print('Result: WARN (issues found)')
            if record_log:
                logger.log('CONFIG_TEST_RESULT', f'WARN paths={len(missing_paths)} execs={len(missing_execs)}', status='WARN')
            sys.exit(4)
            sys.exit(4)

    if args.list:
        print('Available commands:')
        reserved = {'name','executable','executableAlias','argsTemplate','enabled','actions','label'}
        for label, pair in iter_commands(config):
            base = pair.get('_base', {})
            action = pair.get('_action', {})
            exe = resolve_executable(action, config)
            template = action.get('argsTemplate')
            vars_ctx = {k: v for k, v in base.items() if k not in reserved}
            for k, v in action.items():
                if k not in reserved:
                    vars_ctx[k] = v
            build_def: Dict[str, Any] = {'executable': exe, 'argsTemplate': template, **vars_ctx}
            try:
                cmd_str = build_command_string(build_def)
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
        exe = resolve_executable(action, config)
        template = action.get('argsTemplate')
        reserved = {'name','executable','executableAlias','argsTemplate','enabled','actions','label'}
        vars_ctx = {k: v for k, v in base.items() if k not in reserved}
        for k, v in action.items():
            if k not in reserved:
                vars_ctx[k] = v
        build_def: Dict[str, Any] = {'executable': exe, 'argsTemplate': template, **vars_ctx}
        cmd_str = build_command_string(build_def)
        if args.dry_run:
            print(f'DRY RUN: {cmd_str}')
            settings = config.get('settings', {})
            if settings.get('recordLog', False):
                logger = get_logger(resolve_log_path(settings))
                logger.log('CLI_DRY_RUN', f'{label} -> {cmd_str}', status='INFO')
            return
        try:
            subprocess.Popen(cmd_str, shell=True)
            print(f'Executed: {cmd_str}')
            settings = config.get('settings', {})
            if settings.get('recordLog', False):
                logger = get_logger(resolve_log_path(settings))
                logger.log('CLI_EXECUTE', f'{label} -> {cmd_str}', status='OK')
        except Exception as e:
            print(f'Execution failed: {e}', file=sys.stderr)
            settings = config.get('settings', {})
            if settings.get('recordLog', False):
                logger = get_logger(resolve_log_path(settings))
                logger.log('CLI_EXECUTE', f'{label} ERROR {e}', status='ERROR')
            sys.exit(3)
        return

    # If one-shot provided, force closeOnAction true
    if getattr(args, 'one_shot', False):
        config.setdefault('settings', {})['closeOnAction'] = True
    app = CommandBoardApp(config, config_path)
    if getattr(args, 'auto_exit', None):
        seconds = max(0, args.auto_exit)
        ms = seconds * 1000
        if app.record_log:
            app.logger.log('APP_AUTO_EXIT_SCHEDULED', f'exiting in {seconds}s', status='INFO')
        def auto_exit_handler():
            if app.record_log:
                app.logger.log('APP_AUTO_EXIT', 'auto exit trigger', status='INFO')
            app.destroy()
        app.after(ms, auto_exit_handler)
    app.mainloop()

if __name__ == '__main__':
    main(sys.argv)
