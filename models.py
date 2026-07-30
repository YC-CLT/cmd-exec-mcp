from dataclasses import dataclass
from config import RESULT_FIELDS


@dataclass
class ExecResult:
    command_echo: str = ""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration: float = 0.0
    is_timeout: bool = False

    def to_dict(self, fields: dict = None) -> dict:
        """按配置过滤返回字段"""
        if fields is None:
            fields = RESULT_FIELDS
        return {k: getattr(self, k) for k, v in fields.items() if v}