import pytest
import datetime
from src.core.workflows import WORKFLOW_REGISTRY, BaseWorkflow
from jinja2 import Environment, FileSystemLoader

def test_workflow_template_iteration():
    env = Environment(loader=FileSystemLoader(["src/templates/ui", "src/templates"]))
    template = env.get_template("process_recording.html")

    workflows = WORKFLOW_REGISTRY.copy()
    workflows_instances = {}
    for name, workflow_class in workflows.items():
        try:
            # Try to instantiate without args first (for legacy compatibility if any)
            workflows_instances[name] = workflow_class()
        except TypeError:
            # Handle workflows that require a db_session (like SamplePackWorkflow)
            from unittest.mock import MagicMock
            workflows_instances[name] = workflow_class(db_session=MagicMock())

    # We mock project, recording, and stages as they are needed for the template to compile without failing
    class MockProject: id = 1; name = "test"
    class MockRecording: id = 1; name = "test"
    class MockRequest: endpoint = "ui_bp.index"

    try:
        html = template.render(
            project=MockProject(),
            recording=MockRecording(),
            request=MockRequest(),
            now=datetime.datetime.now(),
            workflows=workflows_instances,
            stages={},
            url_for=lambda endpoint, **kwargs: "/mock/url",
            get_flashed_messages=lambda **kwargs: []
        )
        # Verify it renders the stages properly (check for "slicing" since both workflows use it)
        assert "slicing" in html
        assert "A simple example workflow" in html
    except Exception as e:
        pytest.fail(f"Template rendering failed: {e}")
