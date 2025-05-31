import pytest
import os
import datetime
import io  # Added io
from unittest.mock import patch, MagicMock, call, ANY

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import (
    Base,
    Project as ProjectModel,
    MidiDevice as MidiDeviceModel,
    MidiCaptureSession as MidiCaptureSessionModel,
    MidiFile as MidiFileModel,
)
from src.database.utils import init_db as init_db_main  # Renamed to avoid conflict
from src.core.midi_capture import (
    list_available_midi_devices,
    get_midi_device_by_name,
    MidiRecorder,
    sanitize_filename,
)
from src.core.project import Project
import mido  # To help with creating mock mido messages


# --- Test Database Setup ---
TEST_DATABASE_URL = "sqlite:///:memory:"
_test_engine = None
_TestSessionLocal = None


def get_test_engine():
    global _test_engine
    if _test_engine is None:
        _test_engine = create_engine(
            TEST_DATABASE_URL, connect_args={"check_same_thread": False}
        )
    return _test_engine


def get_test_session_local():
    global _TestSessionLocal
    if _TestSessionLocal is None:
        _TestSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=get_test_engine()
        )
    return _TestSessionLocal


@pytest.fixture(scope="function")
def db_session():
    """
    Pytest fixture to set up a new database session for each test function.
    Initializes the database schema and rolls back any changes after the test.
    """
    engine = get_test_engine()
    Base.metadata.create_all(bind=engine)  # Create tables
    SessionLocal_test = get_test_session_local()
    session = SessionLocal_test()
    try:
        yield session
    finally:
        session.rollback()  # Ensure a clean state for the next test
        session.close()
        # Drop tables to ensure full isolation
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_project_model(db_session: Session):
    """Creates a ProjectModel instance in the DB for testing."""
    project = ProjectModel(
        name="Test Project", description="A project for testing MIDI capture."
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture(scope="function")
def test_project_instance(test_project_model: ProjectModel):
    """Creates a Project core class instance using a ProjectModel."""
    # The Project class __init__ uses get_db, which points to main DB.
    # Project.__init__ now accepts db_session.
    # We get a session from the same test session factory used by the db_session fixture.
    db_session_for_project = get_test_session_local()()
    try:
        project_core_instance = Project(
            project_id=test_project_model.id, db_session=db_session_for_project
        )
        # The project_core_instance will use db_session_for_project.
        # Operations within test methods might use the db_session fixture directly.
        # Ensure they operate on the same database if direct assertions are made.
        return project_core_instance
    finally:
        # Ensure the session created for the project instance is closed if the fixture scope
        # intended it to be short-lived (which it does, as it's created here).
        db_session_for_project.close()


# --- Mocks for mido ---


@pytest.fixture
def mock_mido_get_input_names(monkeypatch):
    mock_func = MagicMock(return_value=[])
    monkeypatch.setattr("mido.get_input_names", mock_func)
    return mock_func


@pytest.fixture
def mock_mido_open_input(monkeypatch):
    mock_port = MagicMock(spec=mido.ports.BaseInput)  # Make sure it behaves like a mido port
    mock_port.name = "Mock MIDI Port"
    mock_port.close = MagicMock()
    mock_port.callback = None

    mock_func = MagicMock(return_value=mock_port)
    monkeypatch.setattr("mido.open_input", mock_func)
    return mock_func, mock_port  # Return both the patch itself and the mocked port


@pytest.fixture
def mock_mido_file_save(monkeypatch):
    # This fixture is currently a no-op as mido.MidiFile.save() is not directly mocked
    # for its filepath argument anymore. Tests now verify the byte output from
    # mido_file.save(file=io.BytesIO_buffer).
    # If specific mocking of the save(file=...) behavior is needed in the future,
    # this fixture could be reactivated or adapted.
    pass


# --- Tests for src/core/midi_capture.py ---


def test_sanitize_filename():
    assert sanitize_filename("Test Session 1") == "Test_Session_1"
    assert sanitize_filename('Session /\\:*?"<>|') == "Session_"
    assert sanitize_filename("valid-name_1.2.mid") == "valid-name_1.2.mid"


# == Tests for list_available_midi_devices ==
def test_list_available_midi_devices_no_devices(
    db_session: Session, mock_mido_get_input_names
):
    mock_mido_get_input_names.return_value = []
    devices = list_available_midi_devices(db_session)
    assert len(devices) == 0
    assert db_session.query(MidiDeviceModel).count() == 0


def test_list_available_midi_devices_new_devices(
    db_session: Session, mock_mido_get_input_names
):
    mock_mido_get_input_names.return_value = ["Device A", "Device B"]
    devices = list_available_midi_devices(db_session)
    assert len(devices) == 2
    db_devices = db_session.query(MidiDeviceModel).all()
    assert len(db_devices) == 2
    assert {dev.name for dev in db_devices} == {"Device A", "Device B"}
    for dev in db_devices:
        assert dev.system_identifier == dev.name  # As per current implementation


def test_list_available_midi_devices_existing_devices(
    db_session: Session, mock_mido_get_input_names
):
    # Pre-populate
    existing_device = MidiDeviceModel(name="Device A", system_identifier="Device A SysID")
    db_session.add(existing_device)
    db_session.commit()
    db_session.refresh(existing_device)
    original_updated_at = existing_device.updated_at

    mock_mido_get_input_names.return_value = ["Device A"]

    # To check updated_at, ensure some time passes or mock datetime
    with patch("src.core.midi_capture.datetime") as mock_datetime:
        mock_datetime.datetime.utcnow.return_value = original_updated_at + datetime.timedelta(
            seconds=1
        )
        devices = list_available_midi_devices(db_session)

    assert len(devices) == 1
    db_device = (
        db_session.query(MidiDeviceModel).filter(MidiDeviceModel.name == "Device A").one()
    )
    assert db_device.id == existing_device.id
    assert db_device.updated_at > original_updated_at
    assert db_session.query(MidiDeviceModel).count() == 1


def test_list_available_midi_devices_mixed_new_existing(
    db_session: Session, mock_mido_get_input_names
):
    existing_device = MidiDeviceModel(name="Device A", system_identifier="dev_a_sys")
    db_session.add(existing_device)
    db_session.commit()
    db_session.refresh(existing_device)
    original_updated_at_A = existing_device.updated_at

    mock_mido_get_input_names.return_value = ["Device A", "New Device B"]

    with patch("src.core.midi_capture.datetime") as mock_datetime:
        mock_datetime.datetime.utcnow.return_value = (
            original_updated_at_A + datetime.timedelta(seconds=1)
        )
        devices = list_available_midi_devices(db_session)

    assert len(devices) == 2
    assert db_session.query(MidiDeviceModel).count() == 2

    dev_A = db_session.query(MidiDeviceModel).filter(MidiDeviceModel.name == "Device A").one()
    dev_B = (
        db_session.query(MidiDeviceModel)
        .filter(MidiDeviceModel.name == "New Device B")
        .one_or_none()
    )

    assert dev_A is not None
    assert dev_A.updated_at > original_updated_at_A
    assert dev_B is not None
    assert dev_B.system_identifier == "New Device B"


# == Tests for get_midi_device_by_name ==
def test_get_midi_device_by_name_found(db_session: Session):
    device = MidiDeviceModel(name="Test Device", system_identifier="test_dev_sys")
    db_session.add(device)
    db_session.commit()

    found_device = get_midi_device_by_name(db_session, "Test Device")
    assert found_device is not None
    assert found_device.name == "Test Device"


def test_get_midi_device_by_name_not_found(db_session: Session):
    found_device = get_midi_device_by_name(db_session, "NonExistent Device")
    assert found_device is None


# == Tests for MidiRecorder ==
class TestMidiRecorder:

    @pytest.fixture(autouse=True)
    def setup_mocks(
        self, mock_mido_get_input_names, mock_mido_open_input
    ):  # Removed mock_mido_file_save
        # Ensure these mocks are active for all tests in this class
        self.mock_mido_get_input_names = mock_mido_get_input_names
        self.mock_mido_open_input, self.mock_port = mock_mido_open_input
        # self.mock_mido_file_save = mock_mido_file_save # Removed

    @pytest.fixture
    def initial_devices(self, db_session: Session):
        """Creates initial devices in DB for MidiRecorder tests."""
        dev1 = MidiDeviceModel(name="Device 1", system_identifier="SysID1")
        dev2 = MidiDeviceModel(name="Device 2", system_identifier="SysID2")
        db_session.add_all([dev1, dev2])
        db_session.commit()
        return [dev1, dev2]

    def test_recorder_init_success(
        self, db_session: Session, test_project_model: ProjectModel, initial_devices
    ):
        recorder = MidiRecorder(
            project_id=test_project_model.id,
            selected_device_names=["Device 1", "Device 2"],
            session_name="Test Session",
            db=db_session,
        )
        assert recorder.project_id == test_project_model.id
        assert recorder.session_name == "Test Session"
        assert len(recorder.target_devices) == 2
        assert {dev.name for dev in recorder.target_devices} == {"Device 1", "Device 2"}

        capture_session = (
            db_session.query(MidiCaptureSessionModel)
            .filter_by(project_id=test_project_model.id)
            .first()
        )
        assert capture_session is not None
        assert capture_session.name == "Test Session"
        assert capture_session.status == "pending"
        assert recorder.capture_session == capture_session

    def test_recorder_init_invalid_project_id(self, db_session: Session, initial_devices):
        with pytest.raises(ValueError, match="Project with ID 999 not found"):
            MidiRecorder(
                project_id=999,
                selected_device_names=["Device 1"],
                session_name="Test Session",
                db=db_session,
            )

    def test_recorder_init_non_existent_device_name(
        self,
        db_session: Session,
        test_project_model: ProjectModel,
        initial_devices,
        caplog,
    ):
        # "Device 3" does not exist, "Device 1" does.
        recorder = MidiRecorder(
            project_id=test_project_model.id,
            selected_device_names=["Device 1", "Device 3"],
            session_name="Partial Device Session",
            db=db_session,
        )
        assert len(recorder.target_devices) == 1
        assert recorder.target_devices[0].name == "Device 1"
        assert "Warning: MIDI device 'Device 3' not found in database" in caplog.text

        # Test if all devices are non-existent
        with pytest.raises(ValueError, match="No valid MIDI devices were found or specified"):
            MidiRecorder(
                project_id=test_project_model.id,
                selected_device_names=["Device 3", "Device 4"],
                session_name="No Device Session",
                db=db_session,
            )

    def test_recorder_init_empty_device_list(
        self, db_session: Session, test_project_model: ProjectModel
    ):
        with pytest.raises(ValueError, match="No valid MIDI devices were found or specified"):
            MidiRecorder(
                project_id=test_project_model.id,
                selected_device_names=[],
                session_name="Empty Device Session",
                db=db_session,
            )

    @patch("os.makedirs")
    def test_recorder_directory_paths(
        self,
        mock_os_makedirs,
        db_session: Session,
        test_project_model: ProjectModel,
        initial_devices,
    ):
        """
        Tests the creation of the base output directory for a session.
        MIDI files themselves are not stored here but in the database.
        """
        recorder = MidiRecorder(
            project_id=test_project_model.id,
            selected_device_names=["Device 1"],
            session_name="Path Test Session",
            db=db_session,
        )

        # Test _get_output_directory
        expected_output_dir = os.path.join(
            "data",
            "projects",
            str(test_project_model.id),
            "midi_captures",
            sanitize_filename("Path Test Session"),
        )
        assert recorder._get_output_directory() == expected_output_dir
        mock_os_makedirs.assert_called_with(expected_output_dir, exist_ok=True)

        # _get_midi_filepath method was removed, so tests for it are removed.
        # The _get_output_directory still creates the base session directory.
        # If device-specific subdirectories were created by _get_midi_filepath,
        # those os.makedirs calls are no longer expected here unless _get_output_directory
        # itself creates them (which it doesn't in the current implementation).
        # The current _get_output_directory only creates the main session capture directory.
        # The test for _get_midi_filepath was part of this test, so we just ensure
        # the remaining part for _get_output_directory is correct.
        # mock_os_makedirs.assert_any_call was for the device specific dir,
        # which is no longer made by _get_midi_filepath

    def test_recorder_start_recording_success(
        self, db_session: Session, test_project_model: ProjectModel, initial_devices
    ):
        recorder = MidiRecorder(
            project_id=test_project_model.id,
            selected_device_names=["Device 1"],
            session_name="Start Test",
            db=db_session,
        )

        original_start_time = datetime.datetime.utcnow() - datetime.timedelta(seconds=10)
        recorder.capture_session.start_time = (
            original_start_time  # set it to something in the past
        )

        with patch("src.core.midi_capture.datetime") as mock_datetime:
            # mock_datetime.datetime.utcnow.return_value will be the start_time
            fixed_start_time = datetime.datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.datetime.utcnow.return_value = fixed_start_time

            recorder.start_recording(db_session)

        assert recorder.active is True
        self.mock_mido_open_input.assert_called_with("Device 1", callback=ANY)
        assert len(recorder.midi_inputs) == 1
        assert recorder.midi_inputs["Device 1"] == self.mock_port

        db_session.refresh(recorder.capture_session)  # Refresh from DB
        assert recorder.capture_session.status == "recording"
        assert recorder.capture_session.start_time == fixed_start_time

    def test_recorder_start_recording_already_active(
        self,
        db_session: Session,
        test_project_model: ProjectModel,
        initial_devices,
        caplog,
    ):
        recorder = MidiRecorder(
            project_id=test_project_model.id,
            selected_device_names=["Device 1"],
            session_name="Active Test",
            db=db_session,
        )
        recorder.active = True  # Manually set to active
        recorder.start_recording(db_session)
        assert "Recording is already active." in caplog.text
        assert not self.mock_mido_open_input.called

    def test_recorder_start_recording_port_open_failure(
        self,
        db_session: Session,
        test_project_model: ProjectModel,
        initial_devices,
        caplog,
    ):
        self.mock_mido_open_input.side_effect = Exception("Failed to open port")

        recorder = MidiRecorder(
            project_id=test_project_model.id,
            selected_device_names=["Device 1", "Device 2"],  # Try to open two
            session_name="Port Fail Test",
            db=db_session,
        )
        recorder.start_recording(db_session)

        assert recorder.active is False
        assert len(recorder.midi_inputs) == 0
        assert "Error opening MIDI device Device 1: Failed to open port" in caplog.text
        assert "Error opening MIDI device Device 2: Failed to open port" in caplog.text
        assert (
            "No MIDI input ports could be opened. Recording cannot start."
            in caplog.text
        )

        db_session.refresh(recorder.capture_session)
        assert recorder.capture_session.status == "failed"  # Check if status updated in DB

    def test_recorder_midi_callback(
        self, db_session: Session, test_project_model: ProjectModel, initial_devices
    ):
        recorder = MidiRecorder(
            project_id=test_project_model.id,
            selected_device_names=["Device 1"],
            session_name="Callback Test",
            db=db_session,
        )
        recorder.active = True  # Enable callback processing

        # Simulate a MIDI message with a channel
        msg_ch1 = mido.Message("note_on", note=60, velocity=100, channel=0, time=0.1)
        recorder._midi_callback(msg_ch1, device_name="Device 1")

        assert len(recorder.midi_files) == 1
        file_key_ch1 = ("Device 1", 0)
        assert file_key_ch1 in recorder.midi_files
        mfile_ch1 = recorder.midi_files[file_key_ch1]
        assert isinstance(mfile_ch1, mido.MidiFile)
        assert len(mfile_ch1.tracks) == 1
        assert len(mfile_ch1.tracks[0]) == 2  # Track name meta message + msg_ch1
        assert mfile_ch1.tracks[0][1] == msg_ch1  # msg_ch1 is the second message

        # Simulate a system common message (no channel)
        msg_sys = mido.Message("songpos", pos=123, time=0.2)  # songpos does not have channel
        recorder._midi_callback(msg_sys, device_name="Device 1")

        # Default channel for no-channel messages
        file_key_sys = ("Device 1", -1)  # Default channel for no-channel messages
        assert file_key_sys in recorder.midi_files
        mfile_sys = recorder.midi_files[file_key_sys]
        assert isinstance(mfile_sys, mido.MidiFile)
        assert len(mfile_sys.tracks) == 1
        assert len(mfile_sys.tracks[0]) == 2  # Track name meta message + msg_sys
        assert mfile_sys.tracks[0][1] == msg_sys  # msg_sys is the second message

        # Add another message to channel 0
        msg_ch1_off = mido.Message("note_off", note=60, velocity=0, channel=0, time=0.3)
        recorder._midi_callback(msg_ch1_off, device_name="Device 1")
        assert len(mfile_ch1.tracks[0]) == 3  # Meta, msg_ch1, msg_ch1_off
        assert mfile_ch1.tracks[0][2] == msg_ch1_off

    # Mock makedirs for _get_output_directory, though not strictly for MIDI
    # files.
    @patch("os.makedirs")
    def test_recorder_stop_recording_success(
        self,
        mock_os_makedirs,
        db_session: Session,
        test_project_model: ProjectModel,
        initial_devices,
    ):
        """
        Tests successful recording stop, ensuring MIDI data is stored in the database.
        """
        recorder = MidiRecorder(
            project_id=test_project_model.id,
            selected_device_names=["Device 1"],
            session_name="Stop Test",
            db=db_session,
        )
        recorder.active = True
        # Simulate an opened port
        recorder.midi_inputs["Device 1"] = self.mock_port

        # Populate some mock MIDI data
        msg1 = mido.Message("note_on", channel=0, note=60)
        msg2 = mido.Message("note_off", channel=0, note=60)
        mfile = mido.MidiFile(type=1)
        mfile.add_track()
        mfile.tracks[0].extend([msg1, msg2])
        recorder.midi_files[("Device 1", 0)] = mfile

        original_end_time = datetime.datetime.utcnow() - datetime.timedelta(seconds=10)
        recorder.capture_session.end_time = original_end_time

        with patch("src.core.midi_capture.datetime") as mock_datetime:
            fixed_end_time = datetime.datetime(
                2023, 1, 1, 12, 5, 0
            )  # 5 mins after fixed_start_time
            mock_datetime.datetime.utcnow.return_value = fixed_end_time

            recorder.stop_recording(db_session)

        assert recorder.active is False
        self.mock_port.close.assert_called_once()
        assert len(recorder.midi_inputs) == 0

        # Verify MidiFile record in DB
        db_midi_files = db_session.query(MidiFileModel).all()
        assert len(db_midi_files) == 1
        db_mf = db_midi_files[0]
        assert db_mf.midi_capture_session_id == recorder.capture_session.id
        assert db_mf.midi_device_id == initial_devices[0].id  # Device 1
        assert db_mf.channel_number == 0

        # Generate expected MIDI bytes
        expected_mido_output = mido.MidiFile(type=1)
        track = expected_mido_output.add_track(
            name=f"{sanitize_filename('Device 1')}_ch0"
        )  # Match track name if important
        track.extend([msg1, msg2])

        expected_buffer = io.BytesIO()
        expected_mido_output.save(file=expected_buffer)
        expected_bytes = expected_buffer.getvalue()
        expected_buffer.close()

        assert db_mf.midi_data == expected_bytes  # Compare blob data
        # self.mock_mido_file_save.assert_called_once_with(expected_path) #
        # Removed

        db_session.refresh(recorder.capture_session)
        assert recorder.capture_session.status == "completed"
        assert recorder.capture_session.end_time == fixed_end_time
        assert len(recorder.midi_files) == 0  # Should be cleared

    def test_recorder_stop_recording_not_active(
        self,
        db_session: Session,
        test_project_model: ProjectModel,
        initial_devices,
        caplog,
    ):
        recorder = MidiRecorder(
            project_id=test_project_model.id,
            selected_device_names=["Device 1"],
            session_name="Not Active Stop Test",
            db=db_session,
        )
        recorder.active = False  # Not active
        recorder.stop_recording(db_session)
        assert "Recording is not currently active." in caplog.text
        # assert not self.mock_mido_file_save.called # mock_mido_file_save
        # fixture is removed/changed

    @patch("os.makedirs")
    def test_recorder_stop_recording_no_messages(
        self,
        mock_os_makedirs,
        db_session: Session,
        test_project_model: ProjectModel,
        initial_devices,
        caplog,
    ):
        recorder = MidiRecorder(
            project_id=test_project_model.id,
            selected_device_names=["Device 1"],
            session_name="No Message Stop Test",
            db=db_session,
        )
        recorder.active = True
        # Simulate an opened port
        recorder.midi_inputs["Device 1"] = self.mock_port
        # recorder.midi_files remains empty

        recorder.stop_recording(db_session)

        assert recorder.active is False
        assert db_session.query(MidiFileModel).count() == 0
        # assert not self.mock_mido_file_save.called # mock_mido_file_save
        # fixture is removed/changed

        db_session.refresh(recorder.capture_session)
        assert (
            recorder.capture_session.status == "completed_empty"
        )  # or "completed" based on implementation for empty
        assert "No MIDI messages were captured." in caplog.text  # Or similar log


# --- Tests for Project class MIDI methods ---
# These tests will use the test_project_instance which should be configured
# to use the in-memory test DB for its operations.


class TestProjectMidiMethods:

    @pytest.fixture(autouse=True)
    def setup_project_mocks(
        self, mock_mido_get_input_names, mock_mido_open_input
    ):  # Removed mock_mido_file_save
        # Mocks for mido needed if project methods call underlying midi_capture
        # functions
        self.mock_mido_get_input_names = mock_mido_get_input_names
        self.mock_mido_open_input, self.mock_port = mock_mido_open_input
        # self.mock_mido_file_save = mock_mido_file_save # Removed

    def test_project_list_midi_devices(
        self, test_project_instance: Project, db_session: Session
    ):
        self.mock_mido_get_input_names.return_value = [
            "Project Device A",
            "Project Device B",
        ]

        # The Project.list_midi_devices uses SessionLocal internally.
        # We need to ensure it's using the test SessionLocal.
        with patch("src.core.project.SessionLocal", get_test_session_local()):
            devices = test_project_instance.list_midi_devices()

        assert len(devices) == 2
        assert {dev.name for dev in devices} == {"Project Device A", "Project Device B"}
        # Verify they are in the DB via the passed db_session to be sure
        db_devs = (
            db_session.query(MidiDeviceModel)
            .filter(MidiDeviceModel.name.like("Project Device %"))
            .all()
        )
        assert len(db_devs) == 2

    def test_project_create_midi_capture_session(
        self, test_project_instance: Project, db_session: Session
    ):
        # Ensure "Device 1" exists for MidiRecorder init
        db_session.add(MidiDeviceModel(name="Device 1", system_identifier="SysID1"))
        db_session.commit()

        with patch("src.core.project.SessionLocal", get_test_session_local()):
            recorder = test_project_instance.create_midi_capture_session(
                session_name="Project MIDI Session", selected_device_names=["Device 1"]
            )

        assert isinstance(recorder, MidiRecorder)
        assert recorder.session_name == "Project MIDI Session"
        assert recorder.project_id == test_project_instance.project_id

        # Verify session created in DB
        capture_session_model = (
            db_session.query(MidiCaptureSessionModel)
            .filter_by(
                project_id=test_project_instance.project_id, name="Project MIDI Session"
            )
            .one_or_none()
        )
        assert capture_session_model is not None
        assert recorder.capture_session.id == capture_session_model.id

    def test_project_list_midi_capture_sessions(
        self, test_project_instance: Project, db_session: Session
    ):
        proj_id = test_project_instance.project_id
        # Create some sessions directly
        s1 = MidiCaptureSessionModel(project_id=proj_id, name="Session 1", status="completed")
        s2 = MidiCaptureSessionModel(project_id=proj_id, name="Session 2", status="pending")
        # A session for another project
        s_other = MidiCaptureSessionModel(
            project_id=999, name="Other Project Session", status="completed"
        )
        db_session.add_all([s1, s2, s_other])
        db_session.commit()

        with patch("src.core.project.SessionLocal", get_test_session_local()):
            sessions = test_project_instance.list_midi_capture_sessions()

        assert len(sessions) == 2
        assert {s.name for s in sessions} == {"Session 1", "Session 2"}
        # Default order is created_at.desc, s2 is newer if committed after s1
        # or if time is mocked. Assuming s2 is "newer".
        assert sessions[0].name == "Session 2"
        # Actual order depends on precise created_at. Let's check for names.

    def test_project_get_midi_capture_session(
        self, test_project_instance: Project, db_session: Session
    ):
        proj_id = test_project_instance.project_id
        s1 = MidiCaptureSessionModel(
            project_id=proj_id, name="Target Session", status="completed"
        )
        db_session.add(s1)
        db_session.commit()
        db_session.refresh(s1)  # Get ID

        with patch("src.core.project.SessionLocal", get_test_session_local()):
            # Found
            found_session = test_project_instance.get_midi_capture_session(s1.id)
            assert found_session is not None
            assert found_session.id == s1.id

            # Not found
            not_found_session = test_project_instance.get_midi_capture_session(9999)
            assert not_found_session is None

            # Belongs to another project (create another project and session)
            other_proj = ProjectModel(name="Other Project")
            db_session.add(other_proj)
            db_session.commit()
            s_other_proj = MidiCaptureSessionModel(
                project_id=other_proj.id, name="Session From Other", status="pending"
            )
            db_session.add(s_other_proj)
            db_session.commit()
            db_session.refresh(s_other_proj)

            found_other_session = test_project_instance.get_midi_capture_session(
                s_other_proj.id
            )
            assert found_other_session is None

    def test_project_get_midi_files_for_session(
        self, test_project_instance: Project, db_session: Session
    ):
        proj_id = test_project_instance.project_id

        # Setup: Device, Session, MidiFiles
        device = MidiDeviceModel(name="Test Device For Files", system_identifier="TDFS")
        session = MidiCaptureSessionModel(
            project_id=proj_id, name="Session With Files", status="completed"
        )
        db_session.add_all([device, session])
        db_session.commit()
        db_session.refresh(device)
        db_session.refresh(session)

        # Create MidiFileModel instances with midi_data (binary content).
        # Minimal valid MIDI
        test_midi_data_1 = b"\x4d\x54\x68\x64\x00\x00\x00\x06\x00\x01\x00\x01\x01\xe0"
        test_midi_data_2 = b"\x4d\x54\x68\x64\x00\x00\x00\x06\x00\x01\x00\x01\x01\xe0\x4d\x54\x72\x6b\x00\x00\x00\x04\x00\xff\x2f\x00"  # Minimal with track
        mf1 = MidiFileModel(
            midi_capture_session_id=session.id,
            midi_device_id=device.id,
            channel_number=0,
            midi_data=test_midi_data_1,
        )
        mf2 = MidiFileModel(
            midi_capture_session_id=session.id,
            midi_device_id=device.id,
            channel_number=1,
            midi_data=test_midi_data_2,
        )
        db_session.add_all([mf1, mf2])
        db_session.commit()
        db_session.refresh(mf1)  # Refresh to get any db-generated values if needed by tests
        db_session.refresh(mf2)

        with patch("src.core.project.SessionLocal", get_test_session_local()):
            # Test with files
            files = test_project_instance.get_midi_files_for_session(session.id)
            assert len(files) == 2
            # Verify that the retrieved files have the correct midi_data
            retrieved_data = sorted([f.midi_data for f in files])
            expected_data = sorted([test_midi_data_1, test_midi_data_2])
            assert retrieved_data[0] == expected_data[0]
            assert retrieved_data[1] == expected_data[1]
            # Original assertion for file_path is no longer valid:
            # assert {f.file_path for f in files} == {"/path/mf1.mid", "/path/mf2.mid"}

            # Test with a session that has no files
            session_no_files = MidiCaptureSessionModel(
                project_id=proj_id, name="Session No Files", status="completed"
            )
            db_session.add(session_no_files)
            db_session.commit()
            db_session.refresh(session_no_files)
            files_empty = test_project_instance.get_midi_files_for_session(session_no_files.id)
            assert len(files_empty) == 0

            # Test with invalid session ID
            files_invalid_session = test_project_instance.get_midi_files_for_session(99999)
            assert len(files_invalid_session) == 0
