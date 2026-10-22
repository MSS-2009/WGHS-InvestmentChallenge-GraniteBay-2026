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
