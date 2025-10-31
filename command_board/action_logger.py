import os
import datetime
from typing import Optional

class ActionLogger:
    def __init__(self, log_file: str):
        self.log_file = log_file
        # Ensure directory exists
        os.makedirs(os.path.dirname(log_file) or '.', exist_ok=True)

    def log(self, event: str, detail: str = '', status: str = 'OK'):  # status: OK|ERROR|INFO
        ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"{ts}\t{status}\t{event}\t{detail}\n"
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(line)
                f.flush()
        except Exception:
            # Silent failure to avoid blocking UI
            pass

_default_logger: Optional[ActionLogger] = None

def get_logger(log_path: str) -> ActionLogger:
    global _default_logger
    if _default_logger is None or _default_logger.log_file != log_path:
        _default_logger = ActionLogger(log_path)
    return _default_logger
