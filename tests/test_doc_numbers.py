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
    hits = [m.group(0) for m in pat.finditer("x the IPS median falls from $197.6k\n  to $161.5k, y")]
    assert hits == ["the IPS median falls from $197.6k\n  to $161.5k"]          # any wrapping
    assert not pat.search("the IPS median rises from\n$197.6k to $161.5k")     # the words must match


def test_pattern_keeps_a_table_rows_label():
    pat = doc_numbers.pattern("| VTV | 29.9% | 31.5% |")
    doc = "| VUG | 26.8% | 16.0% |\n| VTV | 29.9% | 31.6% |\n"
    assert [m.group(0) for m in pat.finditer(doc)] == ["| VTV | 29.9% | 31.6% |"]   # not VUG's row


def test_fix_rewrites_only_unambiguous_figures(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "MODEL.md").write_text("a:\n  $1.0k here. b: $5.0k and also b: $6.0k.\n")
    (tmp_path / "docs" / "VALIDATION.md").write_text("")
    monkeypatch.setattr(doc_numbers, "ROOT", tmp_path)
    monkeypatch.setattr(doc_numbers, "checks", lambda: [("MODEL", "one", "a: $2.0k here"), ("MODEL", "two", "b: $7.0k")])
    left = doc_numbers.fix()
    assert (tmp_path / "docs" / "MODEL.md").read_text() == "a:\n  $2.0k here. b: $5.0k and also b: $6.0k.\n"  # wrapping kept
    assert [w for _, w, _ in left] == ["two"]                                   # two matches: left for a person


def test_run_all_regenerates_every_report_the_docs_quote():
    """A report the docs quote but run_all does not rewrite would let a model change leave its
    figures stale while the doc check still passed."""
    import re

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    spec = importlib.util.spec_from_file_location("run_all", scripts / "run_all.py")
    run_all = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_all)
    order = [name for name, _, _ in run_all.ORDER if name != "doc_numbers"]
    quoted = set(re.findall(r'R / "([^"]+)"', (scripts / "doc_numbers.py").read_text()))
    writes = re.compile(r"to_csv|write_text|\bOUT\w*\s*=")       # a line that names the file and writes it
    lines = [ln for name in order for ln in (scripts / f"{name}.py").read_text().splitlines() if writes.search(ln)]
    orphans = [f for f in sorted(quoted) if not any(f in ln for ln in lines)]
    assert not orphans, f"quoted in docs but written by no script in run_all: {orphans}"
