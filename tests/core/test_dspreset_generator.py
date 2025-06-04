import unittest
import os
import shutil
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch
from typing import List, Optional, Any  # For type hinting

from src.core.dspreset_generator import DecentSamplerPresetGenerator
from src.core.instrument_data import InstrumentData

# Correcting model imports to align with typical project structure if database.models is an alias
# Assuming models are directly in src.models.<model_name>_model
from src.models.project_model import ProjectModel
from src.models.recording_model import RecordingModel
from src.models.sample_model import SampleModel
from src.models.sample_mapping_item_model import SampleMappingItemModel
from src.core.project_manager import Project

# from typing import List, Optional, Any # This was moved up already, ensuring it's there.


@unittest.skip(
    "Skipping outdated test suite TestDecentSamplerPresetGenerator. test_dspreset_generator_new.py covers current functionality."
)
class TestDecentSamplerPresetGenerator(unittest.TestCase):
    test_output_base_dir: str
    mock_project_model: ProjectModel
    mock_recording_model: RecordingModel
    mock_project: MagicMock  # Mock for Project core object
    instrument_data: InstrumentData  # This is a real InstrumentData object
    # Add mocks for file system and XML operations
    patcher_os_makedirs: Any  # Was unittest.mock._patch[MagicMock]
    patcher_os_path_exists: Any  # Was unittest.mock._patch[MagicMock]
    patcher_shutil_copy2: Any  # Was unittest.mock._patch[MagicMock]
    patcher_et_write: Any  # Was unittest.mock._patch[MagicMock]
    mock_os_makedirs: MagicMock
    mock_os_path_exists: MagicMock
    mock_shutil_copy2: MagicMock
    mock_et_write: MagicMock

    dummy_artwork_src_dir: str
    dummy_samples_src_dir: str
    dummy_bg_image_path: str
    dummy_sample1_path: str
    dummy_sample2_path: str

    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        self.test_output_base_dir = "temp_test_output_dspreset"
        if os.path.exists(self.test_output_base_dir):
            shutil.rmtree(self.test_output_base_dir)
        os.makedirs(self.test_output_base_dir, exist_ok=True)

        self.mock_project_model = ProjectModel(id=1, name="Test Project")
        self.mock_recording_model = RecordingModel(
            id=1, project_id=1, name="Test Recording", samples=[]
        )
        # Ensure the relationship is correctly typed if ProjectModel expects List[RecordingModel]
        self.mock_project_model.recordings = [self.mock_recording_model]  # type: ignore

        self.mock_project = MagicMock()
        self.mock_project.project_id = 1
        self.mock_project.project_model = self.mock_project_model

        self.instrument_data = InstrumentData(name="My Test Instrument", author="Tester")

        self.dummy_artwork_src_dir = os.path.join(
            self.test_output_base_dir, "dummy_source_artwork"
        )
        self.dummy_samples_src_dir = os.path.join(
            self.test_output_base_dir, "dummy_source_samples"
        )
        os.makedirs(self.dummy_artwork_src_dir, exist_ok=True)
        os.makedirs(self.dummy_samples_src_dir, exist_ok=True)

        self.dummy_bg_image_path = os.path.join(self.dummy_artwork_src_dir, "background.png")
        with open(self.dummy_bg_image_path, "w") as f:
            f.write("dummy_image_content")
        self.instrument_data.ui_background_image_path = self.dummy_bg_image_path

        self.dummy_sample1_path = os.path.join(self.dummy_samples_src_dir, "s1.wav")
        self.dummy_sample2_path = os.path.join(self.dummy_samples_src_dir, "s2.wav")
        with open(self.dummy_sample1_path, "w") as f:
            f.write("s1_content")
        with open(self.dummy_sample2_path, "w") as f:
            f.write("s2_content")

        # Start mock patchers
        self.patcher_os_makedirs = patch("src.core.dspreset_generator.os.makedirs")
        self.mock_os_makedirs = self.patcher_os_makedirs.start()

        self.patcher_os_path_exists = patch("src.core.dspreset_generator.os.path.exists")
        self.mock_os_path_exists = self.patcher_os_path_exists.start()
        # Default to True for os.path.exists to simplify tests that need files to "exist"
        self.mock_os_path_exists.return_value = True

        self.patcher_shutil_copy2 = patch("src.core.dspreset_generator.shutil.copy2")
        self.mock_shutil_copy2 = self.patcher_shutil_copy2.start()

        self.patcher_et_write = patch(
            "xml.etree.ElementTree.ElementTree.write"
        )  # Path to ET.write within the module it's used
        self.mock_et_write = self.patcher_et_write.start()

    def tearDown(self) -> None:
        """Clean up test fixtures after each test method."""
        if os.path.exists(
            self.test_output_base_dir
        ):  # This part is for the integration-style tests
            shutil.rmtree(self.test_output_base_dir)

        # Stop mock patchers
        self.patcher_os_makedirs.stop()
        self.patcher_os_path_exists.stop()
        self.patcher_shutil_copy2.stop()
        self.patcher_et_write.stop()

    def test_sanitize_filename(self) -> None:
        """Test the _sanitize_filename method."""
        # No need to create the full generator for this static-like method test
        # If it were not static, we'd use:
        # generator = DecentSamplerPresetGenerator(self.mock_project, self.instrument_data, self.test_output_base_dir)

        # Directly calling via class if it could be @staticmethod or by instantiating a dummy version
        # For now, assuming it can be called on an instance even if project/instrument_data are not strictly needed for this method
        generator = DecentSamplerPresetGenerator(None, None, None)  # type: ignore [arg-type] # Or provide minimal mocks

        # Input with spaces
        self.assertEqual(
            generator._sanitize_filename("file with spaces.wav"), "file_with_spaces.wav"
        )
        # Input with mixed case
        self.assertEqual(
            generator._sanitize_filename("MixedCaseFile.WAV"), "mixedcasefile.wav"
        )
        # Input that is already sanitized
        self.assertEqual(
            generator._sanitize_filename("already_sanitized.wav"), "already_sanitized.wav"
        )
        # Input with special characters
        self.assertEqual(
            generator._sanitize_filename("file-with!@#$%^&*().wav"), "file-with.wav"
        )
        self.assertEqual(
            generator._sanitize_filename("another_one_with_üöä.mp3"), "another_one_with_.mp3"
        )
        # Test with empty string if relevant, though current implementation might not expect it
        # self.assertEqual(generator._sanitize_filename(""), "")
        # Test with leading/trailing problematic chars
        self.assertEqual(
            generator._sanitize_filename("-leading-trailing-.wav"), "leading-trailing-.wav"
        )

    # --- New tests using mocks for generate_preset ---

    def _setup_mock_project_data(
        self,
        num_recordings=1,
        num_samples_per_recording=1,
        with_mappings=True,
        with_bg_image=True,
    ):
        """Helper to set up mock project, recordings, samples, and instrument data for mocked tests."""
        self.mock_project_model = MagicMock(spec=ProjectModel)
        self.mock_project_model.name = "Mocked Project"
        self.mock_project_model.id = 1

        mock_recordings = []
        for i in range(num_recordings):
            mock_rec = MagicMock(spec=RecordingModel)
            mock_rec.name = f"Recording_{i+1}"
            mock_rec.id = i + 1
            mock_samples = []
            for j in range(num_samples_per_recording):
                mock_sample = MagicMock(spec=SampleModel)
                mock_sample.name = f"sample_{i+1}_{j+1}.wav"
                # In mocked tests, this path will be used to form the XML path,
                # and shutil.copy2 will be mocked, so it doesn't need to exist.
                mock_sample.file_path = f"/dummy/path/to/sample_{i+1}_{j+1}.wav"
                mock_sample.midi_pitch = 60 + j
                mock_sample.id = (i * num_samples_per_recording) + j + 1

                if with_mappings:
                    mock_mapping = MagicMock(spec=SampleMappingItemModel)
                    mock_mapping.key_range_start = 60 + j
                    mock_mapping.key_range_end = 60 + j
                    mock_mapping.velocity_range_start = 0
                    mock_mapping.velocity_range_end = 127
                    mock_sample.sample_mapping_items = [mock_mapping]
                else:
                    mock_sample.sample_mapping_items = []
                mock_samples.append(mock_sample)
            mock_rec.samples = mock_samples
            mock_recordings.append(mock_rec)

        self.mock_project_model.recordings = mock_recordings

        self.mock_project = MagicMock(spec=Project)  # Mock the Project core class
        self.mock_project.project_id = self.mock_project_model.id
        self.mock_project.project_model = self.mock_project_model

        self.instrument_data = InstrumentData(name="Mocked Instrument", author="Mocker")
        if with_bg_image:
            self.instrument_data.ui_background_image_path = "/dummy/path/to/background.png"
        else:
            self.instrument_data.ui_background_image_path = None

        # Ensure os.path.exists returns True for these dummy paths if they are checked
        # The general mock_os_path_exists.return_value = True already covers this
        # but can be more specific if needed:
        # self.mock_os_path_exists.side_effect = lambda p: p in [self.instrument_data.ui_background_image_path] + [s.file_path for r in mock_recordings for s in r.samples]

    # --- Tests for generate_preset (Successful Scenarios) ---

    def test_generate_preset_basic_success(self):
        self._setup_mock_project_data(
            num_recordings=1,
            num_samples_per_recording=1,
            with_mappings=True,
            with_bg_image=True,
        )

        # For these tests, the output_base_dir is just a string, os.makedirs is mocked
        output_base_dir = "/mocked/output"
        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, output_base_dir
        )
        generator.generate_preset()

        sanitized_instrument_name = "mocked_instrument"
        expected_instrument_dir = os.path.join(output_base_dir, sanitized_instrument_name)
        expected_samples_dir = os.path.join(expected_instrument_dir, "Samples")
        expected_artwork_dir = os.path.join(expected_instrument_dir, "Artwork")

        # Assert os.makedirs calls
        self.mock_os_makedirs.assert_any_call(expected_instrument_dir, exist_ok=True)
        self.mock_os_makedirs.assert_any_call(expected_samples_dir, exist_ok=True)
        self.mock_os_makedirs.assert_any_call(expected_artwork_dir, exist_ok=True)

        # Assert shutil.copy2 calls
        self.assertIsNotNone(
            self.instrument_data.ui_background_image_path
        )  # Ensure path exists for type checker
        self.mock_shutil_copy2.assert_any_call(
            self.instrument_data.ui_background_image_path,
            os.path.join(expected_artwork_dir, "background.png"),  # Sanitized name from path
        )
        mock_sample = self.mock_project_model.recordings[0].samples[0]
        self.mock_shutil_copy2.assert_any_call(
            mock_sample.file_path,
            os.path.join(
                expected_samples_dir,
                generator._sanitize_filename(os.path.basename(mock_sample.file_path)),
            ),
        )

        # Assert ET.ElementTree.write call
        expected_xml_path = os.path.join(
            expected_instrument_dir, f"{sanitized_instrument_name}.dspreset"
        )
        self.mock_et_write.assert_called_once()
        # First argument to write is the ElementTree object, second is the path
        call_args = self.mock_et_write.call_args[0]
        written_tree = call_args[0]  # ET.ElementTree instance
        written_path = call_args[1]
        self.assertEqual(written_path, expected_xml_path)

        # Verify XML structure (basic checks, can be more detailed)
        root_element = written_tree.getroot()
        self.assertEqual(root_element.tag, "DecentSampler")
        self.assertEqual(root_element.get("minVersion"), "1.0.0")
        self.assertIsNotNone(root_element.find("ui"))
        self.assertIsNotNone(
            root_element.find(f"ui/tab/background[@image='Artwork{os.sep}background.png']")
        )
        self.assertIsNotNone(root_element.find("groups"))
        self.assertIsNotNone(root_element.find("groups/group"))
        # Path for sample in XML is relative to Samples dir
        expected_sample_xml_path = os.path.join(
            "Samples", generator._sanitize_filename(os.path.basename(mock_sample.file_path))
        )
        self.assertIsNotNone(
            root_element.find(f"groups/group/sample[@path='{expected_sample_xml_path}']")
        )
        # Add more detailed checks for rootNote, loKey, hiKey etc.

    def test_generate_preset_no_ui_background_image(self):
        self._setup_mock_project_data(with_bg_image=False)
        output_base_dir = "/mocked/output"
        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, output_base_dir
        )
        generator.generate_preset()

        # Verify no attempt to copy artwork
        # self.mock_shutil_copy2.assert_not_any # this is tricky, need to check calls carefully
        artwork_copy_calls = [
            c for c in self.mock_shutil_copy2.call_args_list if "Artwork" in c[0][1]
        ]
        self.assertEqual(
            len(artwork_copy_calls), 0, "Should not attempt to copy artwork if no path is set"
        )

        # Verify <ui> element is created but without a background image
        self.mock_et_write.assert_called_once()
        written_tree = self.mock_et_write.call_args[0][0]
        root_element = written_tree.getroot()
        ui_element = root_element.find("ui")
        self.assertIsNotNone(ui_element)
        self.assertIsNone(ui_element.find("tab/background"))

    def test_generate_preset_project_no_recordings(self):
        self._setup_mock_project_data(num_recordings=0)
        output_base_dir = "/mocked/output"
        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, output_base_dir
        )
        generator.generate_preset()

        self.mock_et_write.assert_called_once()
        written_tree = self.mock_et_write.call_args[0][0]
        root_element = written_tree.getroot()
        groups_element = root_element.find("groups")
        self.assertIsNotNone(groups_element)
        self.assertEqual(len(list(groups_element)), 0)  # No <group> children

    # --- Tests for generate_preset (Error Handling and Edge Cases) ---

    @patch("src.core.dspreset_generator.print")  # Mock print for checking warnings
    def test_generate_preset_missing_ui_background_image_file(self, mock_print):
        self._setup_mock_project_data(with_bg_image=True)
        self.assertIsNotNone(self.instrument_data.ui_background_image_path)
        self.mock_os_path_exists.side_effect = lambda p: p != self.instrument_data.ui_background_image_path  # type: ignore

        output_base_dir = "/mocked/output"
        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, output_base_dir
        )
        generator.generate_preset()

        mock_print.assert_any_call(
            f"Warning: UI background image not found at {self.instrument_data.ui_background_image_path}, skipping."
        )
        # Check XML: UI tab should exist, but no background element
        self.mock_et_write.assert_called_once()
        written_tree = self.mock_et_write.call_args[0][0]
        root = written_tree.getroot()
        self.assertIsNone(root.find("ui/tab/background"))

    @patch("src.core.dspreset_generator.print")
    def test_generate_preset_missing_sample_file(self, mock_print):
        self._setup_mock_project_data(
            num_samples_per_recording=2
        )  # Ensure there's another sample
        mock_sample_to_miss = self.mock_project_model.recordings[0].samples[0]

        # os.path.exists returns False only for the first sample, True for UI image and other samples
        def selective_exists(path_to_check):
            if path_to_check == mock_sample_to_miss.file_path:
                return False
            return True  # Covers UI image, other samples, and directory checks if any

        self.mock_os_path_exists.side_effect = selective_exists

        output_base_dir = "/mocked/output"
        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, output_base_dir
        )
        generator.generate_preset()

        mock_print.assert_any_call(
            f"Warning: Sample file not found at {mock_sample_to_miss.file_path}, skipping."
        )

        self.mock_et_write.assert_called_once()
        written_tree = self.mock_et_write.call_args[0][0]
        root = written_tree.getroot()
        samples_in_xml = root.findall("groups/group/sample")
        self.assertEqual(len(samples_in_xml), 1)  # Only one sample should be included
        # Check that the included sample is not the one that was "missing"
        self.assertNotEqual(
            samples_in_xml[0].get("path"),
            os.path.join(
                "Samples",
                generator._sanitize_filename(os.path.basename(mock_sample_to_miss.file_path)),
            ),
        )

    @patch("src.core.dspreset_generator.print")
    def test_generate_preset_oserror_on_makedirs(self, mock_print):
        self._setup_mock_project_data()
        self.mock_os_makedirs.side_effect = OSError("Test OSError")

        output_base_dir = "/mocked/output"
        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, output_base_dir
        )
        generator.generate_preset()

        mock_print.assert_any_call("Error creating directories: Test OSError")
        self.mock_et_write.assert_not_called()  # Should not proceed to XML writing

    @patch("src.core.dspreset_generator.print")
    def test_generate_preset_ioerror_on_artwork_copy(self, mock_print):
        self._setup_mock_project_data(with_bg_image=True)
        self.assertIsNotNone(self.instrument_data.ui_background_image_path)
        # os.path.exists for the image file should be True (default mock behavior)
        self.mock_shutil_copy2.side_effect = lambda src, dst: (
            (_ for _ in ()).throw(IOError("Test IOError on artwork"))
            if "Artwork" in dst
            else None
        )

        output_base_dir = "/mocked/output"
        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, output_base_dir
        )
        generator.generate_preset()

        mock_print.assert_any_call(
            f"Error copying artwork from {self.instrument_data.ui_background_image_path}: Test IOError on artwork"
        )
        # XML might still be written, but without artwork reference or handled gracefully
        self.mock_et_write.assert_called_once()
        written_tree = self.mock_et_write.call_args[0][0]
        root = written_tree.getroot()
        self.assertIsNone(root.find("ui/tab/background"))

    @patch("src.core.dspreset_generator.print")
    def test_generate_preset_ioerror_on_sample_copy(self, mock_print):
        self._setup_mock_project_data(num_samples_per_recording=2)  # sample1, sample2
        mock_sample_to_fail_copy = self.mock_project_model.recordings[0].samples[0]

        # shutil.copy2 raises IOError only for the first sample
        def selective_copy2(src, dst):
            if src == mock_sample_to_fail_copy.file_path:
                raise IOError("Test IOError on sample copy")
            # For other copies (artwork, other samples), do nothing (mocked success)

        self.mock_shutil_copy2.side_effect = selective_copy2
        # Ensure os.path.exists is True for all files initially
        self.mock_os_path_exists.return_value = True

        output_base_dir = "/mocked/output"
        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, output_base_dir
        )
        generator.generate_preset()

        mock_print.assert_any_call(
            f"Error copying sample file {mock_sample_to_fail_copy.file_path}: Test IOError on sample copy"
        )

        self.mock_et_write.assert_called_once()
        written_tree = self.mock_et_write.call_args[0][0]
        root = written_tree.getroot()
        samples_in_xml = root.findall("groups/group/sample")
        self.assertEqual(len(samples_in_xml), 1)  # Only the second sample should be included
        # Check that the included sample is not the one that failed copying
        self.assertNotEqual(
            samples_in_xml[0].get("path"),
            os.path.join(
                "Samples",
                generator._sanitize_filename(
                    os.path.basename(mock_sample_to_fail_copy.file_path)
                ),
            ),
        )

    @patch("src.core.dspreset_generator.print")
    def test_generate_preset_ioerror_on_xml_write(self, mock_print):
        self._setup_mock_project_data()
        self.mock_et_write.side_effect = IOError("Test IOError on XML write")

        output_base_dir = "/mocked/output"
        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, output_base_dir
        )
        generator.generate_preset()

        sanitized_instrument_name = "mocked_instrument"
        expected_xml_path = os.path.join(
            output_base_dir, sanitized_instrument_name, f"{sanitized_instrument_name}.dspreset"
        )
        mock_print.assert_any_call(
            f"Error writing XML file to {expected_xml_path}: Test IOError on XML write"
        )

    # --- End of new tests ---

    def test_directory_and_dspreset_creation(self) -> None:
        """Test creation of main instrument directory, subdirectories, and .dspreset file."""
        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, self.test_output_base_dir
        )
        generator.generate_preset()

        instrument_name_fs: str = self.instrument_data.name.replace(" ", "_").lower()
        expected_instrument_dir: str = os.path.join(
            self.test_output_base_dir, instrument_name_fs
        )

        self.assertTrue(
            os.path.isdir(expected_instrument_dir), "Instrument directory not created."
        )
        self.assertTrue(
            os.path.isdir(os.path.join(expected_instrument_dir, "Samples")),
            "Samples directory not created.",
        )
        self.assertTrue(
            os.path.isdir(os.path.join(expected_instrument_dir, "Artwork")),
            "Artwork directory not created.",
        )
        self.assertTrue(
            os.path.isfile(
                os.path.join(expected_instrument_dir, instrument_name_fs + ".dspreset")
            ),
            ".dspreset file not created.",
        )

    def test_artwork_copying_and_xml(self) -> None:
        """Test that artwork is copied and XML correctly references it."""
        self.instrument_data.ui_background_image_path = self.dummy_bg_image_path

        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, self.test_output_base_dir
        )
        generator.generate_preset()

        instrument_name_fs: str = self.instrument_data.name.replace(" ", "_").lower()
        expected_artwork_file: str = os.path.join(
            self.test_output_base_dir, instrument_name_fs, "Artwork", "background.png"
        )
        self.assertTrue(os.path.isfile(expected_artwork_file), "Artwork file not copied.")

        dspreset_path: str = os.path.join(
            self.test_output_base_dir,
            instrument_name_fs,
            instrument_name_fs + ".dspreset",
        )
        tree: ET.ElementTree = ET.parse(dspreset_path)
        root: ET.Element = tree.getroot()

        ui_element: Optional[ET.Element] = root.find("ui")
        self.assertIsNotNone(ui_element, "UI element not found in XML.")
        if ui_element is None:
            return  # For type checker

        background_element: Optional[ET.Element] = ui_element.find("tab/background")
        self.assertIsNotNone(background_element, "Background element not found in XML ui/tab.")
        if background_element is None:
            return  # For type checker

        self.assertEqual(
            background_element.get("image"),
            os.path.join("Artwork", "background.png"),
            "Background image path in XML is incorrect.",
        )

    def test_sample_copying_and_xml(self) -> None:
        """Test that samples are copied and XML correctly references them."""
        sample1_model = SampleModel(
            id=1,
            recording_id=1,
            name="s1.wav",
            file_path=self.dummy_sample1_path,
            midi_pitch=60,
            sample_mapping_items=[],  # type: ignore # Initialize with empty list
        )

        mapping_item1 = SampleMappingItemModel(
            id=1, sample_id=1, key_range_start=58, key_range_end=62
        )
        sample1_model.sample_mapping_items = [mapping_item1]  # type: ignore

        self.mock_recording_model.samples = [sample1_model]  # type: ignore

        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, self.test_output_base_dir
        )
        generator.generate_preset()

        instrument_name_fs: str = self.instrument_data.name.replace(" ", "_").lower()
        expected_sample_file: str = os.path.join(
            self.test_output_base_dir, instrument_name_fs, "Samples", "s1.wav"
        )
        self.assertTrue(os.path.isfile(expected_sample_file), "Sample file s1.wav not copied.")

        dspreset_path: str = os.path.join(
            self.test_output_base_dir,
            instrument_name_fs,
            instrument_name_fs + ".dspreset",
        )
        tree: ET.ElementTree = ET.parse(dspreset_path)
        root: ET.Element = tree.getroot()

        sample_element: Optional[ET.Element] = root.find("groups/group/sample")
        self.assertIsNotNone(sample_element, "Sample element not found in XML.")
        if sample_element is None:
            return  # For type checker

        self.assertEqual(
            sample_element.get("path"),
            os.path.join("Samples", "s1.wav"),
            "Sample path in XML is incorrect.",
        )
        self.assertEqual(
            sample_element.get("rootNote"), "60", "Sample rootNote in XML is incorrect."
        )
        self.assertEqual(
            sample_element.get("loKey"), "58", "Sample loKey in XML is incorrect."
        )
        self.assertEqual(
            sample_element.get("hiKey"), "62", "Sample hiKey in XML is incorrect."
        )
        self.assertEqual(
            sample_element.get("loVel"),
            "0",
            "Sample loVel in XML is incorrect (default).",
        )
        self.assertEqual(
            sample_element.get("hiVel"),
            "127",
            "Sample hiVel in XML is incorrect (default).",
        )

    def test_sample_copying_xml_default_keyrange(self) -> None:
        """Test sample XML when no explicit key range is defined (defaults to rootNote)."""
        sample2_model = SampleModel(
            id=2,
            recording_id=1,
            name="s2.wav",
            file_path=self.dummy_sample2_path,
            midi_pitch=72,
            sample_mapping_items=[],  # type: ignore
        )
        self.mock_recording_model.samples = [sample2_model]  # type: ignore

        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, self.test_output_base_dir
        )
        generator.generate_preset()

        instrument_name_fs: str = self.instrument_data.name.replace(" ", "_").lower()
        dspreset_path: str = os.path.join(
            self.test_output_base_dir,
            instrument_name_fs,
            instrument_name_fs + ".dspreset",
        )
        tree: ET.ElementTree = ET.parse(dspreset_path)
        root: ET.Element = tree.getroot()

        sample_element: Optional[ET.Element] = root.find("groups/group/sample")
        self.assertIsNotNone(
            sample_element, "Sample element not found in XML for default keyrange test."
        )
        if sample_element is None:
            return  # For type checker
        self.assertEqual(sample_element.get("path"), os.path.join("Samples", "s2.wav"))
        self.assertEqual(sample_element.get("rootNote"), "72")
        self.assertEqual(
            sample_element.get("loKey"), "72", "loKey should default to rootNote."
        )
        self.assertEqual(
            sample_element.get("hiKey"), "72", "hiKey should default to rootNote."
        )

    def test_xml_root_and_basic_structure(self) -> None:
        """Test the root element and basic structure of the .dspreset XML."""
        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, self.test_output_base_dir
        )
        generator.generate_preset()

        instrument_name_fs: str = self.instrument_data.name.replace(" ", "_").lower()
        dspreset_path: str = os.path.join(
            self.test_output_base_dir,
            instrument_name_fs,
            instrument_name_fs + ".dspreset",
        )

        self.assertTrue(
            os.path.isfile(dspreset_path),
            f".dspreset file not found at {dspreset_path}",
        )

        tree: ET.ElementTree = ET.parse(dspreset_path)
        root: ET.Element = tree.getroot()

        self.assertEqual(root.tag, "DecentSampler", "Root XML tag is not DecentSampler.")
        self.assertEqual(root.get("minVersion"), "1.0.0", "minVersion attribute is incorrect.")
        self.assertIsNotNone(root.find("ui"), "UI element not found.")
        self.assertIsNotNone(root.find("groups"), "Groups element not found.")
        self.assertIsNotNone(root.find("effects"), "Effects element not found.")

    def test_empty_project_no_samples_no_artwork(self) -> None:
        """Test behavior with an empty project (no recordings/samples) and no artwork."""
        self.mock_project_model.recordings = []  # type: ignore
        self.instrument_data.ui_background_image_path = None

        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, self.test_output_base_dir
        )
        generator.generate_preset()

        instrument_name_fs: str = self.instrument_data.name.replace(" ", "_").lower()
        expected_instrument_dir: str = os.path.join(
            self.test_output_base_dir, instrument_name_fs
        )
        dspreset_path: str = os.path.join(
            expected_instrument_dir, instrument_name_fs + ".dspreset"
        )

        self.assertTrue(
            os.path.isfile(dspreset_path),
            ".dspreset file not created for empty project.",
        )

        tree: ET.ElementTree = ET.parse(dspreset_path)
        root: ET.Element = tree.getroot()

        groups_element: Optional[ET.Element] = root.find("groups")
        self.assertIsNotNone(groups_element, "Groups element should exist even if empty.")
        if groups_element is None:
            return  # For type checker
        self.assertEqual(
            len(list(groups_element)),
            0,
            "Groups element should have no children (groups).",
        )

        ui_element: Optional[ET.Element] = root.find("ui")
        self.assertIsNotNone(ui_element, "UI element should exist.")
        if ui_element is None:
            return  # For type checker
        self.assertIsNone(
            ui_element.find("tab/background"),
            "Background element should not exist if no image path.",
        )

        samples_output_dir: str = os.path.join(expected_instrument_dir, "Samples")
        artwork_output_dir: str = os.path.join(expected_instrument_dir, "Artwork")
        self.assertTrue(
            os.path.isdir(samples_output_dir),
            "Samples directory should still be created.",
        )
        self.assertTrue(
            os.path.isdir(artwork_output_dir),
            "Artwork directory should still be created.",
        )
        self.assertEqual(
            len(os.listdir(samples_output_dir)), 0, "Samples directory should be empty."
        )
        self.assertEqual(
            len(os.listdir(artwork_output_dir)), 0, "Artwork directory should be empty."
        )


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
