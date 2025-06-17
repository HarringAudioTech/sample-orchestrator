# tests/unit/test_mapping_models.py

import unittest

# Attempt to import the models. If src is not in PYTHONPATH, this might require adjustment
# For now, assume direct import works or the execution environment handles it.
# If issues arise, may need to adjust path or use relative imports if tests are part of the src package.
try:
    from src.models.sample_model import SampleModel
    from src.models.sample_mapping_item_model import SampleMappingItemModel
    from src.models.sample_mapping_model import SampleMappingModel
except ImportError:
    # This is a fallback for local testing if PYTHONPATH isn't set up in the environment
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.models.sample_model import SampleModel
    from src.models.sample_mapping_item_model import SampleMappingItemModel
    from src.models.sample_mapping_model import SampleMappingModel


class TestSampleModel(unittest.TestCase):
    def test_instantiation_valid(self):
        sample = SampleModel(file_path="test.wav", root_note=60)
        self.assertEqual(sample.file_path, "test.wav")
        self.assertEqual(sample.root_note, 60)

    def test_instantiation_default_root_note(self):
        sample = SampleModel(file_path="another.wav")
        self.assertEqual(sample.file_path, "another.wav")
        self.assertIsNone(sample.root_note)

    def test_invalid_file_path(self):
        with self.assertRaises(ValueError):
            SampleModel(file_path="", root_note=60) # Empty file_path
        with self.assertRaises(ValueError):
            SampleModel(file_path=None, root_note=60) # None file_path

    def test_invalid_root_note(self):
        with self.assertRaises(ValueError):
            SampleModel(file_path="test.wav", root_note=-1) # Below range
        with self.assertRaises(ValueError):
            SampleModel(file_path="test.wav", root_note=128) # Above range
        with self.assertRaises(ValueError):
            SampleModel(file_path="test.wav", root_note="not_an_int") # Wrong type


class TestSampleMappingItemModel(unittest.TestCase):
    def setUp(self):
        self.sample = SampleModel(file_path="kick.wav", root_note=36)

    def test_instantiation_valid(self):
        item = SampleMappingItemModel(
            sample=self.sample,
            note_start=60, note_end=60,
            velocity_start=80, velocity_end=100,
            round_robin_group=1,
            tune_cents=5.5,
            pan=-0.5
        )
        self.assertIs(item.sample, self.sample)
        self.assertEqual(item.note_start, 60)
        self.assertEqual(item.note_end, 60)
        self.assertEqual(item.velocity_start, 80)
        self.assertEqual(item.velocity_end, 100)
        self.assertEqual(item.round_robin_group, 1)
        self.assertEqual(item.tune_cents, 5.5)
        self.assertEqual(item.pan, -0.5)

    def test_instantiation_defaults(self):
        item = SampleMappingItemModel(sample=self.sample)
        self.assertEqual(item.note_start, 0)
        self.assertEqual(item.note_end, 127)
        self.assertEqual(item.velocity_start, 0)
        self.assertEqual(item.velocity_end, 127)
        self.assertEqual(item.round_robin_group, 0)
        self.assertEqual(item.tune_cents, 0.0)
        self.assertEqual(item.pan, 0.0)

    def test_invalid_sample(self):
        with self.assertRaises(TypeError):
            SampleMappingItemModel(sample="not_a_sample_model")

    def test_invalid_note_ranges(self):
        with self.assertRaises(ValueError): # start > end
            SampleMappingItemModel(sample=self.sample, note_start=61, note_end=60)
        with self.assertRaises(ValueError): # out of bounds
            SampleMappingItemModel(sample=self.sample, note_start=-1)
        with self.assertRaises(ValueError): # out of bounds
            SampleMappingItemModel(sample=self.sample, note_end=128)

    def test_invalid_velocity_ranges(self):
        with self.assertRaises(ValueError): # start > end
            SampleMappingItemModel(sample=self.sample, velocity_start=101, velocity_end=100)
        with self.assertRaises(ValueError): # out of bounds
            SampleMappingItemModel(sample=self.sample, velocity_start=-1)
        with self.assertRaises(ValueError): # out of bounds
            SampleMappingItemModel(sample=self.sample, velocity_end=128)

    def test_invalid_pan_value(self):
        with self.assertRaises(ValueError):
            SampleMappingItemModel(sample=self.sample, pan=-1.1)
        with self.assertRaises(ValueError):
            SampleMappingItemModel(sample=self.sample, pan=1.1)

    def test_invalid_types(self):
        with self.assertRaises(TypeError):
            SampleMappingItemModel(sample=self.sample, round_robin_group="abc")
        with self.assertRaises(TypeError):
            SampleMappingItemModel(sample=self.sample, tune_cents="abc")
        with self.assertRaises(TypeError): # Pan type check
            SampleMappingItemModel(sample=self.sample, pan="wrong_type")


class TestSampleMappingModel(unittest.TestCase):
    def setUp(self):
        self.sample1 = SampleModel("s1.wav")
        self.sample2 = SampleModel("s2.wav")
        self.item1 = SampleMappingItemModel(sample=self.sample1)
        self.item2 = SampleMappingItemModel(sample=self.sample2, note_start=60, note_end=70)

    def test_instantiation(self):
        model = SampleMappingModel()
        self.assertEqual(len(model.mapping_items), 0)
        self.assertEqual(len(model), 0)

    def test_add_item(self):
        model = SampleMappingModel()
        model.add_mapping_item(self.item1)
        self.assertEqual(len(model.mapping_items), 1)
        self.assertIn(self.item1, model.mapping_items)
        self.assertEqual(len(model), 1)

        model.add_mapping_item(self.item2)
        self.assertEqual(len(model.mapping_items), 2)
        self.assertIn(self.item2, model.mapping_items)
        self.assertEqual(len(model), 2)

        # Test iteration
        items_iterated = [item for item in model]
        self.assertEqual(len(items_iterated), 2)
        self.assertIn(self.item1, items_iterated)
        self.assertIn(self.item2, items_iterated)


    def test_add_invalid_item_type(self):
        model = SampleMappingModel()
        with self.assertRaises(TypeError):
            model.add_mapping_item("not_a_mapping_item")

    def test_remove_item(self):
        model = SampleMappingModel()
        model.add_mapping_item(self.item1)
        model.add_mapping_item(self.item2)

        model.remove_mapping_item(self.item1)
        self.assertEqual(len(model.mapping_items), 1)
        self.assertNotIn(self.item1, model.mapping_items)
        self.assertIn(self.item2, model.mapping_items)
        self.assertEqual(len(model), 1)

    def test_remove_nonexistent_item(self):
        model = SampleMappingModel()
        model.add_mapping_item(self.item1)
        non_existent_item = SampleMappingItemModel(SampleModel("non_existent.wav"))
        with self.assertRaises(ValueError):
            model.remove_mapping_item(non_existent_item)


if __name__ == '__main__':
    unittest.main()
