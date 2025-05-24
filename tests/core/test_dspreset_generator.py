# pylint: disable=too-many-lines
"""
Unit tests for the DecentSamplerPresetGenerator class.

This module tests the creation of .dspreset files and associated directory
structures, including artwork and sample copying, and XML content generation.
"""

import os
import shutil
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock # patch is unused

from src.core.dspreset_generator import DecentSamplerPresetGenerator
from src.core.instrument_data import InstrumentData
from src.database.models import (
    Project as ProjectModel,
    Recording as RecordingModel,
    Sample as SampleModel,
    SampleMappingItem as SampleMappingItemModel
)

# This test class sets up many instance attributes for test data and mocks.
# pylint: disable=too-many-instance-attributes
class TestDecentSamplerPresetGenerator(unittest.TestCase):
    """
    Test suite for the DecentSamplerPresetGenerator class.
    """

    def setUp(self):
        """
        Set up test fixtures and mock data before each test method.
        This includes creating temporary directories for test outputs and
        dummy files for artwork and samples.
        """
        self.test_output_base_dir = "temp_test_output_dspreset"
        if os.path.exists(self.test_output_base_dir):
            shutil.rmtree(self.test_output_base_dir)
        os.makedirs(self.test_output_base_dir, exist_ok=True)

        # Mock database models
        self.mock_project_model = ProjectModel(id=1, name="Test Project")
        self.mock_recording_model = RecordingModel(
            id=1, project_id=1, name="Test Recording", samples=[]
        )
        self.mock_project_model.recordings = [self.mock_recording_model]

        # Mock Project object that the generator will use
        self.mock_project = MagicMock()
        self.mock_project.project_id = 1
        self.mock_project.project_model = self.mock_project_model

        # InstrumentData for the generator
        self.instrument_data = InstrumentData(
            name="My Test Instrument", author="Tester"
        )

        # Setup dummy directories for source files
        self.dummy_artwork_src_dir = os.path.join(
            self.test_output_base_dir, "dummy_source_artwork"
        )
        self.dummy_samples_src_dir = os.path.join(
            self.test_output_base_dir, "dummy_source_samples"
        )
        os.makedirs(self.dummy_artwork_src_dir, exist_ok=True)
        os.makedirs(self.dummy_samples_src_dir, exist_ok=True)

        # Create a dummy background image file
        self.dummy_bg_image_path = os.path.join(
            self.dummy_artwork_src_dir, "background.png"
        )
        with open(self.dummy_bg_image_path, "w", encoding="utf-8") as f:
            f.write("dummy_image_content")
        self.instrument_data.ui_background_image_path = self.dummy_bg_image_path

        # Create dummy sample audio files
        self.dummy_sample1_path = os.path.join(self.dummy_samples_src_dir, "s1.wav")
        self.dummy_sample2_path = os.path.join(self.dummy_samples_src_dir, "s2.wav")
        with open(self.dummy_sample1_path, "w", encoding="utf-8") as f:
            f.write("s1_content")
        with open(self.dummy_sample2_path, "w", encoding="utf-8") as f:
            f.write("s2_content")

    def tearDown(self):
        """
        Clean up test fixtures after each test method.
        This primarily involves removing the temporary output directory.
        """
        if os.path.exists(self.test_output_base_dir):
            shutil.rmtree(self.test_output_base_dir)

    def test_directory_and_dspreset_creation(self):
        """
        Test creation of the main instrument directory, essential subdirectories
        (Samples, Artwork), and the .dspreset file itself.
        """
        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, self.test_output_base_dir
        )
        generator.generate_preset()

        instrument_name_fs = self.instrument_data.name.replace(" ", "_").lower()
        expected_instrument_dir = os.path.join(
            self.test_output_base_dir, instrument_name_fs
        )
        dspreset_filename = f"{instrument_name_fs}.dspreset"

        self.assertTrue(os.path.isdir(expected_instrument_dir),
                        "Instrument directory should be created.")
        self.assertTrue(os.path.isdir(os.path.join(expected_instrument_dir, "Samples")),
                        "Samples subdirectory should be created.")
        self.assertTrue(os.path.isdir(os.path.join(expected_instrument_dir, "Artwork")),
                        "Artwork subdirectory should be created.")
        self.assertTrue(os.path.isfile(os.path.join(expected_instrument_dir, dspreset_filename)),
                        f"{dspreset_filename} file should be created.")

    def test_artwork_copying_and_xml(self):
        """
        Test that artwork (UI background image) is correctly copied to the
        Artwork subdirectory and referenced with a relative path in the XML.
        """
        self.instrument_data.ui_background_image_path = self.dummy_bg_image_path

        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, self.test_output_base_dir
        )
        generator.generate_preset()

        instrument_name_fs = self.instrument_data.name.replace(" ", "_").lower()
        artwork_file_basename = os.path.basename(self.dummy_bg_image_path) # More concise
        expected_artwork_dest_path = os.path.join(
            self.test_output_base_dir,
            instrument_name_fs,
            "Artwork",
            artwork_file_basename
        )
        self.assertTrue(
            os.path.isfile(expected_artwork_dest_path),
            "Artwork file was not copied to the Artwork subdirectory."
        )

        dspreset_path = os.path.join(
            self.test_output_base_dir,
            instrument_name_fs,
            f"{instrument_name_fs}.dspreset"
        )
        tree = ET.parse(dspreset_path)
        root = tree.getroot()

        ui_element = root.find("ui")
        self.assertIsNotNone(ui_element, "<ui> element not found in XML.")
        
        background_element = ui_element.find("tab/background")
        self.assertIsNotNone(background_element,
                             "<background> element not found in XML ui/tab.")
        self.assertEqual(background_element.get("image"),
                         os.path.join("Artwork", artwork_file_basename),
                         "Background image path in XML is incorrect.")

    def test_sample_copying_and_xml(self):
        """
        Test that sample audio files are copied to the Samples subdirectory
        and that the .dspreset XML correctly references them with appropriate
        MIDI note, key range, and velocity range attributes.
        """
        sample1_model = SampleModel(
            id=1, recording_id=1, name="s1.wav",
            file_path=self.dummy_sample1_path, midi_pitch=60, sample_mapping_items=[]
        )
        mapping_item1 = SampleMappingItemModel(
            id=1, sample_id=1, key_range_start=58, key_range_end=62
        )
        sample1_model.sample_mapping_items = [mapping_item1]
        self.mock_recording_model.samples = [sample1_model]

        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, self.test_output_base_dir
        )
        generator.generate_preset()

        instrument_name_fs = self.instrument_data.name.replace(" ", "_").lower()
        sample_file_basename = os.path.basename(self.dummy_sample1_path) # More concise
        expected_sample_dest_path = os.path.join(
            self.test_output_base_dir,
            instrument_name_fs,
            "Samples",
            sample_file_basename
        )
        self.assertTrue(
            os.path.isfile(expected_sample_dest_path),
            f"Sample file {sample_file_basename} was not copied."
        )

        dspreset_path = os.path.join(
            self.test_output_base_dir,
            instrument_name_fs,
            f"{instrument_name_fs}.dspreset"
        )
        tree = ET.parse(dspreset_path)
        root = tree.getroot()

        sample_element = root.find("groups/group/sample")
        self.assertIsNotNone(sample_element, "<sample> element not found in XML.")
        self.assertEqual(sample_element.get("path"),
                         os.path.join("Samples", sample_file_basename))
        self.assertEqual(sample_element.get("rootNote"), "60")
        self.assertEqual(sample_element.get("loKey"), "58")
        self.assertEqual(sample_element.get("hiKey"), "62")
        self.assertEqual(sample_element.get("loVel"), "0")
        self.assertEqual(sample_element.get("hiVel"), "127")

    def test_sample_copying_xml_default_keyrange(self):
        """
        Test sample XML generation when a sample has no explicit key range defined.
        In this case, loKey and hiKey should default to the sample's rootNote.
        """
        sample_file_basename = os.path.basename(self.dummy_sample2_path) # More concise
        sample2_model = SampleModel(
            id=2, recording_id=1, name=sample_file_basename, # Use basename for name too
            file_path=self.dummy_sample2_path, midi_pitch=72, sample_mapping_items=[]
        )
        self.mock_recording_model.samples = [sample2_model]

        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, self.test_output_base_dir
        )
        generator.generate_preset()

        instrument_name_fs = self.instrument_data.name.replace(" ", "_").lower()
        dspreset_path = os.path.join(
            self.test_output_base_dir,
            instrument_name_fs,
            f"{instrument_name_fs}.dspreset"
        )
        tree = ET.parse(dspreset_path)
        root = tree.getroot()
        
        sample_element = root.find("groups/group/sample")
        self.assertIsNotNone(sample_element,
                             "<sample> element missing (default keyrange test).")
        self.assertEqual(sample_element.get("path"),
                         os.path.join("Samples", sample_file_basename))
        self.assertEqual(sample_element.get("rootNote"), "72")
        self.assertEqual(sample_element.get("loKey"), "72",
                         "loKey should default to rootNote.")
        self.assertEqual(sample_element.get("hiKey"), "72",
                         "hiKey should default to rootNote.")

    def test_xml_root_and_basic_structure(self):
        """
        Test the root <DecentSampler> element and presence of essential child
        elements (ui, groups, effects) in the .dspreset XML.
        """
        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, self.test_output_base_dir
        )
        generator.generate_preset()

        instrument_name_fs = self.instrument_data.name.replace(" ", "_").lower()
        dspreset_path = os.path.join(
            self.test_output_base_dir, instrument_name_fs, f"{instrument_name_fs}.dspreset"
        )
        
        self.assertTrue(os.path.isfile(dspreset_path),
                        f".dspreset file not found at {dspreset_path}")
        
        tree = ET.parse(dspreset_path)
        root = tree.getroot()

        self.assertEqual(root.tag, "DecentSampler", "Root XML tag is not 'DecentSampler'.")
        self.assertEqual(root.get("minVersion"), "1.0.0", "'minVersion' attribute incorrect.")
        self.assertIsNotNone(root.find("ui"), "<ui> element not found.")
        self.assertIsNotNone(root.find("groups"), "<groups> element not found.")
        self.assertIsNotNone(root.find("effects"), "<effects> element not found.")

    def test_empty_project_no_samples_no_artwork(self):
        """
        Test preset generation for an empty project (no recordings/samples)
        and no UI artwork. Ensures a valid, minimal .dspreset file is created
        and directories are present but empty.
        """
        self.mock_project_model.recordings = []  # No recordings
        self.instrument_data.ui_background_image_path = None # No artwork

        generator = DecentSamplerPresetGenerator(
            self.mock_project, self.instrument_data, self.test_output_base_dir
        )
        generator.generate_preset()

        instrument_name_fs = self.instrument_data.name.replace(" ", "_").lower()
        expected_instrument_dir = os.path.join(
            self.test_output_base_dir, instrument_name_fs
        )
        dspreset_path = os.path.join(
            expected_instrument_dir, f"{instrument_name_fs}.dspreset"
        )

        self.assertTrue(os.path.isfile(dspreset_path),
                        ".dspreset file not created for empty project.")

        tree = ET.parse(dspreset_path)
        root = tree.getroot()

        groups_element = root.find("groups")
        self.assertIsNotNone(groups_element, "<groups> element should exist even if empty.")
        self.assertEqual(len(list(groups_element)), 0,
                         "<groups> element should have no child <group> tags.")

        ui_element = root.find("ui")
        self.assertIsNotNone(ui_element, "<ui> element should exist.")
        self.assertIsNone(ui_element.find("tab/background"),
                          "<background> element should not exist if no UI image is specified.")
        
        samples_output_dir = os.path.join(expected_instrument_dir, "Samples")
        artwork_output_dir = os.path.join(expected_instrument_dir, "Artwork")
        self.assertTrue(os.path.isdir(samples_output_dir),
                        "Samples directory should still be created.")
        self.assertTrue(os.path.isdir(artwork_output_dir),
                        "Artwork directory should still be created.")
        self.assertEqual(len(os.listdir(samples_output_dir)), 0,
                         "Samples directory should be empty.")
        self.assertEqual(len(os.listdir(artwork_output_dir)), 0,
                         "Artwork directory should be empty.")

if __name__ == '__main__':
    # This allows running the tests with `python path/to/this_file.py`
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
