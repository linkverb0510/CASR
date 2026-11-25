import json
import platform

from casr.environment import collect_environment, main


def test_collect_environment_reports_local_runtime():
    report = collect_environment()

    assert report["python_version"] == platform.python_version()
    assert report["platform"]
    assert report["cpu_count"] >= 1
    assert report["dependencies"]["networkx"]
    assert report["dependencies"]["pydantic"]
    assert report["dependencies"]["GitPython"]


def test_collect_environment_redacts_model_credentials(monkeypatch):
    secret = "never-print-this-value"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)

    report = collect_environment()

    assert report["model_configuration"]["DEEPSEEK_API_KEY"] == "present"
    assert secret not in str(report)


def test_main_prints_json_without_credentials(monkeypatch, capsys):
    secret = "never-print-this-value"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)

    assert main() == 0

    output = capsys.readouterr().out
    assert json.loads(output)["model_configuration"]["DEEPSEEK_API_KEY"] == "present"
    assert secret not in output
