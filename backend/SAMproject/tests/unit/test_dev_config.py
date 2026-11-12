"""Local startup catches stale configuration before running Docker or SAM."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def dev(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[2] / "dev.py"
    spec = importlib.util.spec_from_file_location("dev_config_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    example = json.loads((source.parent / "env.example.json").read_text())
    (tmp_path / "env.example.json").write_text(json.dumps(example))
    (tmp_path / "env.json").write_text(json.dumps(example))
    return module


def edit_config(dev, edit):
    path = dev.ROOT / "env.json"
    config = json.loads(path.read_text())
    edit(config)
    path.write_text(json.dumps(config))
    return path.read_bytes()


def test_complete_config_and_custom_values_are_untouched(dev, capsys):
    before = edit_config(dev, lambda config: config["Parameters"].update({
        "S3_PUBLIC_ENDPOINT": "http://localhost:19090",
        "PROMPT_ARN": "private-custom-value", "EXTRA_SETTING": "keep-me",
    }))
    dev.check_env_config()
    assert (dev.ROOT / "env.json").read_bytes() == before
    assert capsys.readouterr().out == ""


def test_missing_optional_keys_warn_and_preserve_file(dev, capsys):
    def edit(config):
        for key in ("PROMPT_ARN", "GUARDRAIL_ID", "GUARDRAIL_VERSION"):
            config["Parameters"].pop(key)
    before = edit_config(dev, edit)
    dev.check_env_config()
    output = capsys.readouterr().out
    for key in ("PROMPT_ARN", "GUARDRAIL_ID", "GUARDRAIL_VERSION"):
        assert f"Parameters.{key}" in output
    assert "WARNING" in output
    assert "env.example.json" in output
    assert (dev.ROOT / "env.json").read_bytes() == before


@pytest.mark.parametrize("key", ["DYNAMODB_ENDPOINT", "S3_ENDPOINT", "S3_PUBLIC_ENDPOINT", "UPLOAD_BUCKET"])
def test_missing_local_setting_blocks_startup(dev, capsys, key):
    before = edit_config(dev, lambda config: config["Parameters"].pop(key))
    with pytest.raises(SystemExit) as exc:
        dev.check_env_config()
    assert exc.value.code == 1
    assert f"Parameters.{key}" in capsys.readouterr().out
    assert (dev.ROOT / "env.json").read_bytes() == before


@pytest.mark.parametrize("value", ["", "  ", None, 123])
def test_empty_or_invalid_local_override_blocks(dev, capsys, value):
    edit_config(dev, lambda config: config.update({"ResumesFunction": {"S3_ENDPOINT": value}}))
    with pytest.raises(SystemExit):
        dev.check_env_config()
    assert "ResumesFunction.S3_ENDPOINT" in capsys.readouterr().out


def test_new_example_section_reports_each_missing_key(dev, capsys):
    path = dev.ROOT / "env.example.json"
    example = json.loads(path.read_text())
    example["NewFunction"] = {"NEW_SETTING": "example-default"}
    path.write_text(json.dumps(example))
    dev.check_env_config()
    assert "NewFunction.NEW_SETTING" in capsys.readouterr().out


@pytest.mark.parametrize("contents", ['{"Parameters": {"secret": "private-value", broken}', '[]', '{"Parameters": "private-value"}'])
def test_bad_json_or_shape_fails_without_printing_values(dev, capsys, contents):
    (dev.ROOT / "env.json").write_text(contents)
    with pytest.raises(SystemExit):
        dev.check_env_config()
    output = capsys.readouterr().out
    assert "env.json" in output
    assert "private-value" not in output


def test_missing_section_blocks(dev, capsys):
    (dev.ROOT / "env.json").write_text("{}")
    with pytest.raises(SystemExit):
        dev.check_env_config()
    assert "Parameters.S3_PUBLIC_ENDPOINT" in capsys.readouterr().out


def test_first_run_still_copies_example(dev):
    (dev.ROOT / "env.json").unlink()
    dev.copy_if_missing("env.example.json", "env.json")
    dev.check_env_config()
    assert (dev.ROOT / "env.json").read_bytes() == (dev.ROOT / "env.example.json").read_bytes()


def test_invalid_config_stops_before_tools_or_subprocesses(dev, monkeypatch):
    edit_config(dev, lambda config: config["Parameters"].pop("S3_ENDPOINT"))
    require = MagicMock()
    run = MagicMock()
    monkeypatch.setattr(dev, "require", require)
    monkeypatch.setattr(dev.subprocess, "run", run)
    monkeypatch.setattr(dev.sys, "argv", ["dev.py"])
    with pytest.raises(SystemExit):
        dev.main()
    require.assert_not_called()
    run.assert_not_called()
