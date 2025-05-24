import os
import wave
from sqlalchemy.orm import Session
from src.database.models import Project as ProjectModel, Recording as RecordingModel
from src.database.utils import get_db, SessionLocal
from aubio import (
    source,
)  # aubio.notes is not directly used here, but in audio_processor


class Project:
    """
    Manages operations related to a specific project, such as adding,
    retrieving, and processing audio recordings associated with it.

    Attributes:
        project_id (int): The ID of the project this instance manages.
        project_model (ProjectModel): The SQLAlchemy model instance for this project,
                                      loaded from the database.
    """

    def __init__(self, project_id: int):
        """
        Initializes a Project instance by loading its data from the database.

        Args:
            project_id (int): The ID of the project to load.

        Raises:
            ValueError: If no project with the given `project_id` is found in the database.
        """
        # Uses a new session that is closed after loading.
        db_gen = get_db()
        db: Session = next(db_gen)
        try:
            self.project_model = (
                db.query(ProjectModel).filter(
                    ProjectModel.id == project_id).first()
            )
            if not self.project_model:
                raise ValueError(f"Project with id {project_id} not found")
            self.project_id = project_id
        finally:
            next(db_gen, None)  # Ensure generator is exhausted and session closed

    def add_recording(self, file_path: str, name: str) -> RecordingModel:
        """
        Adds a new audio recording to the current project.

        This method extracts metadata (duration, samplerate, channels) from the
        audio file, creates a new Recording entry in the database, and associates
        it with this project.

        Args:
            file_path (str): The absolute or relative path to the audio file.
            name (str): A user-friendly name for this recording.

        Returns:
            RecordingModel: The newly created SQLAlchemy Recording model instance.

        Raises:
            FileNotFoundError: If the audio file at `file_path` does not exist.
            Exception: Can re-raise exceptions from `aubio.source` or `wave.open`
                       if audio file metadata extraction fails for other reasons.
        """
        db: Session = SessionLocal()  # New session for this transaction
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(
                    f"Recording file not found: {file_path}")

            duration_seconds = None
            samplerate = None
            channels = None

            try:
                # Use aubio to get samplerate, as it will be used for
                # processing
                s = source(
                    file_path, 0, 512
                )  # hop_size = 512, samplerate = 0 (use original)
                samplerate = s.samplerate
                # Use wave module for duration and channels as it's more direct
                # for these properties
                with wave.open(file_path, "rb") as wf:
                    frames = wf.getnframes()
                    rate_wave = wf.getframerate()
                    duration_seconds = frames / float(rate_wave)
                    channels = wf.getnchannels()
                    if (
                        samplerate == 0
                    ):  # If aubio couldn't determine samplerate (e.g. non-wav)
                        samplerate = rate_wave
                    elif samplerate != rate_wave:
                        # This can happen if aubio and wave interpret file differently, or if aubio was forced to resample
                        # For consistency, if aubio provides a samplerate,
                        # prefer it.
                        print(
                            f"Warning: aubio samplerate {samplerate} and wave module samplerate {rate_wave} differ for {file_path}. Using aubio's.")
            except Exception as e:
                # Log error but proceed to add recording entry without full
                # metadata if necessary
                print(
                    f"Error getting audio properties for {file_path}: {e}. Recording will be added with available metadata.")

            new_recording = RecordingModel(
                project_id=self.project_id,
                name=name,
                file_path=file_path,  # Store the original path
                duration_seconds=duration_seconds,
                samplerate=samplerate,
                channels=channels,
                status="pending",  # Initial status
            )
            db.add(new_recording)
            db.commit()
            db.refresh(new_recording)
            return new_recording
        finally:
            db.close()

    def get_recording(self, recording_id: int) -> RecordingModel | None:
        """
        Retrieves a specific recording associated with this project by its ID.

        Args:
            recording_id (int): The ID of the recording to retrieve.

        Returns:
            RecordingModel | None: The SQLAlchemy Recording model instance if found,
                                   otherwise None.
        """
        db_gen = get_db()
        db: Session = next(db_gen)
        try:
            recording = (
                db.query(RecordingModel)
                .filter(
                    RecordingModel.id == recording_id,
                    RecordingModel.project_id == self.project_id,
                )
                .first()
            )
            return recording
        finally:
            next(db_gen, None)

    def list_recordings(self) -> list[RecordingModel]:
        """
        Lists all recordings associated with this project.

        Returns:
            list[RecordingModel]: A list of SQLAlchemy Recording model instances.
        """
        db_gen = get_db()
        db: Session = next(db_gen)
        try:
            recordings = (
                db.query(RecordingModel)
                .filter(RecordingModel.project_id == self.project_id)
                .all()
            )
            return recordings
        finally:
            next(db_gen, None)

    def process_recording(self, recording_id: int, output_sample_dir: str):
        """
        Initiates the audio processing (note detection and slicing) for a specific recording.

        This method uses the `detect_and_slice_recording` function from `audio_processor.py`.
        It ensures the output directory for samples exists and then calls the processing function.
        The processing function itself handles database updates for sample creation and
        recording status changes.

        Args:
            recording_id (int): The ID of the recording to process.
            output_sample_dir (str): The directory path where sliced samples should be saved.
        """
        # Import here to avoid circular dependencies at module load time
        from .audio_processor import detect_and_slice_recording

        if not os.path.exists(output_sample_dir):
            try:
                os.makedirs(output_sample_dir)
                print(f"Created output directory: {output_sample_dir}")
            except OSError as e:
                print(
                    f"Error creating output directory {output_sample_dir}: {e}. Processing aborted.")
                # Optionally, update recording status to 'failed' here or let
                # detect_and_slice_recording handle it
                return

        # detect_and_slice_recording uses its own session management.
        # We fetch the recording first to ensure it belongs to this project.
        # A new session is used for this check and for the processing call.
        db_processing_session = SessionLocal()
        try:
            recording = (
                db_processing_session.query(RecordingModel)
                .filter(
                    RecordingModel.id == recording_id,
                    RecordingModel.project_id == self.project_id,
                )
                .first()
            )

            if not recording:
                print(
                    f"Recording with id {recording_id} not found for project {
                        self.project_id}. Processing aborted."
                )
                return

            # Call the processing function, passing the session for it to use
            detect_and_slice_recording(
                db_processing_session, recording_id, output_sample_dir
            )
            # The status of the 'recording' object here might be stale if detect_and_slice_recording committed changes.
            # The caller (e.g., API route) should re-fetch the recording if it
            # needs the latest status immediately.
        except Exception as e:
            # General error handling for the processing call itself, though
            # detect_and_slice should also have its own.
            print(
                f"An unexpected error occurred during process_recording setup for recording {recording_id}: {e}"
            )
            # Optionally update recording status to 'failed' if not already handled by detect_and_slice_recording
            # For example:
            # if recording and recording.status not in ["processed", "failed"]:
            #     recording.status = "failed"
            #     db_processing_session.add(recording) # Ensure it's part of session if modified
            #     db_processing_session.commit()
        finally:
            db_processing_session.close()


