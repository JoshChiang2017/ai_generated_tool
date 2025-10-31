import os
from typing import Dict

class CommandBuilder:
    def __init__(self, cmd_def: Dict):
        self.cmd_def = cmd_def

    def build(self) -> str:
        exe = self.cmd_def.get('executable')
        path = self.cmd_def.get('path')
        template = self.cmd_def.get('argsTemplate', '')
        if not exe or not path:
            raise ValueError('Executable or path missing')
        return f"{exe} {template.format(path=path)}".strip()

    @staticmethod
    def validate(cmd_def: Dict) -> None:
        if not cmd_def.get('executable'):
            raise ValueError('executable is required')
        if not cmd_def.get('path'):
            raise ValueError('path is required')
        if not os.path.exists(cmd_def.get('path')):
            # Non-fatal: allow path that may exist later, but warn via exception if strict desired
            pass
