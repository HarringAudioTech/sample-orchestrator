# tests/unit/test_mapping_models.py

import unittest

# Import the models from the correct location
try:
    from src.database.models import (
        Project,
        Sample as SampleModel,
        SampleMappingItem as SampleMappingItemModel,
        SampleMapping as SampleMappingModel
    )
except ImportError:
    # Fallback for local testing if PYTHONPATH isn't set up in the environment
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.database.models import (
        Project,
        Sample as SampleModel,
        SampleMappingItem as SampleMappingItemModel,
        SampleMapping as SampleMappingModel
    )

# Import datetime for testing timestamps
from datetime import datetime


class TestSampleModel(unittest.TestCase):
    def test_instantiation_valid(self):
        sample = SampleModel(
            name="test_sample",
            recording_id=1,
            file_path="test.wav",
            start_time_seconds=0.0,
            end_time_seconds=1.0,
            midi_pitch=60
        )
        self.assertEqual(sample.name, "test_sample")
        self.assertEqual(sample.recording_id, 1)
        self.assertEqual(sample.file_path, "test.wav")
        self.assertEqual(sample.start_time_seconds, 0.0)
        self.assertEqual(sample.end_time_seconds, 1.0)
        self.assertEqual(sample.midi_pitch, 60)

    def test_instantiation_required_fields(self):
        # SQLAlchemy doesn't enforce required fields at the model level,
        # so we'll test that the required fields are properly set when provided
        sample = SampleModel(
            name="test_sample",
            recording_id=1,
            file_path="test.wav",
            start_time_seconds=0.0,
            end_time_seconds=1.0
        )
        self.assertEqual(sample.name, "test_sample")
        self.assertEqual(sample.recording_id, 1)
        self.assertEqual(sample.file_path, "test.wav")
        self.assertEqual(sample.start_time_seconds, 0.0)
        self.assertEqual(sample.end_time_seconds, 1.0)

    def test_optional_fields(self):
        # Test with optional fields not provided
        sample = SampleModel(
            name="test_sample",
            recording_id=1,
            file_path="test.wav",
            start_time_seconds=0.0,
            end_time_seconds=1.0
        )
        self.assertIsNone(sample.sample_type)
        self.assertIsNone(sample.midi_pitch)
        self.assertIsNone(sample.metadata_json)

    def test_relationships(self):
        # Test that relationships are properly set up
        sample = SampleModel(
            name="test_sample",
            recording_id=1,
            file_path="test.wav",
            start_time_seconds=0.0,
            end_time_seconds=1.0
        )
        self.assertIsNotNone(sample.sample_mapping_items)
        self.assertEqual(len(sample.sample_mapping_items), 0)


class TestSampleMappingItemModel(unittest.TestCase):
    def setUp(self):
        # Create a sample for testing relationships
        self.sample = SampleModel(
            name="kick_sample",
            recording_id=1,
            file_path="kick.wav",
            start_time_seconds=0.0,
            end_time_seconds=1.0,
            midi_pitch=36
        )
        # Create a sample mapping for testing relationships
        self.sample_mapping = SampleMappingModel(
            project_id=1,
            name="Test Mapping"
        )

    def test_instantiation_valid(self):
        # Create a sample mapping item with all fields
        item = SampleMappingItemModel(
            sample_mapping=self.sample_mapping,
            sample=self.sample,
            key_range_start=60,
            key_range_end=72,
            velocity_range_start=80,
            velocity_range_end=100
        )
        # Test that all fields are set correctly
        self.assertIs(item.sample, self.sample)
        self.assertIs(item.sample_mapping, self.sample_mapping)
        self.assertEqual(item.key_range_start, 60)
        self.assertEqual(item.key_range_end, 72)
        self.assertEqual(item.velocity_range_start, 80)
        self.assertEqual(item.velocity_range_end, 100)
        # created_at is set by the database, so we don't test it here

    def test_instantiation_optional_fields(self):
        # Test with all optional fields as None
        item = SampleMappingItemModel(
            sample_mapping=self.sample_mapping,
            sample=self.sample
        )
        self.assertIsNone(item.key_range_start)
        self.assertIsNone(item.key_range_end)
        self.assertIsNone(item.velocity_range_start)
        self.assertIsNone(item.velocity_range_end)

    def test_required_fields(self):
        # SQLAlchemy doesn't enforce required fields at the model level,
        # but we should test that the required relationships are set correctly
        item = SampleMappingItemModel(
            sample_mapping=self.sample_mapping,
            sample=self.sample
        )
        self.assertIs(item.sample, self.sample)
        self.assertIs(item.sample_mapping, self.sample_mapping)

    def test_key_ranges(self):
        # Test setting valid key ranges
        item = SampleMappingItemModel(
            sample_mapping=self.sample_mapping,
            sample=self.sample,
            key_range_start=60,
            key_range_end=72
        )
        self.assertEqual(item.key_range_start, 60)
        self.assertEqual(item.key_range_end, 72)
        
        # Test setting None values (should be allowed)
        item.key_range_start = None
        item.key_range_end = None
        self.assertIsNone(item.key_range_start)
        self.assertIsNone(item.key_range_end)

    def test_velocity_ranges(self):
        # Test setting valid velocity ranges
        item = SampleMappingItemModel(
            sample_mapping=self.sample_mapping,
            sample=self.sample,
            velocity_range_start=20,
            velocity_range_end=100
        )
        self.assertEqual(item.velocity_range_start, 20)
        self.assertEqual(item.velocity_range_end, 100)
        
        # Test setting None values (should be allowed)
        item.velocity_range_start = None
        item.velocity_range_end = None
        self.assertIsNone(item.velocity_range_start)
        self.assertIsNone(item.velocity_range_end)
        with self.assertRaises(TypeError): # Pan type check
            SampleMappingItemModel(sample=self.sample, pan="wrong_type")


