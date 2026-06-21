import subprocess
import sys
import venv


def test_clean_wheel_install_cli_smoke(tmp_path):
    dist_dir = tmp_path / "dist"
    subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir)], check=True)
    wheel = next(dist_dir.glob("agent_runtime-*.whl"))

    venv_dir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    python = venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

    subprocess.run([str(python), "-m", "pip", "install", "--force-reinstall", str(wheel)], check=True)
    help_result = subprocess.run([str(python), "-m", "agent_runtime.cli.main", "--help"], text=True, capture_output=True, check=True)
    assert "agent-runtime" in help_result.stdout

    config_path = tmp_path / "agent-runtime.json"
    subprocess.run([str(python), "-m", "agent_runtime.cli.main", "init", "--path", str(config_path)], check=True)
    validate = subprocess.run(
        [str(python), "-m", "agent_runtime.cli.main", "validate", "--path", str(config_path)],
        text=True,
        capture_output=True,
        check=True,
    )
    assert validate.returncode == 0
    assert validate.stderr == ""
    assert config_path.exists()
