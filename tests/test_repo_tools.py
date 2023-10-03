from pathlib import Path

import pytest
import yaml
from scenario import State, Container
from scenario.runtime import UncaughtCharmError

from theatre.charm_repo_tools import CharmRepo
from theatre.trace_tree_widget.state_node import add_simulated_fs_from_repo

charmpy = """
from ops import CharmBase, Framework

class MyCharm(CharmBase):
  
    def __init__(self, framework: Framework):
        super().__init__(framework)
        framework.observe(self.on.start, self._on_start)

    def _on_start(self, _):
        cts = self.unit.get_container('foo').pull("/opt/baz/qux.yaml").read()
        assert "hello world" == cts, f"hello world not found: {cts} instead"
"""


LOADER = """
from scenario import Context
from charm import MyCharm

def charm_context():
    return Context(charm_type=MyCharm)
"""


def setup_vroot(tempdir: Path):
    tempdir.joinpath("src").mkdir()
    tempdir.joinpath("src", "charm.py").write_text(charmpy)
    tempdir.joinpath("metadata.yaml").write_text(
        yaml.safe_dump({"name": "roberto", "containers": {"foo": {}}})
    )


def test_vroot_init(tmp_path):
    setup_vroot(tmp_path)
    repo = CharmRepo(tmp_path)
    repo.initialize()

    assert (
        tmp_path / ".theatre" / "virtual_fs" / "default" / "foo" / "spec.yaml"
    ).exists()


def test_repo_ctx_exec_if_default_not_setup(tmp_path):
    setup_vroot(tmp_path)
    repo = CharmRepo(tmp_path)
    repo.initialize()
    (tmp_path / ".theatre" / "loader.py").write_text(LOADER)

    ctx = repo.load_context()
    assert ctx.charm_spec.charm_type.__name__ == "MyCharm"
    raw_state = State(containers=[Container("foo", can_connect=True)])

    # this will run the assertion and verify that the charm can indeed access /opt/baz/qux.yaml
    with pytest.raises(UncaughtCharmError):
        ctx.run("start", add_simulated_fs_from_repo(raw_state, repo))


def test_repo_ctx_exec_default_setup(tmp_path):
    """Verify that if we set up properly the default mount for foo, things go well."""
    setup_vroot(tmp_path)
    repo = CharmRepo(tmp_path)
    repo.initialize()
    (tmp_path / ".theatre" / "loader.py").write_text(LOADER)

    ctx = repo.load_context()
    assert ctx.charm_spec.charm_type.__name__ == "MyCharm"

    foo_vfs = tmp_path / ".theatre" / "virtual_fs" / "default" / "foo"

    # put qux.yaml in {local vfs}/kazoo/
    qux = foo_vfs.joinpath("kazoo", "qux.yaml")
    qux.parent.mkdir(parents=True)
    qux.write_text("hello world")

    # tell theatre that whatever is in /kazoo should be mounted at /opt/baz/
    foo_vfs.joinpath("spec.yaml").write_text(
        yaml.safe_dump({"foo": {"mounts": {"/opt/baz/": "kazoo"}}})
    )
    raw_state = State(containers=[Container("foo", can_connect=True)])

    # this will run the assertion and verify that the charm can indeed access /opt/baz/qux.yaml
    state_with_fs = add_simulated_fs_from_repo(raw_state, repo)
    assert state_with_fs.get_container("foo").mounts
    ctx.run("start", state_with_fs)
