"""Release guards reject generated images, lost runtime assets and oversized files."""
from io import BytesIO
import tarfile
import zipfile

import pytest

from scripts.validate_dist import RUNTIME_FILES, validate_dist


def distributions(directory, *, generated=False, omit=None):
    wheel = directory / "hsr_cards-1.1.0-py3-none-any.whl"
    source = directory / "hsr_cards-1.1.0.tar.gz"
    files = {name: b"runtime file" for name in RUNTIME_FILES if name != omit}
    if generated:
        files["hsr_cards/assets/char_builds/acheron/acheron.png"] = b"generated card"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, contents in files.items():
            archive.writestr(name, contents)
    sources = {"src/" + name: contents for name, contents in files.items()}
    sources.update({name: b"source metadata" for name in ("README.md", "LICENSE", "pyproject.toml", "MANIFEST.in")})
    with tarfile.open(source, "w:gz") as archive:
        for name, contents in sources.items():
            member = tarfile.TarInfo("hsr_cards-1.1.0/" + name)
            member.size = len(contents)
            archive.addfile(member, BytesIO(contents))
    return wheel, source


def test_small_complete_distributions_are_accepted(tmp_path):
    distributions(tmp_path)
    assert validate_dist(tmp_path) == []


def test_generated_cards_are_rejected_in_both_package_formats(tmp_path):
    wheel, source = distributions(tmp_path, generated=True)
    issues = validate_dist(tmp_path)
    assert len(issues) == 2
    assert all("generated build files" in issue for issue in issues)
    assert any(wheel.name in issue for issue in issues)
    assert any(source.name in issue for issue in issues)


def test_required_fonts_are_not_lost_when_trimming_generated_assets(tmp_path):
    distributions(tmp_path, omit="hsr_cards/assets/fonts/optimized_global_web.woff2")
    issues = validate_dist(tmp_path)
    assert len(issues) == 2
    assert all("missing runtime/source file" in issue and "optimized_global_web.woff2" in issue for issue in issues)


def test_file_size_limit_is_checked_before_upload(tmp_path):
    distributions(tmp_path)
    issues = validate_dist(tmp_path, max_size=100)
    assert sum("exceeds" in issue for issue in issues) == 2


def test_missing_or_stale_distribution_outputs_fail(tmp_path):
    assert len(validate_dist(tmp_path)) == 2
    wheel, _ = distributions(tmp_path)
    (tmp_path / "hsr_cards-1.0.9-py3-none-any.whl").write_bytes(wheel.read_bytes())
    assert any("one wheel" in issue for issue in validate_dist(tmp_path))


@pytest.mark.parametrize("name", ["hsr_cards-1.1.0-py3-none-any.whl", "hsr_cards-1.1.0.tar.gz"])
def test_corrupt_distribution_is_reported(tmp_path, name):
    distributions(tmp_path)
    (tmp_path / name).write_bytes(b"not an archive")
    assert any("unreadable archive" in issue for issue in validate_dist(tmp_path))
