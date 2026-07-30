# executors/base.py
from abc import ABC, abstractmethod
from models import ExecResult


class BaseExecutor(ABC):
    @abstractmethod
    async def execute(
        self,
        command: str,
        cwd: str = None,
        timeout: int = None,
        env: dict = None,
    ) -> ExecResult:
        """执行单条命令，返回 ExecResult"""
        ...

    @abstractmethod
    async def execute_batch(
        self,
        commands: list[str],
        cwd: str = None,
        timeout: int = None,
        env: dict = None,
    ) -> list[ExecResult]:
        """并发执行多条命令，返回 ExecResult 列表"""
        ...