import json
from pathlib import Path

from theatre.charm_repo_tools import CharmRepo


def init_mock_charm_root(root, charm_source="", meta_source=""):
    src = root / "src"
    src.mkdir()
    (src / "charm.py").write_text(charm_source)
    (root / "metadata.yaml").write_text(meta_source)


def init_theatre(root, loader_source="", state_source=""):
    theatre_dir = root / ".theatre"
    theatre_dir.mkdir()
    (theatre_dir / "loader.py").write_text(loader_source)
    (theatre_dir / "state.json").write_text(state_source)
    (theatre_dir / "scenes").mkdir()


def test_theatre_invalid(tmp_path):
    repo = CharmRepo(tmp_path)
    assert not repo.is_valid
    assert not repo.is_initialized


def test_theatre_valid(tmp_path):
    init_mock_charm_root(tmp_path)
    repo = CharmRepo(tmp_path)
    assert repo.is_valid
    assert not repo.is_initialized


def test_theatre_inited(tmp_path):
    init_mock_charm_root(tmp_path)
    init_theatre(tmp_path)
    repo = CharmRepo(tmp_path)
    assert repo.is_valid
    assert repo.is_initialized


def test_theatre_init(tmp_path):
    init_mock_charm_root(tmp_path)
    repo = CharmRepo(tmp_path)
    assert repo.is_valid
    assert not repo.is_initialized
    repo.initialize()
    assert repo.is_initialized


def test_state(tmp_path):
    init_mock_charm_root(tmp_path)
    init_theatre(tmp_path)
    repo = CharmRepo(tmp_path)
    assert repo.state.current_scene_path is None


def test_state_scenepath(tmp_path):
    init_mock_charm_root(tmp_path)
    init_theatre(tmp_path, state_source=json.dumps({"current_scene_path": "foo.py"}))
    repo = CharmRepo(tmp_path)
    assert repo.state.current_scene_path == Path("foo.py")
