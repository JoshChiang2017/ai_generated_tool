import os
from typing import Dict

class CommandBuilder:
    def __init__(self, cmd_def: Dict):
        self.cmd_def = cmd_def

    def build(self) -> str:
        exe = self.cmd_def.get('executable') or self.cmd_def.get('executableAlias')
        template = self.cmd_def.get('argsTemplate', '') or ''
        path = self.cmd_def.get('path')
        if not exe:
            raise ValueError('Executable missing')
        if '{path}' in template and not path:
            raise ValueError('Path placeholder present but path missing')
        args = template.format(path=path) if template else ''
        return f"{exe} {args}".strip()

    @staticmethod
    def validate(cmd_def: Dict) -> None:
        if not cmd_def.get('executable') and not cmd_def.get('executableAlias'):
            raise ValueError('executable is required')
        template = cmd_def.get('argsTemplate', '') or ''
        if '{path}' in template and not cmd_def.get('path'):
            raise ValueError('Template expects path but path missing')
        p = cmd_def.get('path')
        if p and not os.path.exists(p):
            # Non-fatal allowance
            pass
