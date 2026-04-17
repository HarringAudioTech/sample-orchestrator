# Implementation Plan: Optimize Dockerfile Build with `uv`

## Objective
Optimize the `Dockerfile` build stage by using `uv` (a fast Python package installer and resolver) and official Python 3.14 base images. This will significantly reduce build time and image size compared to the current `pip`-based approach, especially for heavy dependencies like PyTorch, while maintaining full compatibility with the project's Python 3.14 requirement.

## Key Files & Context
- `Dockerfile`: The build specification.
- `pyproject.toml` / `uv.lock`: Project dependency files.

## Implementation Steps
1.  **Update Builder Base Image**:
    -   Change the builder stage to use `FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder`. This image is extremely fast, comes with `uv` baked in, and has the required Python 3.14.
2.  **Use `uv` to Install Dependencies**:
    -   Replace the `pip install` command with `uv sync` or `uv pip install`.
    -   Utilize `uv` cache mounts (`--mount=type=cache,target=/root/.cache/uv`) to avoid re-downloading PyTorch and other large packages across builds.
3.  **Optimize System Dependencies**:
    -   Update the `apt-get install` step to include only necessary build tools (`libasound2-dev`, `libsndfile1-dev`, `portaudio19-dev`).
    -   Since the `bookworm-slim` image is very small, we will need to ensure `build-essential` and `git` are included for compiling C extensions and installing git-based dependencies.
4.  **Final Runtime Stage**:
    -   Use `FROM python:3.14-slim` for the final runtime image to keep it lightweight.
    -   Copy the installed site-packages from the builder stage (`/install` or equivalent).

## Verification & Testing
1.  **Build Validation**: Run `docker compose build app` and verify that the build succeeds and is noticeably faster due to `uv`'s performance.
2.  **Runtime Validation**: Run `docker compose up app` to confirm the application starts correctly with the installed dependencies.