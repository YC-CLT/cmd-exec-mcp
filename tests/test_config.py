import config


def test_security_mode_is_valid_string():
    assert config.SECURITY_MODE in ("restricted", "full")


def test_whitelist_is_list():
    assert isinstance(config.COMMAND_WHITELIST, list)


def test_blacklist_is_list():
    assert isinstance(config.COMMAND_BLACKLIST, list)


def test_default_timeout_is_int():
    assert isinstance(config.DEFAULT_TIMEOUT, int)


def test_default_cwd_is_none():
    assert config.DEFAULT_CWD is None


def test_force_shell_is_none_or_string():
    assert config.FORCE_SHELL is None or isinstance(config.FORCE_SHELL, str)


def test_result_fields_has_required_keys():
    required_keys = {"stdout", "stderr", "exit_code", "duration", "is_timeout", "command_echo", "output_file"}
    assert set(config.RESULT_FIELDS.keys()) == required_keys
    assert all(isinstance(v, bool) for v in config.RESULT_FIELDS.values())


def test_command_list_mode_is_valid():
    assert config.COMMAND_LIST_MODE in ("whitelist", "blacklist")


def test_ssh_config_mode_is_valid():
    assert config.SSH_CONFIG_MODE in ("standard", "custom")


def test_ssh_persistent_is_bool():
    assert isinstance(config.SSH_PERSISTENT, bool)


def test_ssh_connection_timeout_is_positive():
    assert config.SSH_CONNECTION_TIMEOUT > 0