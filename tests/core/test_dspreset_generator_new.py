import os
import shutil
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock, call, mock_open, ANY
import tempfile

# Import the class to be tested
from src.core.dspreset_generator import DecentSamplerPresetGenerator

# Import InstrumentData if it's a concrete class and can be instantiated
from src.core.instrument_data import InstrumentData

# For mocking database models, we'll create MagicMock instances directly
# instead of trying to import potentially complex SQLAlchemy models.


class TestDecentSamplerPresetGeneratorNew(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for test outputs
        self.test_output_dir = tempfile.TemporaryDirectory()
        self.output_base_dir = self.test_output_dir.name

        # --- Mock Project and its underlying models ---
        self.mock_project_model = MagicMock(name="ProjectModel")
        self.mock_project_model.name = "TestProject"
        # self.mock_project_model.recordings should be set per test case
        # Example: self.mock_project_model.recordings = [self.mock_recording_model_1]

        self.mock_project = MagicMock(name="Project")
        self.mock_project.project_model = self.mock_project_model
        self.mock_project.project_id = 1  # Add a project_id for completeness

        # --- Mock InstrumentData ---
        # Using a real InstrumentData object if it's simple, otherwise mock it.
        # For this example, let's assume InstrumentData can be instantiated.
        self.instrument_data = InstrumentData(
            name="TestInstrument",
            author="TestAuthor",
            website="http://example.com",
            version="1.0.1",
            ui_background_image_path=None,  # Default to no image
        )
        # If InstrumentData were complex or had dependencies, we'd do:
        # self.mock_instrument_data = MagicMock(spec=InstrumentData)
        # self.mock_instrument_data.name = "TestInstrument"
        # ... and so on for other attributes

        # Instantiate the generator
        self.generator = DecentSamplerPresetGenerator(
            project=self.mock_project,
            instrument_data=self.instrument_data,  # or self.mock_instrument_data
            output_base_dir=self.output_base_dir,
        )

        # --- Mock individual RecordingModel, SampleModel, SampleMappingItemModel ---
        # These will be configured within specific tests that need them.
        self.mock_recording_model_1 = MagicMock(name="RecordingModel1")
        self.mock_recording_model_1.name = "Piano Recording"
        self.mock_recording_model_1.samples = []  # Default to no samples for a recording

        self.mock_sample_model_1 = MagicMock(name="SampleModel1")
        self.mock_sample_model_1.file_path = "/path/to/sample1.wav"
        self.mock_sample_model_1.midi_pitch = 60  # C4
        self.mock_sample_model_1.sample_mapping_items = []  # Default

        self.mock_sample_mapping_item_1 = MagicMock(name="SampleMappingItemModel1")
        self.mock_sample_mapping_item_1.key_range_start = 60
        self.mock_sample_mapping_item_1.key_range_end = 60
        # self.mock_sample_mapping_item_1.velocity_range_start = 0 # Not used by current generator
        # self.mock_sample_mapping_item_1.velocity_range_end = 127 # Not used by current generator

    def tearDown(self):
        # Clean up the temporary directory
        self.test_output_dir.cleanup()
        # Stop any patches if they were started in setUp or tests directly
        patch.stopall()

    def test_sanitize_filename(self):
        # Test cases for _sanitize_filename
        self.assertEqual(
            self.generator._sanitize_filename("My Instrument Name"), "my_instrument_name"
        )
        self.assertEqual(
            self.generator._sanitize_filename("MY_UPPER_CASE_NAME"), "my_upper_case_name"
        )
        self.assertEqual(
            self.generator._sanitize_filename("already_sanitized"), "already_sanitized"
        )
        # Current implementation of _sanitize_filename is very simple:
        # name.replace(" ", "_").lower()
        # It does not remove special characters other than spaces.
        self.assertEqual(
            self.generator._sanitize_filename("name with-hyphens_and_underscores"),
            "name_with-hyphens_and_underscores",
        )
        self.assertEqual(
            self.generator._sanitize_filename("Name With Numbers 123"), "name_with_numbers_123"
        )
        self.assertEqual(
            self.generator._sanitize_filename(" Special Chars!@#$ "), "_special_chars!@#$_"
        )  # Corrected: added trailing underscore

    # Placeholder for the first complex test for generate_preset
    @patch("os.makedirs")
    @patch("shutil.copy2")
    @patch("xml.etree.ElementTree.ElementTree.write")
    @patch("os.path.exists", return_value=True)
    def test_generate_preset_successful_basic_structure(
        self, mock_exists, mock_xml_write, mock_copy, mock_makedirs
    ):
        # This test primarily checks that the main OS operations and XML write are called.
        # Detailed XML content is for other tests.

        # Configure mock project data for this test
        self.mock_sample_model_1.sample_mapping_items = [self.mock_sample_mapping_item_1]
        self.mock_recording_model_1.samples = [self.mock_sample_model_1]
        self.mock_project.project_model.recordings = [self.mock_recording_model_1]
        self.instrument_data.ui_background_image_path = "/path/to/artwork.jpg"

        # Call the method under test
        self.generator.generate_preset()

        # Assertions for directory creation
        sanitized_instrument_name = self.generator._sanitize_filename(
            self.instrument_data.name
        )
        expected_instrument_dir = os.path.join(self.output_base_dir, sanitized_instrument_name)
        expected_samples_dir = os.path.join(expected_instrument_dir, "Samples")
        expected_artwork_dir = os.path.join(expected_instrument_dir, "Artwork")

        mock_makedirs.assert_any_call(expected_instrument_dir, exist_ok=True)
        mock_makedirs.assert_any_call(expected_samples_dir, exist_ok=True)
        mock_makedirs.assert_any_call(expected_artwork_dir, exist_ok=True)

        # Assertions for file copying (artwork and samples)
        # Artwork
        artwork_filename = os.path.basename(self.instrument_data.ui_background_image_path)
        expected_dest_artwork_path = os.path.join(expected_artwork_dir, artwork_filename)
        mock_copy.assert_any_call(
            self.instrument_data.ui_background_image_path, expected_dest_artwork_path
        )

        # Sample
        sample_filename = os.path.basename(self.mock_sample_model_1.file_path)
        expected_dest_sample_path = os.path.join(expected_samples_dir, sample_filename)
        mock_copy.assert_any_call(
            self.mock_sample_model_1.file_path, expected_dest_sample_path
        )

        # Assertion for XML file writing
        expected_dspreset_filename = sanitized_instrument_name + ".dspreset"
        expected_dspreset_path = os.path.join(
            expected_instrument_dir, expected_dspreset_filename
        )
        # The mocked write method receives the path as its first argument if called as tree.write(path, ...)
        # and tree is an instance of a class where 'write' is a method.
        # The error message "Actual: write('/tmp/tmpxg6dywul/testinstrument/testinstrument.dspreset', ...)"
        # indicates the first argument seen by the mock IS the path.
        mock_xml_write.assert_called_once_with(
            expected_dspreset_path, encoding="UTF-8", xml_declaration=True
        )

    @patch("xml.etree.ElementTree.ElementTree")  # Mock the class constructor
    @patch("os.makedirs")
    @patch("shutil.copy2")
    @patch("os.path.exists", return_value=True)
    def test_generate_preset_xml_content_detailed(
        self, mock_exists, mock_copy, mock_makedirs, mock_ET_ElementTree_class
    ):
        # Configure mock project data
        self.mock_sample_mapping_item_1.key_range_start = 50
        self.mock_sample_mapping_item_1.key_range_end = 55
        self.mock_sample_model_1.sample_mapping_items = [self.mock_sample_mapping_item_1]
        self.mock_sample_model_1.midi_pitch = 52  # Within the key range
        self.mock_sample_model_1.file_path = "samples_for_test/sample1.wav"

        mock_sample_model_2 = MagicMock(name="SampleModel2")
        mock_sample_model_2.file_path = "samples_for_test/sample2.flac"
        mock_sample_model_2.midi_pitch = 70
        mock_sample_mapping_item_2 = MagicMock(name="SampleMappingItemModel2")
        mock_sample_mapping_item_2.key_range_start = 68
        mock_sample_mapping_item_2.key_range_end = 72
        mock_sample_model_2.sample_mapping_items = [mock_sample_mapping_item_2]

        self.mock_recording_model_1.samples = [self.mock_sample_model_1, mock_sample_model_2]
        self.mock_project.project_model.recordings = [self.mock_recording_model_1]
        self.instrument_data.ui_background_image_path = "artwork_files/background.png"
        self.instrument_data.version = "1.2.3"  # Test version attribute

        # Configure the mock for ET.ElementTree() constructor to return a mock tree instance
        mock_tree_instance = MagicMock(name="MockTreeInstance")
        mock_ET_ElementTree_class.return_value = mock_tree_instance

        # Call the method under test
        self.generator.generate_preset()

        # Capture the root ET.Element passed to the ET.ElementTree constructor
        self.assertTrue(
            mock_ET_ElementTree_class.called, "ET.ElementTree constructor was not called."
        )
        constructor_args, _ = mock_ET_ElementTree_class.call_args
        written_tree_root = constructor_args[0]

        # --- Verify XML structure ---
        self.assertEqual(written_tree_root.tag, "DecentSampler")
        self.assertEqual(written_tree_root.get("minVersion"), "1.0.0")
        self.assertEqual(written_tree_root.get("version"), "1.2.3")

        # UI Element
        ui_element = written_tree_root.find("ui")
        self.assertIsNotNone(ui_element)
        tab_element = ui_element.find("tab")
        self.assertIsNotNone(tab_element)
        self.assertEqual(tab_element.get("name"), "main")
        background_element = tab_element.find("background")
        self.assertIsNotNone(background_element)
        expected_artwork_path = os.path.join(
            "Artwork", os.path.basename(self.instrument_data.ui_background_image_path)
        )
        self.assertEqual(background_element.get("image"), expected_artwork_path)

        # Groups Element
        groups_element = written_tree_root.find("groups")
        self.assertIsNotNone(groups_element)

        group_elements = groups_element.findall("group")
        self.assertEqual(len(group_elements), 1)  # One recording
        group1 = group_elements[0]
        self.assertEqual(group1.get("name"), self.mock_recording_model_1.name)

        # Samples within the group
        sample_elements = group1.findall("sample")
        self.assertEqual(len(sample_elements), 2)  # Two samples in the recording

        # Sample 1 assertions
        sample1_xml = sample_elements[0]
        expected_sample1_path = os.path.join(
            "Samples", os.path.basename(self.mock_sample_model_1.file_path)
        )
        self.assertEqual(sample1_xml.get("path"), expected_sample1_path)
        self.assertEqual(sample1_xml.get("rootNote"), str(self.mock_sample_model_1.midi_pitch))
        self.assertEqual(
            sample1_xml.get("loKey"), str(self.mock_sample_mapping_item_1.key_range_start)
        )
        self.assertEqual(
            sample1_xml.get("hiKey"), str(self.mock_sample_mapping_item_1.key_range_end)
        )
        self.assertEqual(sample1_xml.get("loVel"), "0")  # Default
        self.assertEqual(sample1_xml.get("hiVel"), "127")  # Default

        # Sample 2 assertions
        sample2_xml = sample_elements[1]
        expected_sample2_path = os.path.join(
            "Samples", os.path.basename(mock_sample_model_2.file_path)
        )
        self.assertEqual(sample2_xml.get("path"), expected_sample2_path)
        self.assertEqual(sample2_xml.get("rootNote"), str(mock_sample_model_2.midi_pitch))
        self.assertEqual(
            sample2_xml.get("loKey"), str(mock_sample_mapping_item_2.key_range_start)
        )
        self.assertEqual(
            sample2_xml.get("hiKey"), str(mock_sample_mapping_item_2.key_range_end)
        )

        # Effects Element (should be present and empty by default)
        effects_element = written_tree_root.find("effects")
        self.assertIsNotNone(effects_element)
        self.assertEqual(len(list(effects_element)), 0)  # No child elements

        # Assert that the tree's write method was called correctly
        sanitized_instrument_name = self.generator._sanitize_filename(
            self.instrument_data.name
        )
        expected_instrument_dir = os.path.join(self.output_base_dir, sanitized_instrument_name)
        expected_dspreset_filename = sanitized_instrument_name + ".dspreset"
        expected_dspreset_path = os.path.join(
            expected_instrument_dir, expected_dspreset_filename
        )
        mock_tree_instance.write.assert_called_once_with(
            expected_dspreset_path, encoding="UTF-8", xml_declaration=True
        )

    @patch("xml.etree.ElementTree.ElementTree")
    @patch("os.makedirs")
    @patch("shutil.copy2")
    @patch("os.path.exists", return_value=True)
    def test_generate_preset_no_ui_background_image(
        self, mock_exists, mock_copy, mock_makedirs, mock_ET_ElementTree_class
    ):
        self.instrument_data.ui_background_image_path = None  # Ensure no image path

        mock_tree_instance = MagicMock(name="MockTreeInstance")
        mock_ET_ElementTree_class.return_value = mock_tree_instance

        # Minimal project data
        self.mock_project.project_model.recordings = []

        self.generator.generate_preset()

        # Check that copy2 was not called for artwork
        artwork_copy_called = False
        for call_item in mock_copy.call_args_list:
            args, _ = call_item
            if "Artwork" in args[1]:
                artwork_copy_called = True
                break
        self.assertFalse(
            artwork_copy_called,
            "shutil.copy2 should not be called for artwork if no path is provided.",
        )

        # Verify XML structure for UI
        self.assertTrue(mock_ET_ElementTree_class.called)
        constructor_args, _ = mock_ET_ElementTree_class.call_args
        written_tree_root = constructor_args[0]

        ui_element = written_tree_root.find("ui")
        self.assertIsNotNone(ui_element)
        tab_element = ui_element.find("tab")

        all_background_images = written_tree_root.findall(".//ui/tab/background[@image]")
        self.assertEqual(
            len(all_background_images), 0, "No background image attribute should be present."
        )
        if tab_element:  # Tab might still exist
            self.assertIsNone(
                tab_element.find("background"),
                "Background element itself should be absent or have no image attr.",
            )

    @patch("xml.etree.ElementTree.ElementTree")
    @patch("os.makedirs")
    @patch("shutil.copy2")
    @patch("os.path.exists", return_value=False)
    def test_generate_preset_no_recordings_or_samples(
        self, mock_exists, mock_copy, mock_makedirs, mock_ET_ElementTree_class
    ):
        self.mock_project.project_model.recordings = []
        self.instrument_data.ui_background_image_path = None

        mock_tree_instance = MagicMock(name="MockTreeInstance")
        mock_ET_ElementTree_class.return_value = mock_tree_instance

        with patch("builtins.print") as mock_print:
            self.generator.generate_preset()

        # Verify XML structure
        self.assertTrue(mock_ET_ElementTree_class.called)
        constructor_args, _ = mock_ET_ElementTree_class.call_args
        written_tree_root = constructor_args[0]

        groups_element = written_tree_root.find("groups")
        self.assertIsNotNone(groups_element)
        self.assertEqual(
            len(groups_element.findall("group")),
            0,
            "Groups element should be empty if no recordings.",
        )

        # Check print output for info message
        # This check depends on the exact message logged by the generator
        # For now, let's assume a general check. A more specific check might be needed.
        printed_output = "".join(str(call_arg) for call_arg in mock_print.call_args_list)
        self.assertIn(
            "No recordings found",
            printed_output,
            "Expected info message about no recordings not found in print output.",
        )

        mock_copy.assert_not_called()

    @patch("os.makedirs")
    @patch("shutil.copy2")
    @patch("xml.etree.ElementTree.ElementTree")  # Patching the class itself
    @patch("os.path.exists")  # Control existence of files
    @patch("builtins.print")  # To capture print output for warnings
    def test_generate_preset_missing_ui_background_image_file(
        self, mock_print, mock_exists, MockElementTree, mock_copy, mock_makedirs
    ):
        # InstrumentData specifies a UI image, but os.path.exists returns False for it
        self.instrument_data.ui_background_image_path = "/path/to/missing_artwork.jpg"

        # Configure os.path.exists: artwork missing, samples (if any) exist
        def side_effect_exists(path):
            if path == self.instrument_data.ui_background_image_path:
                return False  # Artwork is missing
            return True  # Other files (e.g. samples) exist

        mock_exists.side_effect = side_effect_exists

        # Minimal project data (no samples needed for this specific test focus)
        self.mock_project.project_model.recordings = []

        # Mock the ElementTree instance and its write method
        mock_tree_instance = MockElementTree.return_value

        self.generator.generate_preset()

        # Verify warning is printed for missing artwork
        self.assertTrue(
            any(
                f"WARNING: Artwork source file not found: {self.instrument_data.ui_background_image_path}"
                in str(call_args)
                for call_args in mock_print.call_args_list
            )
        )

        # Verify XML structure for UI (should not contain the background image)
        self.assertTrue(MockElementTree.called)
        args, _ = MockElementTree.call_args
        written_tree_root = args[0]  # The root ET.Element passed to ET.ElementTree()

        all_background_images = written_tree_root.findall(".//ui/tab/background[@image]")
        self.assertEqual(
            len(all_background_images),
            0,
            "No background image should be in XML if source file is missing.",
        )

        # Verify copy was not called for the missing artwork
        artwork_copy_called = False
        for call_item in mock_copy.call_args_list:
            args_copy, _ = call_item
            if args_copy[0] == self.instrument_data.ui_background_image_path:
                artwork_copy_called = True
                break
        self.assertFalse(
            artwork_copy_called, "shutil.copy2 should not be called for missing artwork."
        )

    @patch("os.makedirs")
    @patch("shutil.copy2")
    @patch("xml.etree.ElementTree.ElementTree")
    @patch("os.path.exists")
    @patch("builtins.print")
    def test_generate_preset_missing_sample_file(
        self, mock_print, mock_exists, MockElementTree, mock_copy, mock_makedirs
    ):
        # Configure a sample whose file is missing
        self.mock_sample_model_1.file_path = "/path/to/missing_sample.wav"
        self.mock_sample_model_1.sample_mapping_items = [self.mock_sample_mapping_item_1]
        self.mock_recording_model_1.samples = [self.mock_sample_model_1]
        self.mock_project.project_model.recordings = [self.mock_recording_model_1]
        self.instrument_data.ui_background_image_path = None  # No artwork for simplicity

        # os.path.exists: sample is missing
        def side_effect_exists(path):
            if path == self.mock_sample_model_1.file_path:
                return False
            return True  # Other files (e.g. artwork, other samples) might exist

        mock_exists.side_effect = side_effect_exists

        mock_tree_instance = MockElementTree.return_value

        self.generator.generate_preset()

        # Verify warning for missing sample
        self.assertTrue(
            any(
                f"WARNING: Sample source file not found, skipping: {self.mock_sample_model_1.file_path}"
                in str(call_args)
                for call_args in mock_print.call_args_list
            )
        )

        # Verify XML: the missing sample should not be included
        self.assertTrue(MockElementTree.called)
        args, _ = MockElementTree.call_args
        written_tree_root = args[0]

        sample_elements = written_tree_root.findall(".//group/sample")
        self.assertEqual(
            len(sample_elements),
            0,
            "No sample elements should be in XML if the source file is missing.",
        )

        # Verify copy was not called for the missing sample
        sample_copy_called = False
        for call_item in mock_copy.call_args_list:
            args_copy, _ = call_item
            if args_copy[0] == self.mock_sample_model_1.file_path:
                sample_copy_called = True
                break
        self.assertFalse(
            sample_copy_called, "shutil.copy2 should not be called for a missing sample file."
        )

    @patch("os.makedirs", side_effect=OSError("Test OSError"))
    @patch("shutil.copy2")
    @patch("xml.etree.ElementTree.ElementTree")
    @patch("os.path.exists", return_value=True)
    @patch("builtins.print")
    def test_generate_preset_oserror_on_makedirs(
        self, mock_print, mock_exists, MockElementTree, mock_copy, mock_makedirs_oserror
    ):
        self.generator.generate_preset()
        # Verify error message is printed
        self.assertTrue(
            any(
                "ERROR: Could not create instrument directories: Test OSError"
                in str(call_args)
                for call_args in mock_print.call_args_list
            )
        )
        # Verify that further operations like copying or XML writing are not attempted
        mock_copy.assert_not_called()
        MockElementTree.assert_not_called()  # ElementTree constructor shouldn't be called
        # Accessing MockElementTree.return_value.write would fail if MockElementTree itself wasn't called

    @patch("os.makedirs")
    @patch("shutil.copy2", side_effect=IOError("Test IOError on artwork copy"))
    @patch("xml.etree.ElementTree.ElementTree")
    @patch("os.path.exists", return_value=True)
    @patch("builtins.print")
    def test_generate_preset_ioerror_on_artwork_copy(
        self, mock_print, mock_exists, MockElementTree, mock_copy_ioerror, mock_makedirs
    ):
        self.instrument_data.ui_background_image_path = "/path/to/artwork.jpg"
        # Ensure project has at least one sample so that sample copying is also attempted,
        # to isolate that the error is from artwork copy
        self.mock_sample_model_1.sample_mapping_items = [self.mock_sample_mapping_item_1]
        self.mock_recording_model_1.samples = [self.mock_sample_model_1]
        self.mock_project.project_model.recordings = [self.mock_recording_model_1]

        mock_tree_instance = MockElementTree.return_value

        # Make shutil.copy2 raise IOError only for the artwork file
        def copy_side_effect(src, dst):
            if src == self.instrument_data.ui_background_image_path:
                raise IOError("Test IOError on artwork copy")
            # else: # Simulate successful copy for other files (samples)
            #   pass

        mock_copy_ioerror.side_effect = copy_side_effect

        self.generator.generate_preset()

        artwork_filename = os.path.basename(self.instrument_data.ui_background_image_path)
        self.assertTrue(
            any(
                f"ERROR: Could not copy artwork file {artwork_filename}: Test IOError on artwork copy"
                in str(call_args)
                for call_args in mock_print.call_args_list
            )
        )

        # XML should still be generated, but UI might be affected (no background image)
        self.assertTrue(MockElementTree.called)
        args, _ = MockElementTree.call_args
        written_tree_root = args[0]
        all_background_images = written_tree_root.findall(".//ui/tab/background[@image]")
        self.assertEqual(len(all_background_images), 0)  # No background if copy failed

        # Ensure sample was still copied (if mock_exists allows it)
        sample_path_to_check = self.mock_sample_model_1.file_path
        was_sample_copied = any(
            call_item.args[0] == sample_path_to_check
            for call_item in mock_copy_ioerror.call_args_list
            if call_item.args[0] != self.instrument_data.ui_background_image_path
        )  # Exclude the failing artwork call
        self.assertTrue(
            was_sample_copied,
            "Sample should still be attempted to be copied if artwork copy fails",
        )

    @patch("os.makedirs")
    @patch("shutil.copy2")  # This will be mocked with a side_effect
    @patch("xml.etree.ElementTree.ElementTree")
    @patch("os.path.exists", return_value=True)  # Assume all files exist initially
    @patch("builtins.print")
    def test_generate_preset_ioerror_on_sample_copy(
        self, mock_print, mock_exists, MockElementTree, mock_copy, mock_makedirs
    ):
        # Setup: one sample that will fail to copy, one that will succeed
        failing_sample_path = "/path/to/failing_sample.wav"
        mock_failing_sample = MagicMock(name="FailingSampleModel")
        mock_failing_sample.file_path = failing_sample_path
        mock_failing_sample.midi_pitch = 60
        mock_failing_sample.sample_mapping_items = [
            self.mock_sample_mapping_item_1
        ]  # Reuse mapping

        successful_sample_path = self.mock_sample_model_1.file_path  # from setUp
        self.mock_sample_model_1.sample_mapping_items = [
            self.mock_sample_mapping_item_1
        ]  # Reuse

        self.mock_recording_model_1.samples = [mock_failing_sample, self.mock_sample_model_1]
        self.mock_project.project_model.recordings = [self.mock_recording_model_1]
        self.instrument_data.ui_background_image_path = None  # No artwork for simplicity

        # shutil.copy2 side effect: raise IOError for the failing sample
        def copy_side_effect(src, dst):
            if src == failing_sample_path:
                raise IOError("Test IOError on sample copy")
            # else: pass # Successful copy for other files

        mock_copy.side_effect = copy_side_effect

        mock_tree_instance = MockElementTree.return_value

        self.generator.generate_preset()

        failing_sample_filename = os.path.basename(failing_sample_path)
        self.assertTrue(
            any(
                f"ERROR: Could not copy sample file {failing_sample_filename}: Test IOError on sample copy"
                in str(call_args)
                for call_args in mock_print.call_args_list
            )
        )

        # XML: failing sample should be skipped, successful one included
        self.assertTrue(MockElementTree.called)
        args, _ = MockElementTree.call_args
        written_tree_root = args[0]

        sample_elements = written_tree_root.findall(".//group/sample")
        self.assertEqual(len(sample_elements), 1)
        if len(sample_elements) == 1:
            successful_sample_filename = os.path.basename(successful_sample_path)
            expected_xml_path = os.path.join("Samples", successful_sample_filename)
            self.assertEqual(sample_elements[0].get("path"), expected_xml_path)

    @patch("os.makedirs")
    @patch("shutil.copy2")
    @patch("xml.etree.ElementTree.ElementTree")  # Patching the class
    @patch("os.path.exists", return_value=True)
    @patch("builtins.print")
    def test_generate_preset_ioerror_on_xml_write(
        self, mock_print, mock_exists, MockElementTree, mock_copy, mock_makedirs
    ):
        # Setup ElementTree instance mock to raise IOError on write
        mock_tree_instance = MockElementTree.return_value
        mock_tree_instance.write.side_effect = IOError("Test IOError on XML write")

        # Minimal project data
        self.mock_project.project_model.recordings = []
        self.instrument_data.ui_background_image_path = None

        self.generator.generate_preset()

        self.assertTrue(
            any(
                "ERROR: Could not write .dspreset file: Test IOError on XML write"
                in str(call_args)
                for call_args in mock_print.call_args_list
            )
        )
        # Ensure that directory creation and file copying (if any) were attempted
        mock_makedirs.assert_called()  # At least instrument dir
        # mock_copy might or might not be called depending on if there was artwork/samples
        # For this specific minimal setup, it's not called.
        mock_copy.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
