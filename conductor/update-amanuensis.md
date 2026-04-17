# Implementation Plan: Update Amanuensis to v0.3 (Python 3.14 Support)

## Objective
Update the `amanuensis` dependency from the `trunk` branch to the `v0.3` release tag in both the project configuration and Dockerfile. This is necessary because v0.3 introduces support for Python 3.14, resolving the build failures encountered when attempting to build the project's Docker image using the modern Python 3.14 base image.

## Key Files & Context
- `pyproject.toml`: Contains project dependencies, currently specifying `amanuensis` from the `trunk` branch.
- `Dockerfile`: The build specification for the project, currently cloning `amanuensis` from the `trunk` branch.

## Implementation Steps
1.  **Update `pyproject.toml`**:
    -   Locate the `amanuensis` dependency definition.
    -   Replace `{ git = "https://github.com/HarringAudioTech/amanuensis.git", branch = "trunk" }` with `{ git = "https://github.com/HarringAudioTech/amanuensis.git", tag = "v0.3" }`.
2.  **Update `Dockerfile`**:
    -   Locate the `pip install` command section in the builder stage.
    -   Replace `"amanuensis @ git+https://${TOKEN}@github.com/HarringAudioTech/amanuensis.git@trunk"` with `"amanuensis @ git+https://${TOKEN}@github.com/HarringAudioTech/amanuensis.git@v0.3"`.

## Verification & Testing
1.  **Validate Changes**: Check that `pyproject.toml` and `Dockerfile` reflect the `v0.3` tag update.
2.  **Build Validation**: After the plan is approved and implemented, the Docker image should be rebuilt to ensure that the pip installation succeeds with the new Amanuensis v0.3 dependency running on Python 3.14.