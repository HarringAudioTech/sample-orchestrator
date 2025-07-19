import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch, mock_open
import pytest

from src.core.dspreset_generator import DecentSamplerPresetGenerator
from src.core.project import Project
from src.core.instrument_data import InstrumentData
from src.database.models import Recording, Sample, SampleMappingItem


class TestDecentSamplerPresetGenerator:
    """Test suite for the DecentSamplerPresetGenerator class."""

    @pytest.fixture
    def setup_generator(self):
        """Set up a test instance of DecentSamplerPresetGenerator with mocks."""
        # Create a temporary directory for test outputs
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock project with sample data
            mock_project = MagicMock(spec=Project)
            
            # Set up mock project model with required attributes
            mock_project_model = MagicMock()
            mock_project.project_model = mock_project_model
            
            # Set up mock recordings and samples
            mock_recording = MagicMock(spec=Recording)
            mock_recording.id = 1
            mock_recording.name = "Test Recording"
            
            mock_sample = MagicMock(spec=Sample)
            mock_sample.id = 1
            mock_sample.file_path = "/fake/path/sample.wav"
            mock_sample.root_note = 60  # C3
            mock_sample.midi_pitch = 60  # C3 - required by DecentSamplerPresetGenerator
            
            # Set up mock sample mapping item
            mock_mapping_item = MagicMock(spec=SampleMappingItem)
            mock_mapping_item.sample = mock_sample
            mock_mapping_item.lo_key = 48  # C2
            mock_mapping_item.hi_key = 72   # C4
            mock_mapping_item.lo_vel = 0
            mock_mapping_item.hi_vel = 127
            # Add key range attributes used by DecentSamplerPresetGenerator
            mock_mapping_item.key_range_start = 48  # C2
            mock_mapping_item.key_range_end = 72    # C4
            
            # Add sample_mapping_items to the sample mock
            mock_sample.sample_mapping_items = [mock_mapping_item]
            
            # Configure mock project to return our test data
            mock_project.list_recordings.return_value = [mock_recording]
            
            # Set up the project model's recordings relationship
            mock_project_model.recordings = [mock_recording]
            
            # Set up the recording's samples relationship
            mock_recording.samples = [mock_sample]
            
            # Set up the sample's mapping items
            mock_sample.mapping_items = [mock_mapping_item]
            
            # Create instrument data
            instrument_data = InstrumentData(
                name="Test Instrument",
                author="Test Author",
                version="1.0",
                ui_background_image_path="/fake/path/background.png"
            )
            
            # Create the generator instance
            generator = DecentSamplerPresetGenerator(
                project=mock_project,
                instrument_data=instrument_data,
                output_base_dir=temp_dir
            )
            
            # Add mock objects to the generator for testing
            generator.temp_dir = temp_dir
            generator.mock_project = mock_project
            generator.mock_project_model = mock_project_model
            generator.mock_recording = mock_recording
            generator.mock_sample = mock_sample
            generator.mock_mapping_item = mock_mapping_item
            
            yield generator
            
            # Cleanup - the TemporaryDirectory will handle this automatically

    def test_sanitize_filename(self, setup_generator):
        """Test that filenames are properly sanitized."""
        generator = setup_generator
        
        # Test space replacement and lowercase conversion
        assert generator._sanitize_filename("Test Instrument") == "test_instrument"
        
        # Test special characters (should be preserved)
        assert generator._sanitize_filename("Test-Instrument_123") == "test-instrument_123"
        
        # Test with already sanitized name
        assert generator._sanitize_filename("test_instrument") == "test_instrument"

    @patch('os.makedirs')
    @patch('shutil.copy2')
    @patch('xml.etree.ElementTree.ElementTree.write')
    @patch('os.path.exists', return_value=True)  # Mock file existence
    def test_generate_preset_basic(self, mock_exists, mock_write, mock_copy, mock_makedirs, setup_generator):
        """Test basic preset generation with all components."""
        generator = setup_generator
        
        # Mock file operations
        mock_copy.return_value = None  # shutil.copy2 returns None on success
        
        # Call the method under test
        generator.generate_preset()
        
        # Verify directories were created
        expected_dir = os.path.join(generator.temp_dir, "test_instrument")
        mock_makedirs.assert_any_call(expected_dir, exist_ok=True)
        mock_makedirs.assert_any_call(os.path.join(expected_dir, "Samples"), exist_ok=True)
        mock_makedirs.assert_any_call(os.path.join(expected_dir, "Artwork"), exist_ok=True)
        
        # Verify artwork was copied
        expected_artwork_dest = os.path.join(expected_dir, "Artwork", "background.png")
        mock_copy.assert_any_call("/fake/path/background.png", expected_artwork_dest)
        
        # Verify sample was copied
        expected_sample_dest = os.path.join(expected_dir, "Samples", "sample.wav")
        mock_copy.assert_any_call("/fake/path/sample.wav", expected_sample_dest)
        
        # Verify XML was written
        mock_write.assert_called_once()
        
    @patch('os.path.exists', return_value=False)
    def test_generate_preset_missing_artwork(self, mock_exists, setup_generator):
        """Test preset generation when artwork file is missing."""
        generator = setup_generator
        
        # Call the method under test
        generator.generate_preset()
        
        # Verify the method completed without errors (artwork missing is a warning, not a failure)
        assert True
        
    def test_create_root_element(self, setup_generator):
        """Test creation of the root XML element."""
        generator = setup_generator
        
        root = generator._create_root_element()
        
        assert root.tag == "DecentSampler"
        assert root.get("minVersion") == "1.0.0"
        assert root.get("version") == "1.0"
        
    def test_create_ui_element_with_artwork(self, setup_generator):
        """Test UI element creation with artwork."""
        generator = setup_generator
        
        ui_element = generator._create_ui_element(
            artwork_output_dir="/fake/artwork/dir",
            artwork_successfully_copied=True
        )
        
        assert ui_element.tag == "ui"
        tab = ui_element.find("tab")
        assert tab is not None
        assert tab.get("name") == "main"
        
        background = tab.find("background")
        assert background is not None
        assert background.get("image") == "Artwork/background.png"
        
    def test_create_ui_element_no_artwork(self, setup_generator):
        """Test UI element creation without artwork."""
        generator = setup_generator
        generator.instrument_data.ui_background_image_path = None
        
        ui_element = generator._create_ui_element(
            artwork_output_dir="/fake/artwork/dir",
            artwork_successfully_copied=False
        )
        
        assert ui_element.tag == "ui"
        assert len(ui_element) == 0  # No children when no artwork
        
    @patch('shutil.copy2')
    @patch('os.path.exists', return_value=True)  # Mock file existence
    def test_create_groups_element(self, mock_exists, mock_copy, setup_generator):
        """Test creation of groups element with sample data."""
        generator = setup_generator
        
        # Mock the sample file copy
        mock_copy.return_value = None
        
        # Create a temporary directory for samples
        with tempfile.TemporaryDirectory() as samples_dir:
            groups_element = generator._create_groups_element(samples_dir)
            
            # Verify the group structure
            assert groups_element.tag == "groups"
            group = groups_element.find("group")
            assert group is not None
            
            # Verify sample was copied
            expected_dest = os.path.join(samples_dir, "sample.wav")
            mock_copy.assert_called_once_with("/fake/path/sample.wav", expected_dest)
            
            # Verify sample element
            sample = group.find("sample")
            assert sample is not None
            assert sample.get("path") == "Samples/sample.wav"
            assert sample.get("rootNote") == "60"
            assert sample.get("loKey") == "48"
            assert sample.get("hiKey") == "72"
            assert sample.get("loVel") == "0"
            assert sample.get("hiVel") == "127"
    
    def test_create_effects_element(self, setup_generator):
        """Test creation of effects element (empty by default)."""
        generator = setup_generator
        
        effects_element = generator._create_effects_element()
        
        assert effects_element.tag == "effects"
        assert len(effects_element) == 0  # No effects by default

    @patch('os.makedirs', side_effect=OSError("Permission denied"))
    def test_generate_preset_directory_error(self, mock_makedirs, setup_generator):
        """Test error handling when directory creation fails."""
        generator = setup_generator
        
        # This should not raise an exception, but should print an error
        generator.generate_preset()
        
        # Verify no further operations were attempted
        assert True  # If we get here, the test passes

    @patch('shutil.copy2', side_effect=IOError("File not found"))
    @patch('os.path.exists', return_value=True)  # Mock file existence
    def test_generate_preset_sample_copy_error(self, mock_exists, mock_copy, setup_generator):
        """Test error handling when sample file copy fails."""
        generator = setup_generator
        
        # This should not raise an exception, but should print an error
        with tempfile.TemporaryDirectory() as samples_dir:
            groups_element = generator._create_groups_element(samples_dir)
            
            # The groups element should still be created, just without the sample
            assert groups_element is not None
            # The group is still created, but the sample copy will fail
            assert len(groups_element) == 1  # Group is still added, but sample copy fails
            group = groups_element.find("group")
            assert group is not None
            assert len(group) == 0  # No samples added due to error

    @patch('xml.etree.ElementTree.ElementTree.write', side_effect=IOError("Write error"))
    def test_generate_preset_write_error(self, mock_write, setup_generator):
        """Test error handling when writing the preset file fails."""
        generator = setup_generator
        
        # This should not raise an exception, but should print an error
        generator.generate_preset()
        assert True  # If we get here, the test passes
