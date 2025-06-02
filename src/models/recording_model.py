# Placeholder for recording_model.py
class RecordingModel:
    def __init__(self, id=None, project_id=None, name=None, samples=None):
        self.id = id
        self.project_id = project_id
        self.name = name
        self.samples = samples if samples is not None else []
