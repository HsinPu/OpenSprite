"""Entry point for running OpenSprite as a module: python -m opensprite."""

from .app.cli.commands import app


if __name__ == "__main__":
    app()
