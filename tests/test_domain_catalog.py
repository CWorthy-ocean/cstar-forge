"""Tests for DomainCatalog GitHub URL handling."""

from pathlib import Path
from unittest.mock import patch

import pytest

from cstar_forge.domain_catalog import (
    DomainCatalog,
    _is_github_catalog_url,
    _parse_github_catalog_url,
)


@pytest.mark.parametrize(
    "url,expected",
    [
        (
            "https://github.com/CWorthy-ocean/cstar-forge",
            ("CWorthy-ocean", "cstar-forge", Path(".")),
        ),
        (
            "https://github.com/CWorthy-ocean/cstar-forge/",
            ("CWorthy-ocean", "cstar-forge", Path(".")),
        ),
        (
            "https://github.com/CWorthy-ocean/cstar-forge/tree/main/cstar_forge/catalog",
            ("CWorthy-ocean", "cstar-forge", Path("cstar_forge/catalog")),
        ),
        (
            "git@github.com:CWorthy-ocean/cstar-forge.git",
            ("CWorthy-ocean", "cstar-forge", Path(".")),
        ),
    ],
)
def test_parse_github_catalog_url(url, expected):
    assert _parse_github_catalog_url(url) == expected


def test_is_github_catalog_url():
    assert _is_github_catalog_url("https://github.com/org/repo")
    assert _is_github_catalog_url("git@github.com:org/repo.git")
    assert not _is_github_catalog_url("/local/path/with/github/in/name")
    assert not _is_github_catalog_url("local")


def test_github_catalog_uses_org_and_repo():
    url = "https://github.com/CWorthy-ocean/cstar-forge"
    with patch("cstar_forge.domain_catalog.fsspec.filesystem") as mock_fs:
        mock_fs.return_value.exists = lambda _path: False
        catalog = DomainCatalog(
            catalog_root=url,
            suppress_validation=True,
        )
    mock_fs.assert_called_once_with("github", org="CWorthy-ocean", repo="cstar-forge")
    assert catalog.catalog_root == Path(".")
    assert catalog._fs is mock_fs.return_value


def test_parse_github_catalog_url_invalid():
    with pytest.raises(ValueError, match="Could not parse GitHub org/repo"):
        _parse_github_catalog_url("https://github.com/only-org")
