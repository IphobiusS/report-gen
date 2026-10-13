"""Portuguese is a launch preference, never a rewrite of report data."""
import json
import os
from types import SimpleNamespace

import pytest

import delivery_signature
import diagnostics
from error_messages import message
from languages import language_argument, language_tag, normalize_language
import start


@pytest.mark.parametrize("value", ["pt", "pt-BR", "PT-br", " pt-BR "])
def test_portuguese_aliases_have_one_persisted_key_and_public_tag(value):
    assert language_argument(value) == "pt"
    assert language_tag(value) == "pt-BR"


@pytest.mark.parametrize("value", [None, [], {}, "fr", "", "pt-PT", "../pt"])
def test_unsupported_language_does_not_silently_become_a_valid_cli_choice(value):
    assert normalize_language(value, None) is None
    with pytest.raises(ValueError):
        language_argument(value)


def test_launcher_passes_portuguese_then_restores_parent_preference(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REPORT_GEN_UI_LANG", "en")
    monkeypatch.setattr(start, "ROOT", tmp_path)
    monkeypatch.setattr(start, "_dependencies", lambda _python: True)
    observed = []
    monkeypatch.setattr(start, "_run_server", lambda _python, _port:
                        observed.append(os.environ["REPORT_GEN_UI_LANG"]) or 0)
    assert start.main(["--lang", "pt-BR"]) == 0
    assert observed == ["pt"]
    assert os.environ["REPORT_GEN_UI_LANG"] == "en"
    assert "Dados:" in capsys.readouterr().out
    assert not (tmp_path / "webapp/projects").exists()


def test_diagnostic_prose_is_portuguese_without_installing_anything(monkeypatch):
    monkeypatch.setattr(diagnostics, "weasy", lambda _root: None)
    monkeypatch.setattr(diagnostics, "chromium", lambda _root: None)
    monkeypatch.setattr(diagnostics, "word", lambda _root: None)
    result = diagnostics.run("pt-BR")
    assert result["editor_ready"] and result["pdf_ready"]
    assert result["checks"][2]["label"] == "Word editável"
    assert all(row["detail"] == "Teste de exportação aprovado" for row in result["checks"])
    assert "computador" in result["note"]


def test_launch_preparation_errors_share_selected_language(monkeypatch, capsys):
    def invalid_workspace(*_args):
        raise ValueError(message("Prueba de ruta: {path}", en="Path test: {path}",
                                 pt="Teste de caminho: {path}", path="English Español.pem"))
    monkeypatch.setattr(start, "select_workspace", invalid_workspace)
    assert start.main(["--lang", "pt-BR"]) == 1
    assert "Teste de caminho: English Español.pem" in capsys.readouterr().err


def test_launch_hint_preserves_language_for_the_next_session(tmp_path):
    import shlex
    selection = SimpleNamespace(external=True, root=tmp_path / "dados privados")
    command = start._launch_hint(selection, "pt-BR")
    assert "--lang pt" in command
    if os.name != "nt":
        words = shlex.split(command)
        assert words[words.index("--workspace") + 1] == str(selection.root)
        assert words[words.index("--lang") + 1] == "pt"


def test_signing_help_is_portuguese_and_has_no_side_effects(capsys):
    with pytest.raises(SystemExit) as exc:
        delivery_signature.main(["--lang", "pt-BR", "--help"])
    assert exc.value.code == 0
    text = capsys.readouterr().out
    assert "Assinatura local opcional" in text
    assert "Gera novas chaves Ed25519" in text


def test_signing_failure_keeps_portuguese_scope_and_opaque_path(tmp_path, capsys):
    missing = tmp_path / "Spanish English Português.pem"
    assert delivery_signature.main(["--lang", "pt", "fingerprint", "--public-key", str(missing)]) == 1
    result = json.loads(capsys.readouterr().err)
    assert result["language"] == "pt"
    assert "Não foi possível acessar" in result["error"]
