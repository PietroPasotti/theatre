import json
from pathlib import Path
from typing import Optional

from scenario import Context, State

from theatre.config import TEMPLATES_DIR
from theatre.helpers import load_module
from theatre.logger import logger

LOADER_TEMPLATE = TEMPLATES_DIR / "loader_template.py"


class InvalidLoader(RuntimeError):
    """Raised if the contents of .theatre/loader.py are invalid."""


class TheatreState:
    def __init__(self, theatre_dir: Path):
        self.file = theatre_dir / "state.json"

        self.current_scene_path: Optional[Path] = None

        if self.file.exists():
            self.reload()

    def reload(self):
        if not self.file.exists():
            logger.debug("cannot load state: state file does not exist")
            return

        raw = json.loads(self.file.read_text())
        current_scene_path = raw.get("current_scene_path")
        self.current_scene_path = (
            Path(current_scene_path) if current_scene_path else None
        )


class CharmRepo:
    def __init__(self, path: Path):
        self._root = path
        self.state = TheatreState(self.theatre_dir)

    @property
    def theatre_dir(self):
        return self.root / ".theatre"

    @property
    def root(self) -> Path:
        return self._root

    @property
    def is_valid(self):
        return all(
            expected_file.exists()
            for expected_file in [
                self.root / "metadata.yaml",
                self.root / "src" / "charm.py",
            ]
        )

    @property
    def is_initialized(self) -> bool:
        return self.theatre_dir.exists()

    @property
    def loader_path(self) -> Path:
        return self.theatre_dir / "loader.py"

    def has_loader(self) -> bool:
        return self.loader_path.exists()

    def initialize(self):
        self.theatre_dir.mkdir(parents=True)

        loader_file = self.loader_path
        # todo: load charm type from charm.py and inject the import in the template
        loader_file.write_bytes(LOADER_TEMPLATE.read_bytes())
        print(f"created {loader_file}: put there your charm loader for this repo")

        self.state.file.write_text("{}")
        logger.info(f"created {self.state.file}")

        scenes = self.theatre_dir / "scenes"
        scenes.mkdir()
        logger.info(f"created {scenes}")
        self.state.reload()

    def load_context(self):
        return load_charm_context(self.root, self.loader_path)

    @property
    def current_scene(self):
        current_scene_path = self.state.current_scene_path
        if current_scene_path and current_scene_path.exists():
            return current_scene_path.read_text()


def load_charm_context(
    root: Path, loader_path: Path = TEMPLATES_DIR / "loader_template.py"
):
    logger.info(f"Loading charm context from repo: {root}.")
    module = load_module(loader_path, add_to_path=[root / "lib", root / "src"])

    logger.info(f"imported module {module}.")
    context_getter = getattr(module, "charm_context", None)

    if not context_getter:
        raise InvalidLoader("missing charm_context function definition")

    if not callable(context_getter):
        raise InvalidLoader(
            f"{loader_path}::context_getter should be of type Callable[[], Context]"
        )

    try:
        ctx = context_getter()
    except Exception as e:
        raise InvalidLoader(
            f"{loader_path}::context_getter() raised an exception"
        ) from e

    if not isinstance(ctx, Context):
        raise InvalidLoader(
            f"{loader_path}::context_getter() returned {type(ctx)}: "
            f"instead of scenario.Context"
        )

    logger.info(
        f"Successfully loaded charm {ctx.charm_spec.charm_type} context from {loader_path}."
    )
    return ctx
