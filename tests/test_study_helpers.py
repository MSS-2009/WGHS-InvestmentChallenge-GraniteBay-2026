"""Pure helpers inside the study scripts (scripts/ is not a package, so they load by path)."""
import importlib.util
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cov(k: int = 4, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((400, k + 5)) @ rng.standard_normal((k + 5, k + 5))
    return np.cov(x, rowvar=False)


def test_scaling_the_equity_rate_block_keeps_variances_and_stays_psd():
    scaled = _load("stock_rate_corr").scaled
    cov, k = _cov(), 4
    for c in (0.0, 0.5, 1.0):                        # mixes of the matrix and its block diagonal: PSD as is
        out, repaired = scaled(cov, k, c)
        assert repaired == 0.0
        assert np.allclose(np.diag(out), np.diag(cov))
        assert np.allclose(out[:k, k:k + 3], c * cov[:k, k:k + 3])
        assert np.allclose(out[k + 3:, :], cov[k + 3:, :])
    out, repaired = scaled(cov, k, -3.0)             # far outside: repaired, variances restored
    assert repaired < 0 and np.linalg.eigvalsh(out).min() > -1e-10
    assert np.allclose(np.diag(out), np.diag(cov))


def test_ledoit_wolf_intensity_toward_a_target():
    lw_intensity = _load("corr_shrink_oos").lw_intensity     # off-diagonal entries only (correlations)
    rng = np.random.default_rng(1)
    std = lambda x: (x - x.mean(0)) / x.std(0)
    eye = np.eye(6)
    # truly uncorrelated data: the identity target is right, so shrink (nearly) all the way
    assert lw_intensity(std(rng.standard_normal((120, 6))), eye) > 0.7
    # strongly correlated data and many months: the identity target is wrong, so shrink little
    x = std(rng.standard_normal((2000, 6)) + 2 * rng.standard_normal((2000, 1)))
    assert lw_intensity(x, eye) < 0.05
    # a target equal to the sample correlations: nothing to lose by shrinking
    assert lw_intensity(x, np.corrcoef(x, rowvar=False)) == 1.0
