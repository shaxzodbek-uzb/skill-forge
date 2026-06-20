"""CLI tests — invoke main([...]) in-process."""

from __future__ import annotations

from skill_forge.cli import main
from skill_forge.frontmatter import parse_frontmatter


def test_cli_forge_stdout(capsys, python_project):
    rc = main(["forge", str(python_project), "--stdout"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith("---")
    fields, body = parse_frontmatter(out)
    assert fields["name"] == "widget"
    assert body.strip()


def test_cli_forge_write_and_overwrite(capsys, tmp_path, python_project):
    rc = main(["forge", str(python_project), "-o", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "widget" / "SKILL.md").is_file()
    assert "wrote" in capsys.readouterr().out

    # second write without --force fails cleanly
    rc = main(["forge", str(python_project), "-o", str(tmp_path)])
    assert rc == 1
    assert "already exists" in capsys.readouterr().err

    rc = main(["forge", str(python_project), "-o", str(tmp_path), "--force"])
    assert rc == 0


def test_cli_lint_good(capsys, tmp_path, python_project):
    main(["forge", str(python_project), "-o", str(tmp_path)])
    capsys.readouterr()
    rc = main(["lint", str(tmp_path)])
    assert rc == 0
    assert "valid" in capsys.readouterr().out


def test_cli_lint_bad(capsys, tmp_path):
    bad = tmp_path / "broken"
    bad.mkdir()
    (bad / "SKILL.md").write_text("no frontmatter at all\n", encoding="utf-8")
    rc = main(["lint", str(bad / "SKILL.md")])
    assert rc == 1
    assert "✗" in capsys.readouterr().out


def test_cli_check_in_sync_then_drift(capsys, tmp_path, python_project):
    main(["forge", str(python_project), "-o", str(tmp_path)])
    capsys.readouterr()

    rc = main(["check", str(python_project), "-o", str(tmp_path), "--name", "widget"])
    assert rc == 0
    assert "in sync" in capsys.readouterr().out

    target = tmp_path / "widget" / "SKILL.md"
    target.write_text(target.read_text(encoding="utf-8") + "\nextra drift\n", encoding="utf-8")
    rc = main(["check", str(python_project), "-o", str(tmp_path), "--name", "widget"])
    assert rc == 1
    assert "drifted" in capsys.readouterr().out


def test_cli_version(capsys):
    rc = main(["version"])
    assert rc == 0
    assert "skill-forge" in capsys.readouterr().out


def test_cli_unknown_source_errors(capsys, tmp_path):
    rc = main(["forge", str(tmp_path / "nope")])
    assert rc == 1
    assert "error:" in capsys.readouterr().err
