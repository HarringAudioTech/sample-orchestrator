import unittest
from unittest.mock import patch, MagicMock, call, ANY
import os
import datetime

# Modules to be tested
from src.core.project import Project

# Assuming database models can be mocked easily.
# We'll use MagicMock for Session and the model classes.
# from src.database.models import Project as ProjectModel, Recording as RecordingModel
# from src.database.utils import get_db # For mocking the session generation
# For now, use MagicMock without spec_set for more flexibility.
ProjectModel = MagicMock(name="ProjectModel_Mock")
# RecordingModel will be configured with a side_effect in relevant tests or setUp
RecordingModel = MagicMock(name="RecordingModel_ClassMock")
MidiDeviceModel = MagicMock(name="MidiDeviceModel_Mock")
MidiCaptureSessionModel = MagicMock(name="MidiCaptureSessionModel_Mock")
MidiFileModel = MagicMock(name="MidiFileModel_Mock")
# Mock get_db at the module level for cases where it might be imported directly
# However, specific patching in tests is generally preferred.

from sqlalchemy.exc import SQLAlchemyError
import librosa # For librosa exceptions
import numpy as np # For librosa return types

# from src.core.midi_capture import MidiRecorder # For type hinting if Project returns MidiRecorder
# MidiRecorder can also be a MagicMock if only type hinting is needed and not actual instance behavior
MidiRecorder = MagicMock(name="MidiRecorder_Mock")


