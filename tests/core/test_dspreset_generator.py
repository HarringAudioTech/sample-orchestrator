import unittest
import os
import shutil
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from src.core.dspreset_generator import DecentSamplerPresetGenerator
from src.core.instrument_data import InstrumentData
from src.database.models import (
    Project as ProjectModel,
    Recording as RecordingModel,
    Sample as SampleModel,
    SampleMappingItem as SampleMappingItemModel
)

class TestDecentSamplerPresetGenerator(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_output_base_dir = "temp_test_output_dspreset"
        # Clean up any previous test runs
        if os.path.exists(self.test_output_base_dir):
            shutil.rmtree(self.test_output_base_dir)
        os.makedirs(self.test_output_base_dir, exist_ok=True)

        # Mock database models
        self.mock_project_model = ProjectModel(id=1, name="Test Project")
        self.mock_recording_model = RecordingModel(id=1, project_id=1, name="Test Recording", samples=[])
        self.mock_project_model.recordings = [self.mock_recording_model]

        # Mock Project object
        self.mock_project = MagicMock()
        self.mock_project.project_id = 1
        self.mock_project.project_model = self.mock_project_model

        # InstrumentData
        self.instrument_data = InstrumentData(name="My Test Instrument", author="Tester")

        # Dummy source files directories
        self.dummy_artwork_src_dir = os.path.join(self.test_output_base_dir, "dummy_source_artwork")
        self.dummy_samples_src_dir = os.path.join(self.test_output_base_dir, "dummy_source_samples")
        os.makedirs(self.dummy_artwork_src_dir, exist_ok=True)
        os.makedirs(self.dummy_samples_src_dir, exist_ok=True)

        # Dummy background image
        self.dummy_bg_image_path = os.path.join(self.dummy_artwork_src_dir, "background.png")
        with open(self.dummy_bg_image_path, "w") as f:
            f.write("dummy_image_content")
        self.instrument_data.ui_background_image_path = self.dummy_bg_image_path

        # Dummy sample files (will be created specifically in relevant tests if needed)
        self.dummy_sample1_path = os.path.join(self.dummy_samples_src_dir, "s1.wav")
        self.dummy_sample2_path = os.path.join(self.dummy_samples_src_dir, "s2.wav")
        with open(self.dummy_sample1_path, "w") as f: # Create one for general use
            f.write("s1_content")
        with open(self.dummy_sample2_path, "w") as f:
            f.write("s2_content")


    def tearDown(self):
        """Clean up test fixtures after each test method."""
        if os.path.exists(self.test_output_base_dir):
            shutil.rmtree(self.test_output_base_dir)

    def test_directory_and_dspreset_creation(self):
        """Test creation of main instrument directory, subdirectories, and .dspreset file."""
        generator = DecentSamplerPresetGenerator(self.mock_project, self.instrument_data, self.test_output_base_dir)
        generator.generate_preset()

        instrument_name_fs = self.instrument_data.name.replace(" ", "_").lower()
        expected_instrument_dir = os.path.join(self.test_output_base_dir, instrument_name_fs)

        self.assertTrue(os.path.isdir(expected_instrument_dir), "Instrument directory not created.")
        self.assertTrue(os.path.isdir(os.path.join(expected_instrument_dir, "Samples")), "Samples directory not created.")
        self.assertTrue(os.path.isdir(os.path.join(expected_instrument_dir, "Artwork")), "Artwork directory not created.")
        self.assertTrue(os.path.isfile(os.path.join(expected_instrument_dir, instrument_name_fs + ".dspreset")),
                        ".dspreset file not created.")

    def test_artwork_copying_and_xml(self):
        """Test that artwork is copied and XML correctly references it."""
        self.instrument_data.ui_background_image_path = self.dummy_bg_image_path # Ensure it's set

        generator = DecentSamplerPresetGenerator(self.mock_project, self.instrument_data, self.test_output_base_dir)
        generator.generate_preset()

        instrument_name_fs = self.instrument_data.name.replace(" ", "_").lower()
        expected_artwork_file = os.path.join(self.test_output_base_dir, instrument_name_fs, "Artwork", "background.png")
        self.assertTrue(os.path.isfile(expected_artwork_file), "Artwork file not copied.")

        dspreset_path = os.path.join(self.test_output_base_dir, instrument_name_fs, instrument_name_fs + ".dspreset")
        tree = ET.parse(dspreset_path)
        root = tree.getroot()

        ui_element = root.find("ui")
        self.assertIsNotNone(ui_element, "UI element not found in XML.")
        
        # Decent Sampler UI structure can be <ui><tab name="main"><background image="..."/></tab></ui>
        # or <ui><background image="..."/></ui> if no tabs. The generator creates a "main" tab.
        background_element = ui_element.find("tab/background")
        self.assertIsNotNone(background_element, "Background element not found in XML ui/tab.")
        self.assertEqual(background_element.get("image"), os.path.join("Artwork", "background.png"),
                         "Background image path in XML is incorrect.")

    def test_sample_copying_and_xml(self):
        """Test that samples are copied and XML correctly references them."""
        # Create specific sample model for this test
        sample1_model = SampleModel(id=1, recording_id=1, name="s1.wav", file_path=self.dummy_sample1_path, midi_pitch=60, sample_mapping_items=[])
        
        # Create a sample mapping item for key range testing
        mapping_item1 = SampleMappingItemModel(id=1, sample_id=1, key_range_start=58, key_range_end=62)
        sample1_model.sample_mapping_items = [mapping_item1]
        
        self.mock_recording_model.samples = [sample1_model]

        generator = DecentSamplerPresetGenerator(self.mock_project, self.instrument_data, self.test_output_base_dir)
        generator.generate_preset()

        instrument_name_fs = self.instrument_data.name.replace(" ", "_").lower()
        expected_sample_file = os.path.join(self.test_output_base_dir, instrument_name_fs, "Samples", "s1.wav")
        self.assertTrue(os.path.isfile(expected_sample_file), "Sample file s1.wav not copied.")

        dspreset_path = os.path.join(self.test_output_base_dir, instrument_name_fs, instrument_name_fs + ".dspreset")
        tree = ET.parse(dspreset_path)
        root = tree.getroot()

        sample_element = root.find("groups/group/sample")
        self.assertIsNotNone(sample_element, "Sample element not found in XML.")
        self.assertEqual(sample_element.get("path"), os.path.join("Samples", "s1.wav"), "Sample path in XML is incorrect.")
        self.assertEqual(sample_element.get("rootNote"), "60", "Sample rootNote in XML is incorrect.")
        self.assertEqual(sample_element.get("loKey"), "58", "Sample loKey in XML is incorrect.")
        self.assertEqual(sample_element.get("hiKey"), "62", "Sample hiKey in XML is incorrect.")
        self.assertEqual(sample_element.get("loVel"), "0", "Sample loVel in XML is incorrect (default).")
        self.assertEqual(sample_element.get("hiVel"), "127", "Sample hiVel in XML is incorrect (default).")


    def test_sample_copying_xml_default_keyrange(self):
        """Test sample XML when no explicit key range is defined (defaults to rootNote)."""
        sample2_model = SampleModel(id=2, recording_id=1, name="s2.wav", file_path=self.dummy_sample2_path, midi_pitch=72, sample_mapping_items=[])
        # No SampleMappingItemModel for sample2_model, so key ranges should default to rootNote
        self.mock_recording_model.samples = [sample2_model]

        generator = DecentSamplerPresetGenerator(self.mock_project, self.instrument_data, self.test_output_base_dir)
        generator.generate_preset()

        instrument_name_fs = self.instrument_data.name.replace(" ", "_").lower()
        dspreset_path = os.path.join(self.test_output_base_dir, instrument_name_fs, instrument_name_fs + ".dspreset")
        tree = ET.parse(dspreset_path)
        root = tree.getroot()
        
        sample_element = root.find("groups/group/sample")
        self.assertIsNotNone(sample_element, "Sample element not found in XML for default keyrange test.")
        self.assertEqual(sample_element.get("path"), os.path.join("Samples", "s2.wav"))
        self.assertEqual(sample_element.get("rootNote"), "72")
        self.assertEqual(sample_element.get("loKey"), "72", "loKey should default to rootNote.")
        self.assertEqual(sample_element.get("hiKey"), "72", "hiKey should default to rootNote.")


    def test_xml_root_and_basic_structure(self):
        """Test the root element and basic structure of the .dspreset XML."""
        generator = DecentSamplerPresetGenerator(self.mock_project, self.instrument_data, self.test_output_base_dir)
        generator.generate_preset()

        instrument_name_fs = self.instrument_data.name.replace(" ", "_").lower()
        dspreset_path = os.path.join(self.test_output_base_dir, instrument_name_fs, instrument_name_fs + ".dspreset")
        
        self.assertTrue(os.path.isfile(dspreset_path), f".dspreset file not found at {dspreset_path}")
        
        tree = ET.parse(dspreset_path)
        root = tree.getroot()

        self.assertEqual(root.tag, "DecentSampler", "Root XML tag is not DecentSampler.")
        self.assertEqual(root.get("minVersion"), "1.0.0", "minVersion attribute is incorrect.")
        self.assertIsNotNone(root.find("ui"), "UI element not found.")
        self.assertIsNotNone(root.find("groups"), "Groups element not found.")
        self.assertIsNotNone(root.find("effects"), "Effects element not found.")

    def test_empty_project_no_samples_no_artwork(self):
        """Test behavior with an empty project (no recordings/samples) and no artwork."""
        self.mock_project_model.recordings = []  # No recordings
        self.instrument_data.ui_background_image_path = None # No artwork

        generator = DecentSamplerPresetGenerator(self.mock_project, self.instrument_data, self.test_output_base_dir)
        generator.generate_preset()

        instrument_name_fs = self.instrument_data.name.replace(" ", "_").lower()
        expected_instrument_dir = os.path.join(self.test_output_base_dir, instrument_name_fs)
        dspreset_path = os.path.join(expected_instrument_dir, instrument_name_fs + ".dspreset")

        self.assertTrue(os.path.isfile(dspreset_path), ".dspreset file not created for empty project.")

        tree = ET.parse(dspreset_path)
        root = tree.getroot()

        groups_element = root.find("groups")
        self.assertIsNotNone(groups_element, "Groups element should exist even if empty.")
        self.assertEqual(len(list(groups_element)), 0, "Groups element should have no children (groups).")

        ui_element = root.find("ui")
        self.assertIsNotNone(ui_element, "UI element should exist.")
        # Check that no background tab was created
        self.assertIsNone(ui_element.find("tab/background"), "Background element should not exist if no image path.")
        
        # Check that Samples and Artwork directories are empty
        samples_output_dir = os.path.join(expected_instrument_dir, "Samples")
        artwork_output_dir = os.path.join(expected_instrument_dir, "Artwork")
        self.assertTrue(os.path.isdir(samples_output_dir), "Samples directory should still be created.")
        self.assertTrue(os.path.isdir(artwork_output_dir), "Artwork directory should still be created.")
        self.assertEqual(len(os.listdir(samples_output_dir)), 0, "Samples directory should be empty.")
        self.assertEqual(len(os.listdir(artwork_output_dir)), 0, "Artwork directory should be empty.")

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
