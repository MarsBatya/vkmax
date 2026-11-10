import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


def requirement_name(entry: str) -> str:
    return entry.split(";")[0].split("==")[0].strip().lower()


def test_requirements_match_pyproject_dependencies():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    expected = {requirement_name(dep) for dep in pyproject["project"]["dependencies"]}
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    actual = {
        requirement_name(line)
        for line in lines
        if line.strip() and not line.startswith("#")
    }
    assert actual == expected


def test_py_typed_marker_present():
    assert (ROOT / "vkmax" / "py.typed").is_file()