class TestProject(unittest.TestCase):

    def setUp(self):
        self.project_id = 1
        self.project_name = "Test Project Alpha"
        # Create a new MagicMock for ProjectModel instance for each test if needed,
        # or configure this one appropriately.
        # For Project.__init__ tests, this mock_project_model_instance is what's "loaded" from DB.
        self.mock_project_model_instance = ProjectModel(id=self.project_id, name=self.project_name)
        # Ensure it has a 'recordings' attribute if Project class accesses it (e.g. project.recordings)
        self.mock_project_model_instance.recordings = []


        # Mock for the database session, created fresh for each test.
        self.mock_db_session = MagicMock(name="MockDBSession")

    def tearDown(self):
        patch.stopall() # Stop any patches that might have been started globally or not using decorators/context managers

    @patch('src.core.project.get_db')
    def test_project_init_successful_no_session_provided(self, mock_get_db_global):
        mock_get_db_global.return_value = iter([self.mock_db_session])

        self.mock_db_session.query(ProjectModel).filter_by(id=self.project_id).first.return_value = self.mock_project_model_instance

        project = Project(project_id=self.project_id)

        self.assertEqual(project.project_id, self.project_id)
        # Reverted: Assume SUT calls .first() correctly and assigns the instance.
        self.assertEqual(project.project_model, self.mock_project_model_instance)
        mock_get_db_global.assert_called_once()
        self.mock_db_session.query(ProjectModel).filter_by(id=self.project_id).first.assert_called_once()
        # Check session closure (mock_db_session.close would be called if Project.__exit__ is triggered by context manager use)
        # If get_db() is used as a context manager in SUT: e.g. with get_db() as db:
        # then db.close() will be called. If it's just db = next(get_db()), then Project must call db.close().
        # Assuming Project's __init__ calls db.close() in a finally block.
        # self.mock_db_session.close.assert_called_once() # Add if applicable based on SUT

    def test_project_init_successful_session_provided(self):
        self.mock_db_session.query(ProjectModel).filter_by(id=self.project_id).first.return_value = self.mock_project_model_instance

        # Using a local patch for get_db to ensure it's not called
        with patch('src.core.project.get_db') as mock_get_db_local:
            project = Project(project_id=self.project_id, db_session=self.mock_db_session)
            mock_get_db_local.assert_not_called() # Verify get_db is not called when session is provided

        self.assertEqual(project.project_id, self.project_id)
        # Reverted: Assume SUT calls .first() correctly.
        self.assertEqual(project.project_model, self.mock_project_model_instance)
        self.mock_db_session.query(ProjectModel).filter_by(id=self.project_id).first.assert_called_once()


    @patch('src.core.project.get_db')
    def test_project_init_not_found(self, mock_get_db_notfound):
        mock_get_db_notfound.return_value = iter([self.mock_db_session])
        self.mock_db_session.query(ProjectModel).filter_by(id=self.project_id).first.return_value = None

        with self.assertRaisesRegex(ValueError, f"Project with id {self.project_id} not found"):
            Project(project_id=self.project_id)

        mock_get_db_notfound.assert_called_once()
        # self.mock_db_session.close.assert_called_once() # If applicable

    @patch('src.core.project.get_db')
    def test_project_init_sqlalchemy_error(self, mock_get_db_sqlerror):
        mock_get_db_sqlerror.return_value = iter([self.mock_db_session])
        self.mock_db_session.query(ProjectModel).filter_by(id=self.project_id).first.side_effect = SQLAlchemyError("DB Init Error")

        with self.assertRaisesRegex(SQLAlchemyError, "DB Init Error"):
            Project(project_id=self.project_id)
        mock_get_db_sqlerror.assert_called_once()
        # self.mock_db_session.rollback.assert_called_once() # If SUT does rollback on general SQLAlchemyError
        # self.mock_db_session.close.assert_called_once() # If applicable

    @patch('src.core.project.os.path.exists', return_value=True)
    @patch('src.core.project.librosa.load')
    @patch('src.core.project.librosa.get_duration')
    # Patched RecordingModel will be handled by the side_effect setup
    @patch('src.core.project.get_db')
    def test_add_recording_successful_no_session_provided(self, mock_get_db_rec, mock_get_duration, mock_librosa_load, mock_os_exists):
        # Setup RecordingModel mock to return instances with attributes from kwargs
        def recording_model_factory(**kwargs):
            instance = MagicMock(name="RecordingModelInstance_Mock")
            # Set a default 'id' if not provided, as SUT might expect it after refresh
            kwargs.setdefault('id', None)
            instance.configure_mock(**kwargs)
            return instance

        # Temporarily patch RecordingModel for this test if not globally
        with patch('src.core.project.RecordingModel', side_effect=recording_model_factory) as PatchedRecordingModel:
            mock_get_db_rec.return_value = iter([self.mock_db_session])
            # Initial project load
            self.mock_db_session.query(ProjectModel).filter_by(id=self.project_id).first.return_value = self.mock_project_model_instance
            project = Project(project_id=self.project_id)

            # Reset mocks for the add_recording part of the test
            self.mock_db_session.reset_mock()
            mock_get_db_rec.reset_mock()
            mock_get_db_rec.return_value = iter([self.mock_db_session])

            dummy_audio_data = np.array([0.1, 0.2, 0.1]) # Mono
            sample_rate = 44100
            duration = 1.5
            mock_librosa_load.return_value = (dummy_audio_data, sample_rate)
            mock_get_duration.return_value = duration

            file_path = "/test/audio.wav"
            recording_name = "Test WAV Recording"

            new_recording_model_instance = project.add_recording(file_path=file_path, name=recording_name)

            mock_os_exists.assert_called_once_with(file_path)
            mock_librosa_load.assert_called_once_with(file_path, sr=None, mono=False)
            mock_get_duration.assert_called_once_with(y=dummy_audio_data, sr=sample_rate)

            self.mock_db_session.add.assert_called_once()
            added_object = self.mock_db_session.add.call_args[0][0]

            self.assertIs(added_object, new_recording_model_instance)
            self.assertEqual(added_object.project_id, self.project_id)
            self.assertEqual(added_object.name, recording_name)
            self.assertEqual(added_object.file_path, file_path)
            self.assertEqual(added_object.duration_seconds, duration)
            self.assertEqual(added_object.samplerate, sample_rate)
            self.assertEqual(added_object.channels, 1)
            self.assertEqual(added_object.status, "pending")

            self.mock_db_session.commit.assert_called_once()
            self.mock_db_session.refresh.assert_called_once_with(added_object)

            self.assertEqual(mock_get_db_rec.call_count, 1) # After reset_mock, add_recording calls it once.

    @patch('src.core.project.os.path.exists', return_value=True)
    @patch('src.core.project.librosa.load')
    @patch('src.core.project.librosa.get_duration')
    # Patched RecordingModel will be handled by the side_effect setup
    def test_add_recording_successful_session_provided(self, mock_get_duration, mock_librosa_load, mock_os_exists):
        def recording_model_factory(**kwargs):
            instance = MagicMock(name="RecordingModelInstance_Mock")
            kwargs.setdefault('id', None)
            instance.configure_mock(**kwargs)
            return instance

        with patch('src.core.project.RecordingModel', side_effect=recording_model_factory) as PatchedRecordingModel:
            self.mock_db_session.query(ProjectModel).filter_by(id=self.project_id).first.return_value = self.mock_project_model_instance
            project = Project(project_id=self.project_id, db_session=self.mock_db_session)
            self.mock_db_session.reset_mock()

            stereo_audio_data = np.array([[0.1, 0.2], [0.3, 0.4]])
            sample_rate = 22050
            duration = 0.5
            mock_librosa_load.return_value = (stereo_audio_data, sample_rate)
            mock_get_duration.return_value = duration

            file_path = "/test/stereo_audio.mp3"
            recording_name = "Stereo MP3"

            new_recording_model_instance = project.add_recording(file_path=file_path, name=recording_name)

            self.mock_db_session.add.assert_called_once()
            added_object = self.mock_db_session.add.call_args[0][0]
            self.assertIs(added_object, new_recording_model_instance)
            self.assertEqual(added_object.channels, 2)
            self.mock_db_session.commit.assert_called_once()


    @patch('src.core.project.os.path.exists', return_value=False)
    @patch('src.core.project.get_db')
    def test_add_recording_file_not_found(self, mock_get_db_fnf, mock_os_exists_fnf):
        mock_get_db_fnf.return_value = iter([self.mock_db_session])
        self.mock_db_session.query(ProjectModel).filter_by(id=self.project_id).first.return_value = self.mock_project_model_instance
        project = Project(project_id=self.project_id)
        self.mock_db_session.reset_mock()
        mock_get_db_fnf.reset_mock()
        mock_get_db_fnf.return_value = iter([self.mock_db_session])


        file_path = "/test/nonexistent.wav"
        with self.assertRaisesRegex(FileNotFoundError, f"Recording file not found: {file_path}"):
            project.add_recording(file_path=file_path, name="Non Existent")

        self.mock_db_session.add.assert_not_called()
        self.mock_db_session.commit.assert_not_called()

    @patch('src.core.project.os.path.exists', return_value=True)
    @patch('src.core.project.librosa.load', side_effect=librosa.LibrosaError("Librosa load failed"))
    # Patched RecordingModel will be handled by the side_effect setup
    @patch('src.core.project.get_db')
    def test_add_recording_librosa_error(self, mock_get_db_le, mock_librosa_load_err, mock_os_exists_le):
        def recording_model_factory(**kwargs):
            instance = MagicMock(name="RecordingModelInstance_Mock")
            kwargs.setdefault('id', None)
            instance.configure_mock(**kwargs)
            return instance

        with patch('src.core.project.RecordingModel', side_effect=recording_model_factory) as PatchedRecordingModel:
            mock_get_db_le.return_value = iter([self.mock_db_session])
            self.mock_db_session.query(ProjectModel).filter_by(id=self.project_id).first.return_value = self.mock_project_model_instance
            project = Project(project_id=self.project_id)
            self.mock_db_session.reset_mock()
            mock_get_db_le.reset_mock()
            mock_get_db_le.return_value = iter([self.mock_db_session])

            new_recording = project.add_recording(file_path="/test/audio.wav", name="Librosa Error Case")

            self.mock_db_session.add.assert_called_once()
            added_object = self.mock_db_session.add.call_args[0][0]
            self.assertIs(new_recording, added_object)
            self.assertIsNone(added_object.duration_seconds)
            self.assertIsNone(added_object.samplerate)
            self.assertIsNone(added_object.channels)
            self.mock_db_session.commit.assert_called_once()


    @patch('src.core.project.os.path.exists', return_value=True)
    @patch('src.core.project.librosa.load', return_value=(np.array([0.1]), 44100))
    @patch('src.core.project.librosa.get_duration', return_value=1.0)
    # Patched RecordingModel will be handled by the side_effect setup
    @patch('src.core.project.get_db')
    def test_add_recording_sqlalchemy_error(self, mock_get_db_sqlae, mock_get_duration_sqlae, mock_librosa_load_sqlae, mock_os_exists_sqlae):
        def recording_model_factory(**kwargs):
            instance = MagicMock(name="RecordingModelInstance_Mock")
            kwargs.setdefault('id', None)
            instance.configure_mock(**kwargs)
            return instance

        with patch('src.core.project.RecordingModel', side_effect=recording_model_factory) as PatchedRecordingModel:
            mock_get_db_sqlae.return_value = iter([self.mock_db_session])
            self.mock_db_session.query(ProjectModel).filter_by(id=self.project_id).first.return_value = self.mock_project_model_instance
            project = Project(project_id=self.project_id)
            self.mock_db_session.reset_mock()
            mock_get_db_sqlae.reset_mock()
            mock_get_db_sqlae.return_value = iter([self.mock_db_session])

            self.mock_db_session.commit.side_effect = SQLAlchemyError("DB Commit Error for Recording")

            with self.assertRaisesRegex(SQLAlchemyError, "DB Commit Error for Recording"):
                project.add_recording(file_path="/test/audio.wav", name="DB Error Case")

            self.mock_db_session.add.assert_called_once()
            self.mock_db_session.rollback.assert_called_once()


    @patch('src.core.project.get_db')
    def test_get_recording_found_no_session_provided(self, mock_get_db_gr):
        # Project creates its own session
        mock_get_db_gr.return_value = iter([self.mock_db_session])
        self.mock_db_session.query(ProjectModel).filter(ProjectModel.id == self.project_id).first.return_value = self.mock_project_model_instance
        project = Project(project_id=self.project_id)
        self.mock_db_session.reset_mock()
        mock_get_db_gr.reset_mock() # Reset mock_get_db as well for this specific call
        mock_get_db_gr.return_value = iter([self.mock_db_session]) # For get_recording

        mock_recording = RecordingModel(id=10, name="Found Rec", project_id=self.project_id)
        # Specific mock for the RecordingModel query chain
        self.mock_db_session.query(RecordingModel).filter_by(id=10, project_id=self.project_id).first.return_value = mock_recording

        recording = project.get_recording(recording_id=10)

        self.assertEqual(recording, mock_recording)
        self.mock_db_session.query(RecordingModel).filter_by(id=10, project_id=self.project_id).first.assert_called_once()
        mock_get_db_gr.assert_called_once() # Called for get_recording method


    def test_get_recording_found_session_provided(self):
        # Project uses provided session
        self.mock_db_session.query(ProjectModel).filter(ProjectModel.id == self.project_id).first.return_value = self.mock_project_model_instance
        project = Project(project_id=self.project_id, db_session=self.mock_db_session)
        self.mock_db_session.reset_mock() # After init

        mock_recording = RecordingModel(id=11, name="Found Rec Session", project_id=self.project_id)
        self.mock_db_session.query(RecordingModel).filter_by(id=11, project_id=self.project_id).first.return_value = mock_recording

        recording = project.get_recording(recording_id=11)
        self.assertEqual(recording, mock_recording)
        self.mock_db_session.query(RecordingModel).filter_by(id=11, project_id=self.project_id).first.assert_called_once()


    @patch('src.core.project.get_db')
    def test_get_recording_not_found(self, mock_get_db_grnf):
        mock_get_db_grnf.return_value = iter([self.mock_db_session])
        self.mock_db_session.query(ProjectModel).filter(ProjectModel.id == self.project_id).first.return_value = self.mock_project_model_instance
        project = Project(project_id=self.project_id)
        self.mock_db_session.reset_mock()
        mock_get_db_grnf.reset_mock()
        mock_get_db_grnf.return_value = iter([self.mock_db_session])

        self.mock_db_session.query(RecordingModel).filter_by(id=99, project_id=self.project_id).first.return_value = None # Not found
        recording = project.get_recording(recording_id=99)
        self.assertIsNone(recording)
        mock_get_db_grnf.assert_called_once()

    @patch('src.core.project.get_db')
    def test_get_recording_sqlalchemy_error(self, mock_get_db_gr_sqlerr):
        mock_get_db_gr_sqlerr.return_value = iter([self.mock_db_session])
        self.mock_db_session.query(ProjectModel).filter(ProjectModel.id == self.project_id).first.return_value = self.mock_project_model_instance
        project = Project(project_id=self.project_id)
        self.mock_db_session.reset_mock()
        mock_get_db_gr_sqlerr.reset_mock()
        mock_get_db_gr_sqlerr.return_value = iter([self.mock_db_session])

        self.mock_db_session.query(RecordingModel).filter_by(id=1, project_id=self.project_id).first.side_effect = SQLAlchemyError("GetRec DB Error")
        with self.assertRaisesRegex(SQLAlchemyError, "GetRec DB Error"):
            project.get_recording(recording_id=1)
        mock_get_db_gr_sqlerr.assert_called_once()

    @patch('src.core.project.get_db')
    def test_list_recordings_successful(self, mock_get_db_lr):
        mock_get_db_lr.return_value = iter([self.mock_db_session])
        self.mock_db_session.query(ProjectModel).filter(ProjectModel.id == self.project_id).first.return_value = self.mock_project_model_instance
        project = Project(project_id=self.project_id)
        self.mock_db_session.reset_mock()
        mock_get_db_lr.reset_mock()
        mock_get_db_lr.return_value = iter([self.mock_db_session])

        mock_recordings_list = [
            RecordingModel(id=1, name="Rec A", project_id=self.project_id),
            RecordingModel(id=2, name="Rec B", project_id=self.project_id)
        ]
        # Mock the chain for list_recordings
        self.mock_db_session.query(RecordingModel).filter_by(project_id=self.project_id).order_by().all.return_value = mock_recordings_list

        recordings = project.list_recordings()
        self.assertEqual(recordings, mock_recordings_list)
        self.mock_db_session.query(RecordingModel).filter_by(project_id=self.project_id).order_by().all.assert_called_once()
        mock_get_db_lr.assert_called_once()

    @patch('src.core.project.get_db')
    def test_list_recordings_sqlalchemy_error(self, mock_get_db_lr_err):
        mock_get_db_lr_err.return_value = iter([self.mock_db_session])
        self.mock_db_session.query(ProjectModel).filter(ProjectModel.id == self.project_id).first.return_value = self.mock_project_model_instance
        project = Project(project_id=self.project_id)
        self.mock_db_session.reset_mock()
        mock_get_db_lr_err.reset_mock()
        mock_get_db_lr_err.return_value = iter([self.mock_db_session])

        self.mock_db_session.query(RecordingModel).filter_by(project_id=self.project_id).order_by().all.side_effect = SQLAlchemyError("ListRec DB Error")
        with self.assertRaisesRegex(SQLAlchemyError, "ListRec DB Error"):
            project.list_recordings()
        mock_get_db_lr_err.assert_called_once()

    # --- MIDI Related Method Tests ---

    @patch('src.core.project.list_available_midi_devices')
    @patch('src.core.project.get_db')
    def test_list_midi_devices_successful(self, mock_get_db_lmd, mock_list_devices_func):
        mock_get_db_lmd.return_value = iter([self.mock_db_session])
        self.mock_db_session.query(ProjectModel).filter(ProjectModel.id == self.project_id).first.return_value = self.mock_project_model_instance
        project = Project(project_id=self.project_id)
        # Reset get_db mock for the list_midi_devices call specifically
        mock_get_db_lmd.reset_mock()
        mock_get_db_lmd.return_value = iter([self.mock_db_session])


        mock_device_list = [MidiDeviceModel(id=1, name="Device 1")]
        mock_list_devices_func.return_value = mock_device_list

        devices = project.list_midi_devices()

        self.assertEqual(devices, mock_device_list)
        mock_list_devices_func.assert_called_once_with(self.mock_db_session)
        mock_get_db_lmd.assert_called_once()

    @patch('src.core.project.MidiRecorder', new=MidiRecorder) # Patch with our global mock
    @patch('src.core.project.get_db')
    def test_create_midi_capture_session_successful(self, mock_get_db_cmcs): # Removed MockMidiRecorder_class_patch
        # This test uses the global MidiRecorder mock defined at the top of the file,
        # which was patched into src.core.project.MidiRecorder
        mock_get_db_cmcs.return_value = iter([self.mock_db_session])
        self.mock_db_session.query(ProjectModel).filter(ProjectModel.id == self.project_id).first.return_value = self.mock_project_model_instance
        project = Project(project_id=self.project_id)
        mock_get_db_cmcs.reset_mock()
        mock_get_db_cmcs.return_value = iter([self.mock_db_session])

        # Configure the return_value of the global MidiRecorder mock (which is now the class in SUT's context)
        mock_recorder_instance = MagicMock(name="MockMidiRecorderInstance")
        MidiRecorder.return_value = mock_recorder_instance # When MidiRecorder(...) is called, return this

        session_name = "My MIDI Session"
        selected_devices = ["Device A"]

        recorder = project.create_midi_capture_session(session_name, selected_devices)

        self.assertEqual(recorder, mock_recorder_instance)
        MidiRecorder.assert_called_once_with( # Check args passed to MidiRecorder constructor
            project_id=self.project_id,
            selected_device_names=selected_devices,
            session_name=session_name,
            db=self.mock_db_session
        )
        mock_get_db_cmcs.assert_called_once()

    @patch('src.core.project.get_db')
    def test_list_midi_capture_sessions_successful(self, mock_get_db_lmcs):
        mock_get_db_lmcs.return_value = iter([self.mock_db_session])
        self.mock_db_session.query(ProjectModel).filter(ProjectModel.id == self.project_id).first.return_value = self.mock_project_model_instance
        project = Project(project_id=self.project_id)
        self.mock_db_session.reset_mock()
        mock_get_db_lmcs.reset_mock()
        mock_get_db_lmcs.return_value = iter([self.mock_db_session])


        mock_sessions_list = [MidiCaptureSessionModel(id=1, name="Session 1", project_id=self.project_id)]
        # Mock the chain for list_midi_capture_sessions
        query_mock = self.mock_db_session.query(MidiCaptureSessionModel)
        filter_mock = query_mock.filter_by(project_id=self.project_id) # Test specific filter
        orderby_mock = filter_mock.order_by()
        orderby_mock.all.return_value = mock_sessions_list

        sessions = project.list_midi_capture_sessions()
        self.assertEqual(sessions, mock_sessions_list)
        # Verify filter for project_id was used
        query_mock.filter_by.assert_called_once_with(project_id=self.project_id)
        mock_get_db_lmcs.assert_called_once()


    @patch('src.core.project.get_db')
    def test_get_midi_capture_session_found(self, mock_get_db_gmcs):
        mock_get_db_gmcs.return_value = iter([self.mock_db_session])
        self.mock_db_session.query(ProjectModel).filter(ProjectModel.id == self.project_id).first.return_value = self.mock_project_model_instance
        project = Project(project_id=self.project_id)
        self.mock_db_session.reset_mock()
        mock_get_db_gmcs.reset_mock()
        mock_get_db_gmcs.return_value = iter([self.mock_db_session])

        session_id = 5
        mock_session = MidiCaptureSessionModel(id=session_id, name="Target Session", project_id=self.project_id)
        self.mock_db_session.query(MidiCaptureSessionModel).filter_by(id=session_id, project_id=self.project_id).first.return_value = mock_session

        session = project.get_midi_capture_session(session_id=session_id)
        self.assertEqual(session, mock_session)
        self.mock_db_session.query(MidiCaptureSessionModel).filter_by(id=session_id, project_id=self.project_id).first.assert_called_once()
        mock_get_db_gmcs.assert_called_once()

    @patch('src.core.project.get_db')
    def test_get_midi_files_for_session_successful(self, mock_get_db_gmfs):
        mock_get_db_gmfs.return_value = iter([self.mock_db_session])
        self.mock_db_session.query(ProjectModel).filter(ProjectModel.id == self.project_id).first.return_value = self.mock_project_model_instance
        project = Project(project_id=self.project_id)
        self.mock_db_session.reset_mock()
        mock_get_db_gmfs.reset_mock()
        mock_get_db_gmfs.return_value = iter([self.mock_db_session])

        session_id = 7
        mock_capture_session = MidiCaptureSessionModel(id=session_id, name="Session With Files", project_id=self.project_id)

        # Mock for the session lookup
        q_session_mock = self.mock_db_session.query(MidiCaptureSessionModel)
        f_session_mock = q_session_mock.filter_by(id=session_id, project_id=self.project_id)
        f_session_mock.first.return_value = mock_capture_session

        mock_midi_files_list = [MidiFileModel(id=1, midi_capture_session_id=session_id, midi_device_id=1, channel_number=0, midi_data=b'data')]

        # Mock for the MIDI files lookup
        q_files_mock = self.mock_db_session.query(MidiFileModel)
        f_files_mock = q_files_mock.filter_by(midi_capture_session_id=session_id)
        o_files_mock = f_files_mock.order_by()
        o_files_mock.all.return_value = mock_midi_files_list

        midi_files = project.get_midi_files_for_session(session_id=session_id)

        self.assertEqual(midi_files, mock_midi_files_list)

        q_session_mock.filter_by.assert_called_once_with(id=session_id, project_id=self.project_id)
        q_files_mock.filter_by.assert_called_once_with(midi_capture_session_id=session_id)
        mock_get_db_gmfs.assert_called_once()


    @patch('src.core.project.get_db')
    def test_get_midi_files_for_session_not_found_or_not_project_session(self, mock_get_db_gmfs_nf):
        mock_get_db_gmfs_nf.return_value = iter([self.mock_db_session])
        self.mock_db_session.query(ProjectModel).filter(ProjectModel.id == self.project_id).first.return_value = self.mock_project_model_instance
        project = Project(project_id=self.project_id)
        self.mock_db_session.reset_mock()
        mock_get_db_gmfs_nf.reset_mock()
        mock_get_db_gmfs_nf.return_value = iter([self.mock_db_session])

        session_id = 8
        self.mock_db_session.query(MidiCaptureSessionModel).filter_by(id=session_id, project_id=self.project_id).first.return_value = None

        midi_files = project.get_midi_files_for_session(session_id=session_id)
        self.assertEqual(midi_files, [])
        # Ensure query for MidiFileModel was not made if session not found
        self.mock_db_session.query(MidiFileModel).filter_by().order_by().all.assert_not_called()
        mock_get_db_gmfs_nf.assert_called_once()

if __name__ == '__main__':
    unittest.main(verbosity=2)
