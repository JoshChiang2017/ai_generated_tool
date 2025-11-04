import os
import re
from typing import Dict

_RESERVED = {'executable', 'executableAlias', 'argsTemplate'}

class CommandBuilder:
    """Generic command builder performing placeholder substitution.

    Any key in cmd_def not in _RESERVED is considered a substitution variable.
    Example:
      {
        "executable": "explorer",
        "argsTemplate": "{folder_path}",
        "folder_path": "D:\\work\\Grace\\"  # variable used in template
      }

    This replaces previous special-case 'path' / 'pathOverride'. Action-level
    variables override command-level ones before calling this builder.
    """
    def __init__(self, cmd_def: Dict):
        self.cmd_def = cmd_def

    def _variables(self) -> Dict:
        return {k: v for k, v in self.cmd_def.items() if k not in _RESERVED}

    def build(self) -> str:
        exe = self.cmd_def.get('executable') or self.cmd_def.get('executableAlias')
        template = (self.cmd_def.get('argsTemplate') or '').strip()
        if not exe:
            raise ValueError('Executable missing')
        if not template:
            return exe.strip()
        vars_dict = self._variables()
        # Validate placeholders present
        placeholders = set(re.findall(r'{([a-zA-Z0-9_]+)}', template))
        missing = [p for p in placeholders if p not in vars_dict]
        if missing:
            raise ValueError(f'Missing variables for template: {", ".join(missing)}')
        try:
            args = template.format(**vars_dict)
        except KeyError as e:
            raise ValueError(f'Variable missing during format: {e.args[0]}')
        return f"{exe} {args}".strip()

    @staticmethod
    def validate(cmd_def: Dict) -> None:
        exe = cmd_def.get('executable') or cmd_def.get('executableAlias')
        if not exe:
            raise ValueError('executable is required')
        template = (cmd_def.get('argsTemplate') or '').strip()
        if not template:
            return
        vars_dict = {k: v for k, v in cmd_def.items() if k not in _RESERVED}
        placeholders = set(re.findall(r'{([a-zA-Z0-9_]+)}', template))
        missing = [p for p in placeholders if p not in vars_dict]
        if missing:
            raise ValueError(f'Variables missing: {", ".join(missing)}')
        # Light path existence check for variables that look like paths.
        for name in placeholders:
            val = vars_dict.get(name)
            if isinstance(val, str) and len(val) > 2 and val[1] == ':' and ('\\' in val or '/' in val):
                if not os.path.exists(val):
                    # Non-fatal; builder does not fail, validation warns.
                    pass
