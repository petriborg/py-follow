#!/usr/bin/env bash
# Install the py-follow package using uv (modern pip alternative)
# Ensure uv is installed: https://github.com/astral-sh/uv
# This script creates an editable install in the current environment.

set -e

# Use uv to install the package in editable mode
uv pip install -e .
