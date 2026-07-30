from models import ExecResult


def test_exec_result_defaults():
    result = ExecResult()
    assert result.command_echo == ""
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.exit_code == 0
    assert result.duration == 0.0
    assert result.is_timeout is False


def test_exec_result_with_values():
    result = ExecResult(
        command_echo="echo hello",
        stdout="hello\n",
        stderr="",
        exit_code=0,
        duration=0.05,
        is_timeout=False,
    )
    assert result.command_echo == "echo hello"
    assert result.stdout == "hello\n"
    assert result.exit_code == 0


def test_to_dict_all_fields():
    result = ExecResult(
        command_echo="echo hello",
        stdout="hello\n",
        stderr="",
        exit_code=0,
        duration=0.05,
        is_timeout=False,
    )
    d = result.to_dict()
    assert d == {
        "command_echo": "echo hello",
        "stdout": "hello\n",
        "stderr": "",
        "exit_code": 0,
        "duration": 0.05,
        "is_timeout": False,
    }


def test_to_dict_filtered_fields():
    result = ExecResult(
        command_echo="echo hello",
        stdout="hello\n",
        stderr="",
        exit_code=0,
        duration=0.05,
        is_timeout=False,
    )
    custom_fields = {
        "stdout": True,
        "stderr": True,
        "exit_code": True,
        "duration": False,
        "is_timeout": False,
        "command_echo": False,
    }
    d = result.to_dict(fields=custom_fields)
    assert d == {"stdout": "hello\n", "stderr": "", "exit_code": 0}


def test_to_dict_timeout_result():
    result = ExecResult(
        command_echo="sleep 100",
        is_timeout=True,
        exit_code=-1,
        duration=5.0,
    )
    d = result.to_dict()
    assert d["is_timeout"] is True
    assert d["exit_code"] == -1
    assert d["duration"] == 5.0