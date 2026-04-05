import pytest
from src.core.stages.segment_classification_stage import SegmentClassificationStage
from src.database.models import ProjectType

@pytest.fixture
def classification_stage():
    return SegmentClassificationStage()

class TestSegmentClassificationStage:
    def test_name(self, classification_stage):
        assert classification_stage.name == "segment_classification"

    def test_ambient_classification(self, classification_stage):
        segments = [{"start_time": 0.0, "end_time": 6.0}] # Duration = 6.0, >= 5.0 -> ambient
        result = classification_stage.process(segments)
        assert len(result) == 1
        assert result[0]["type"] == "ambient"
        assert result[0]["metadata"]["classification_confidence"] == 0.85

    def test_one_shot_classification(self, classification_stage):
        segments = [{"start_time": 0.0, "end_time": 1.5}] # Duration = 1.5, <= 2.0 -> one_shot
        result = classification_stage.process(segments)
        assert len(result) == 1
        assert result[0]["type"] == "one_shot"
        assert result[0]["metadata"]["classification_confidence"] == 0.9

    def test_loop_classification(self, classification_stage):
        segments = [{"start_time": 0.0, "end_time": 3.0}] # Duration = 3.0, > 2.0 and < 5.0 -> loop
        result = classification_stage.process(segments)
        assert len(result) == 1
        assert result[0]["type"] == "loop"
        assert result[0]["metadata"]["classification_confidence"] == 0.8

    def test_unknown_classification(self, classification_stage):
        # We need a duration > 32.0 (max_loop_duration) to fail loop, but since ambient_min is 5.0,
        # anything > 5.0 becomes ambient. Let's adjust params to force an unknown.
        segments = [{"start_time": 0.0, "end_time": 40.0}]
        params = {
            "classification_rules": {
                "max_one_shot_duration": 2.0,
                "min_loop_duration": 0.5,
                "max_loop_duration": 32.0,
                "ambient_min_duration": 50.0 # Ambient requires 50s now
            }
        }
        result = classification_stage.process(segments, params=params)
        assert len(result) == 1
        assert result[0]["type"] == "unknown"
        assert result[0]["metadata"]["classification_confidence"] == 0.5

    def test_preserves_existing_metadata(self, classification_stage):
        segments = [{
            "start_time": 0.0, "end_time": 1.5,
            "metadata": {"source": "manual"}
        }]
        result = classification_stage.process(segments)
        assert result[0]["metadata"]["source"] == "manual"
        assert result[0]["metadata"]["classification_reason"] == "Short duration"

    def test_project_type_context(self, classification_stage):
        segments = [{"start_time": 0.0, "end_time": 1.5}]
        context = {"project_type": ProjectType.VIRTUAL_INSTRUMENT}
        result = classification_stage.process(segments, context=context)
        # Even with VIRTUAL_INSTRUMENT, duration classification runs
        assert result[0]["type"] == "one_shot"

