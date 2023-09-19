#!/usr/bin/env python3
import os
from pathlib import Path

import typer

from theatre.main_window import display as _display


def display(
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
    app.command(name="run", no_args_is_help=True)(display)


if __name__ == "__main__":
    _display()
