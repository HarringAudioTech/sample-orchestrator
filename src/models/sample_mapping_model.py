# src/models/sample_mapping_model.py

from typing import List
from .sample_mapping_item_model import SampleMappingItemModel

class SampleMappingModel:
    """
    Represents a collection of sample mapping items, defining how multiple
    samples are mapped to MIDI events for an instrument.
    """
    def __init__(self):
        """
        Initializes a SampleMappingModel instance with an empty list of mapping items.
        """
        self.mapping_items: List[SampleMappingItemModel] = []

    def add_mapping_item(self, item: SampleMappingItemModel):
        """
        Adds a SampleMappingItemModel to the collection.

        Args:
            item (SampleMappingItemModel): The mapping item to add.

        Raises:
            TypeError: If the item is not an instance of SampleMappingItemModel.
        """
        if not isinstance(item, SampleMappingItemModel):
            raise TypeError("Only SampleMappingItemModel instances can be added.")
        self.mapping_items.append(item)

    def remove_mapping_item(self, item: SampleMappingItemModel):
        """
        Removes a SampleMappingItemModel from the collection.

        Args:
            item (SampleMappingItemModel): The mapping item to remove.

        Raises:
            ValueError: If the item is not found in the list.
        """
        try:
            self.mapping_items.remove(item)
        except ValueError:
            raise ValueError("Item not found in mapping_items list.")

    def __repr__(self):
        return f"SampleMappingModel(mapping_items_count={len(self.mapping_items)})"

    def __len__(self):
        """Returns the number of mapping items."""
        return len(self.mapping_items)

    def __iter__(self):
        """Allows iteration over the mapping items."""
        return iter(self.mapping_items)
