#!/usr/bin/env python3
import os
import sys
import typing
from pathlib import Path

import typer
from qtpy.QtWidgets import QApplication

from theatre.charm_repo_tools import CharmRepo
from theatre.logger import logger as theatre_logger
from theatre.main_window import TheatreMainWindow

logger = theatre_logger.getChild(__file__)


def show_main_window(cwd: Path = None):
    app = QApplication([])
    app.setStyle("Fusion")

    window = TheatreMainWindow()
    if window.SHOW_MAXIMIZED:
        window.showMaximized()
    else:
        window.show()

    if cwd:
        repo = CharmRepo(cwd)

        if repo.is_valid:
            logger.info("charm repo root detected")
            if repo.is_initialized:
                logger.info(".theatre found, resuming...")
                window.resume_from_charm_repo(repo)

            else:
                logger.info("no .theatre found, attempting init...")
                repo.initialize()

        if repo.current_scene:
            window.open_if_not_already_open(repo.current_scene)
    else:
        dummy_scene = Path("~/.local/share/theatre/scenes/myscene.scene").expanduser()
        window.open_if_not_already_open(dummy_scene)

    sys.exit(app.exec_())


def _display(path: typing.Optional[Path] = None):
    """Open the charm at this path in Theatre."""
    path = Path(path or os.getcwd())
    show_main_window(path)


def run(
    path: Path = typer.Option(
        None,
        "--path",
        "-p",
        "A charm repository root in which to run scenario. " "Defaults to the CWD.",
    )
):
    _display(path)


def main():
    app = typer.Typer(
        name="theatre",
        help="Scenario graphical runtime. "
        "For docs, issues and feature requests, visit "
        "the github repo --> https://github.com/PietroPasotti/theatre",
        no_args_is_help=True,
        rich_markup_mode="markdown",
    )
    app.command(name="foo", hidden=True)(
        lambda: None
    )  # prevent subcommand from taking over
    app.command(name="run", no_args_is_help=True)(run)


if __name__ == "__main__":
    main()
