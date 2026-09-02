"""Provider-agnostic catalog and access layer for public data."""

from importlib.metadata import version

from dataregistrar.model import Kind, Record, Status

__version__ = version("dataregistrar")

__all__ = ["Kind", "Record", "Status", "__version__"]
