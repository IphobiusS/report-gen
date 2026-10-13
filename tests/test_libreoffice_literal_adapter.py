"""Contract checks; native installed-extension acceptance runs separately in CI."""
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "integrations" / "libreoffice"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def adapter(monkeypatch):
    # The stand-in tests only policy and delegation. It is not a Writer/UNO
    # acceptance substitute; the native CI installs the complete OXT.
    helper = ModuleType("unohelper")
    helper.Base = type("Base", (), {})
    registrations = []
    helper.ImplementationHelper = lambda: SimpleNamespace(addImplementation=lambda *a: registrations.append(a))
    monkeypatch.setitem(sys.modules, "unohelper", helper)
    for name in ("com", "com.sun", "com.sun.star", "com.sun.star.i18n", "com.sun.star.lang"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    sys.modules["com.sun.star.i18n"].XBreakIterator = type("XBreakIterator", (), {})
    sys.modules["com.sun.star.lang"].XServiceInfo = type("XServiceInfo", (), {})
    module = load(INTEGRATION / "extension" / "technical_literals.py", "adapter_contract")
    module.registrations = registrations
    return module


@pytest.mark.parametrize("prefix", ["URL: ", "Referencia: ", "\U0001f510 URL: ", "e\u0301: "])
def test_utf16_offsets_and_token_edges(adapter, prefix):
    token = "ID_" + "A" * 40
    text = prefix + token + " trailing prose"
    first = len(prefix.encode("utf-16-le")) // 2
    assert adapter.eligible_ascii_cut(text, first + 10, 0)
    assert not adapter.eligible_ascii_cut(text, first, 0)
    assert not adapter.eligible_ascii_cut(text, first + len(token), 0)
    assert not adapter.eligible_ascii_cut(text, first + 10, first + 10)


@pytest.mark.parametrize("text", [
    "pneumonoultramicroscopicsilicovolcanoconiosis",
    "ordinary English words " * 10,
    "ID_short",
    "https://example.test/short",
    "\U0001f469\u200d\U0001f4bb" * 30,
    "a\u0301" * 40,
])
def test_natural_words_short_values_and_unicode_clusters_are_untouched(adapter, text):
    assert not adapter.eligible_ascii_cut(text, 15, 0)


def test_exact_locale_service_only_and_fallback_delegation(adapter):
    builder = load(INTEGRATION / "build_oxt.py", "adapter_constants")
    assert (builder.LANGUAGE_TAG, builder.SERVICE, builder.IMPLEMENTATION) == (
        adapter.LANGUAGE_TAG, adapter.SERVICE, adapter.IMPLEMENTATION)
    assert adapter.registrations[0][2] == (
        "com.sun.star.i18n.BreakIterator_qlt_ZZ_zxx-ZZ-x-rgwrap",)
    assert "com.sun.star.i18n.BreakIterator_qlt" not in adapter.registrations[0][2]
    calls = []
    result = SimpleNamespace(breakIndex=4, breakType=1, rHyphenatedWord="original")
    delegate = SimpleNamespace(getLineBreak=lambda *args: (calls.append(args), result)[1],
                               nextWord=lambda *args: ("untouched", args))
    context = SimpleNamespace(ServiceManager=SimpleNamespace(
        createInstanceWithContext=lambda service, ctx: delegate))
    instance = adapter.TechnicalLiteralIterator(context)
    text = "URL: https://example.test/" + "A" * 40
    for locale in [SimpleNamespace(Language="en", Country="US", Variant=""),
                   SimpleNamespace(Language="qlt", Country="ZZ", Variant="zxx-ZZ-x-other"),
                   SimpleNamespace(Language="qlt", Country="", Variant=adapter.LANGUAGE_TAG)]:
        assert instance.getLineBreak(text, 30, locale, 0, "h", "o") is result
        assert (result.breakIndex, result.breakType, result.rHyphenatedWord) == (4, 1, "original")
    assert len(calls) == 3
    assert instance.nextWord("sample", 4) == ("untouched", ("sample", 4))
    locale = SimpleNamespace(Language="qlt", Country="ZZ", Variant=adapter.LANGUAGE_TAG)
    assert instance.getLineBreak(text, 30, locale, 0, "h", "o") is result
    assert (result.breakIndex, result.breakType, result.rHyphenatedWord) == (30, 0, None)
    assert calls[-1] == (text, 30, locale, 0, "h", "o")


def test_long_paragraph_and_edits_keep_correct_utf16_offsets(adapter):
    tokens = [f"https://bank.example/evidence/{number:02d}/" + "A" * 64 for number in range(72)]
    prefix = "\U0001f510 Evidence: "
    text = prefix + " ".join(tokens)
    for token in tokens:
        position = text.index(token) + 25
        cut = len(text[:position].encode("utf-16-le")) // 2
        assert adapter.eligible_ascii_cut(text, cut, 0)
    # An actual edit displaces all token coordinates; an old cache must not
    # make the newly inserted prose break like a technical literal.
    first_cut = len(prefix.encode("utf-16-le")) // 2 + 25
    edited = "Ordinary new prose. " * 20 + text
    assert not adapter.eligible_ascii_cut(edited, first_cut, 0)
    moved_cut = len(("Ordinary new prose. " * 20).encode("utf-16-le")) // 2 + first_cut
    assert adapter.eligible_ascii_cut(edited, moved_cut, 0)
    assert adapter.eligible_ascii_cut(text, first_cut, 0)


def test_oxt_is_deterministic_explicit_and_carries_license(tmp_path):
    builder = load(INTEGRATION / "build_oxt.py", "oxt_builder")
    first, second = builder.build_oxt(tmp_path / "one.oxt"), builder.build_oxt(tmp_path / "two.oxt")
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {
            "technical_literals.py", "description.xml", "META-INF/manifest.xml", "LICENSE", "SCOPE.txt"}
        assert archive.read("LICENSE") == (ROOT / "LICENSE").read_bytes()
        assert archive.read("technical_literals.py") == (INTEGRATION / "extension" / "technical_literals.py").read_bytes()
        assert b'type=Python' in archive.read("META-INF/manifest.xml")
        assert all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist())
        assert all(info.create_system == 3 and info.external_attr == 0o100644 << 16
                   for info in archive.infolist())


def test_builder_uses_only_selected_bytes_and_rejects_residual_paths(tmp_path):
    builder = load(INTEGRATION / "build_oxt.py", "oxt_selected_bytes")
    payload = {name: ("selected-ref:" + name).encode() for name in builder.PAYLOAD_PATHS}
    path = builder.build_oxt(tmp_path / "selected.oxt", payload)
    with zipfile.ZipFile(path) as archive:
        assert {name: archive.read(name) for name in archive.namelist()} == payload
    for mutation in [dict(payload, **{"../residual": b"bad"}), {"technical_literals.py": b"partial"}]:
        with pytest.raises(ValueError, match="exactly"):
            builder.build_oxt(tmp_path / "rejected.oxt", mutation)
    payload["LICENSE"] = "not bytes"
    with pytest.raises(TypeError, match="bytes"):
        builder.build_oxt(tmp_path / "rejected.oxt", payload)
