# Agent Instructions for Core Logic

This guide provides instructions for working with the core audio processing components of this project.

## Adding a New Audio Processing Stage

1.  **Create a new file** in the `src/core/stages/` directory (e.g., `my_new_stage.py`).
2.  **Define a new class** in that file that inherits from `AudioProcessingStage` (found in `src/core/processing_stages.py`).
3.  **Implement the required abstract properties** in your new class:
    * `name`: A unique, snake_case name for your stage.
    * `description`: A clear, concise description of what the stage does.
    * `input_type` and `output_type`: Use the `DATA_TYPE_*` constants from `src/core/processing_stages.py`.
    * `default_params`: A dictionary of default parameters for your stage.
4.  **Implement the `process` method**: This is where you'll put the logic for your stage.
5.  **Register your new stage**: At the end of your new stage's file, call `register_stage(YourStageClass)` from `src/core/stage_runner.py`.

## Creating a New Workflow

1.  **Add a new class** to `src/core/workflows.py` that inherits from `BaseWorkflow`.
2.  **Implement the required abstract properties**:
    * `name`: A unique, human-readable name for your workflow.
    * `description`: A clear description of what the workflow does.
    * `stages_definition`: A list of dictionaries defining the sequence of stages and their parameters.
3.  **Register your new workflow**: At the end of `src/core/workflows.py`, call `register_workflow(YourWorkflowClass)`.

## Testing Core Components

- When you add a new stage or workflow, create a corresponding test file in the `tests/core/` directory.
- For a new stage, add a test file to `tests/core/stages/`.
- For a new workflow, add tests to `tests/core/test_workflows.py`.