if __name__ == "__main__":
    # Example Usage (requires a database with a project)
    # This section is for demonstration or direct script execution testing.
    # Ensure your database is initialized (`python -m src.database.utils`)
    # and has at least one project.

    # --- Example: Create a project first (if running this as a script) ---
    # from src.database.utils import init_db
    # init_db() # Run once to create tables

    # temp_db_session_gen = get_db()
    # temp_db_session = next(temp_db_session_gen)
    # try:
    #     # Check if a test project exists or create one
    #     example_project_model = temp_db_session.query(ProjectModel).filter(ProjectModel.name == "CLI Test Project").first()
    #     if not example_project_model:
    #         example_project_model = ProjectModel(name="CLI Test Project", description="A project for CLI testing")
    #         temp_db_session.add(example_project_model)
    #         temp_db_session.commit()
    #         temp_db_session.refresh(example_project_model)
    #         print(f"Created project with ID: {example_project_model.id}")
    #     cli_project_id = example_project_model.id
    # finally:
    #     next(temp_db_session_gen, None)
    #
    # print(f"Using project ID for CLI test: {cli_project_id}")
    # project_manager = Project(project_id=cli_project_id)

    # --- Create a dummy WAV file for testing add_recording ---
    # import soundfile as sf # You might need to pip install soundfile
    # dummy_file_path = "dummy_cli_audio.wav"
    # if not os.path.exists(dummy_file_path):
    #     sf.write(dummy_file_path, [0.0] * 44100, 44100, subtype='PCM_16') # 1 second of silence
    #     print(f"Created dummy audio file: {dummy_file_path}")

    # try:
    #     print(f"\nListing recordings before adding: {len(project_manager.list_recordings())} recordings.")
    #     new_rec = project_manager.add_recording(file_path=dummy_file_path, name="CLI Test Recording 1")
    #     print(f"Added recording: ID {new_rec.id}, Name: {new_rec.name}, Duration: {new_rec.duration_seconds}s, Status: {new_rec.status}")

    #     retrieved_rec = project_manager.get_recording(new_rec.id)
    #     if retrieved_rec:
    #         print(f"Retrieved recording: {retrieved_rec.name}")
    #     else:
    #         print(f"Could not retrieve recording ID {new_rec.id}")

    #     print(f"Listing recordings after adding: {len(project_manager.list_recordings())} recordings.")

    #     # --- Test processing (requires audio_processor.py and its dependencies) ---
    #     if new_rec:
    #         output_dir_cli = f"data/projects/{cli_project_id}/samples_cli_test_rec_{new_rec.id}"
    #         # Ensure base data directory exists if not managed by app startup
    #         if not os.path.exists(f"data/projects/{cli_project_id}"):
    #             os.makedirs(f"data/projects/{cli_project_id}", exist_ok=True)

    #         print(f"\nAttempting to process recording ID: {new_rec.id} into {output_dir_cli}")
    #         project_manager.process_recording(new_rec.id, output_dir_cli)

    #         # Verify status and samples (requires a new session to see committed changes from process_recording)
    #         verify_db_gen = get_db()
    #         verify_db = next(verify_db_gen)
    #         try:
    #             updated_rec_status = verify_db.query(RecordingModel.status).filter(RecordingModel.id == new_rec.id).scalar()
    #             print(f"Status of recording {new_rec.id} after processing attempt: {updated_rec_status}")
    #             samples_from_db = verify_db.query(SampleModel).filter(SampleModel.recording_id == new_rec.id).all()
    #             print(f"Found {len(samples_from_db)} samples in DB for recording {new_rec.id}.")
    #             for s_db in samples_from_db:
    #                 print(f"  - Sample: {s_db.name}, Path: {s_db.file_path}")
    #         finally:
    #             next(verify_db_gen, None)
    #         print(f"Check filesystem for samples in: {output_dir_cli}")

    # except ValueError as e:
    #     print(f"ValueError: {e}")
    # except FileNotFoundError as e:
    #     print(f"FileNotFoundError: {e}")
    # except Exception as e:
    #     print(f"An unexpected error occurred during CLI example: {e}")
    #     import traceback
    #     traceback.print_exc()
    # finally:
    #     if os.path.exists(dummy_file_path):
    #         # os.remove(dummy_file_path) # Keep it for multiple runs if desired
    #         # print(f"Cleaned up dummy audio file: {dummy_file_path}")
    #         pass
    # Example Usage (requires a database with a project)
    # First, ensure your database is initialized and has a project
    # from src.database.utils import init_db
    # init_db() # Make sure this is run once to create tables

    # db_session = SessionLocal()
    # example_project = ProjectModel(name="Test Project", description="A project for testing")
    # db_session.add(example_project)
    # db_session.commit()
    # project_id = example_project.id
    # db_session.close()

    # print(f"Using project ID: {project_id}")

    # project_manager = Project(project_id=project_id)

    # Create a dummy wav file for testing
    # import soundfile as sf
    # dummy_file_path = "dummy_audio.wav"
    # sf.write(dummy_file_path, [0.0] * 44100, 44100) # 1 second of silence

    # try:
    #     print(f"Listing recordings before adding: {project_manager.list_recordings()}")
    #     new_rec = project_manager.add_recording(file_path=dummy_file_path, name="Test Recording 1")
    #     print(f"Added recording: {new_rec.id}, Name: {new_rec.name}, Duration: {new_rec.duration_seconds}s, Status: {new_rec.status}")
    #     retrieved_rec = project_manager.get_recording(new_rec.id)
    #     print(f"Retrieved recording: {retrieved_rec.name}")
    #     print(f"Listing recordings after adding: {project_manager.list_recordings()}")

    # Test processing (will be fully implemented later)
    # output_dir = f"data/projects/{project_id}/samples"
    # project_manager.process_recording(new_rec.id, output_dir)
    # print(f"Called process_recording for recording {new_rec.id}. Check status in DB and files in {output_dir}")

    # except ValueError as e:
    #     print(f"Error: {e}")
    # except FileNotFoundError as e:
    #     print(f"Error: {e}")
    # finally:
    #     if os.path.exists(dummy_file_path):
    #         os.remove(dummy_file_path)
    pass
