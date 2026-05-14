#!/usr/bin/env python
"""Compatibility wrapper for the uv-managed AutoGrade CLI."""

from autograde_tool.cli import main


if __name__ == "__main__":
    raise SystemExit(main())

