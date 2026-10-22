"""The figures quoted in docs/MODEL.md and docs/VALIDATION.md match the committed reports."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("doc_numbers", Path(__file__).resolve().parents[1] / "scripts" / "doc_numbers.py")
doc_numbers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doc_numbers)


def test_docs_quote_the_current_reports():
    bad = doc_numbers.missing()
    assert not bad, "stale figures in the docs (run scripts/doc_numbers.py):\n" + "\n".join(
        f"{doc}: {what}: expected {text!r}" for doc, what, text in bad)


def test_pattern_finds_the_stale_version_of_a_figure():
    pat = doc_numbers.pattern("the IPS median falls from\n$197.2k to $161.2k")
    assert pat.findall("x the IPS median falls from\n$197.6k to $161.5k, y") == ["the IPS median falls from\n$197.6k to $161.5k"]
    assert not pat.findall("the IPS median rises from\n$197.6k to $161.5k")     # the words must match


def test_pattern_keeps_a_table_rows_label():
    pat = doc_numbers.pattern("| VTV | 29.9% | 31.5% |")
    doc = "| VUG | 26.8% | 16.0% |\n| VTV | 29.9% | 31.6% |\n"
    assert pat.findall(doc) == ["| VTV | 29.9% | 31.6% |"]                     # not VUG's row


def test_fix_rewrites_only_unambiguous_figures(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "MODEL.md").write_text("a: $1.0k here. b: $5.0k and also b: $6.0k.\n")
    (tmp_path / "docs" / "VALIDATION.md").write_text("")
    monkeypatch.setattr(doc_numbers, "ROOT", tmp_path)
    monkeypatch.setattr(doc_numbers, "checks", lambda: [("MODEL", "one", "a: $2.0k here"), ("MODEL", "two", "b: $7.0k")])
    left = doc_numbers.fix()
    assert (tmp_path / "docs" / "MODEL.md").read_text() == "a: $2.0k here. b: $5.0k and also b: $6.0k.\n"
    assert [w for _, w, _ in left] == ["two"]                                   # two matches: left for a person