class TestSampleMappingModel(unittest.TestCase):
    def setUp(self):
        # Create a project for testing relationships
        self.project = Project(name="Test Project")
        
        # Create samples for testing
        self.sample1 = SampleModel(
            name="kick_sample",
            recording_id=1,
            file_path="kick.wav",
            start_time_seconds=0.0,
            end_time_seconds=1.0,
            midi_pitch=36
        )
        
        self.sample2 = SampleModel(
            name="snare_sample",
            recording_id=1,
            file_path="snare.wav",
            start_time_seconds=0.0,
            end_time_seconds=0.5,
            midi_pitch=38
        )
        
        # Create a sample mapping for testing
        self.sample_mapping = SampleMappingModel(
            project=self.project,
            name="Drum Kit Mapping",
            mapping_type="drum_kit"
        )
        
        # Create mapping items
        self.item1 = SampleMappingItemModel(
            sample_mapping=self.sample_mapping,
            sample=self.sample1,
            key_range_start=36,
            key_range_end=36,
            velocity_range_start=0,
            velocity_range_end=127
        )
        
        self.item2 = SampleMappingItemModel(
            sample_mapping=self.sample_mapping,
            sample=self.sample2,
            key_range_start=38,
            key_range_end=38,
            velocity_range_start=0,
            velocity_range_end=127
        )

    def test_instantiation(self):
        # Test basic instantiation with required fields
        mapping = SampleMappingModel(
            project=self.project,
            name="Test Mapping"
        )
        self.assertEqual(mapping.name, "Test Mapping")
        self.assertIs(mapping.project, self.project)
        self.assertIsNone(mapping.mapping_type)
        # created_at and updated_at are set by the database, so we don't test them here
        self.assertEqual(len(mapping.sample_mapping_items), 0)
        
        # Test with all fields
        mapping_with_type = SampleMappingModel(
            project=self.project,
            name="Test Mapping with Type",
            mapping_type="instrument_key_zone"
        )
        self.assertEqual(mapping_with_type.mapping_type, "instrument_key_zone")

    def test_required_fields(self):
        # SQLAlchemy doesn't enforce required fields at the model level,
        # but we should test that the required fields are set correctly
        mapping = SampleMappingModel(
            project=self.project,
            name="Test Required Fields"
        )
        self.assertEqual(mapping.name, "Test Required Fields")
        self.assertIs(mapping.project, self.project)

    def test_relationships(self):
        # Test relationship with project
        # Note: The project.sample_mappings relationship might not be populated automatically
        # So we'll test the direct relationship instead
        self.assertIs(self.sample_mapping.project, self.project)
        
        # Create a new list of items for this test to avoid interference from setUp
        test_item1 = SampleMappingItemModel(
            sample_mapping=self.sample_mapping,
            sample=self.sample1,
            key_range_start=48,
            key_range_end=60
        )
        test_item2 = SampleMappingItemModel(
            sample_mapping=self.sample_mapping,
            sample=self.sample2,
            key_range_start=61,
            key_range_end=72
        )
        
        # Add items to the mapping
        self.sample_mapping.sample_mapping_items = [test_item1, test_item2]
        
        # Test the relationship
        self.assertEqual(len(self.sample_mapping.sample_mapping_items), 2)
        self.assertIn(test_item1, self.sample_mapping.sample_mapping_items)
        self.assertIn(test_item2, self.sample_mapping.sample_mapping_items)
        
        # Test backref from items to mapping
        self.assertIs(test_item1.sample_mapping, self.sample_mapping)
        self.assertIs(test_item2.sample_mapping, self.sample_mapping)

    def test_timestamps(self):
        # Test that the timestamp attributes exist
        self.assertTrue(hasattr(self.sample_mapping, 'created_at'))
        self.assertTrue(hasattr(self.sample_mapping, 'updated_at'))
        
        # In a real test with a database, we'd test that:
        # 1. created_at is set when the record is first created
        # 2. updated_at changes when the record is updated
        # But since we're not using a real database in these tests,
        # we'll just verify the attributes exist and are the correct type
        if self.sample_mapping.created_at is not None:
            self.assertIsInstance(self.sample_mapping.created_at, datetime)
        if self.sample_mapping.updated_at is not None:
            self.assertIsInstance(self.sample_mapping.updated_at, datetime)


if __name__ == '__main__':
    unittest.main()
