"""Data-related UI routes for the sample orchestrator application."""

import datetime
from flask import render_template, abort, Blueprint
from src.database.utils import get_db
from src.database.models import RecordingModel, SampleModel

data_bp = Blueprint(
    "data_bp",
    __name__,
    template_folder="../templates/ui",  # Points to src/templates/ui
)

@data_bp.route("/recordings/<int:recording_id>")
def view_recording(recording_id: int) -> str:
    """Renders the page for viewing a single recording and its samples."""
    with get_db() as db:
        recording = db.query(RecordingModel).filter(RecordingModel.id == recording_id).first()
        if not recording:
            abort(404, description=f"Recording with ID {recording_id} not found.")

        samples = db.query(SampleModel).filter(SampleModel.recording_id == recording_id).all()

        return render_template(
            "view_recording.html",
            title=f"Recording - {recording.name}",
            recording=recording,
            samples=samples,
            now=datetime.datetime.now()
        )

@data_bp.route("/samples/<int:sample_id>")
def view_sample(sample_id: int) -> str:
    """Renders the page for viewing a single sample."""
    with get_db() as db:
        sample = db.query(SampleModel).filter(SampleModel.id == sample_id).first()
        if not sample:
            abort(404, description=f"Sample with ID {sample_id} not found.")

        return render_template(
            "view_sample.html",
            title=f"Sample - {sample.id}",
            sample=sample,
            now=datetime.datetime.now()
        )
