# src/models/sample_mapping_item_model.py

from .sample_model import SampleModel

class SampleMappingItemModel:
    """
    Represents a single mapping rule for a sample, linking it to MIDI
    note ranges, velocity layers, and other performance parameters.
    """
    def __init__(self,
                 sample: SampleModel,
                 note_start: int = 0,
                 note_end: int = 127,
                 velocity_start: int = 0,
                 velocity_end: int = 127,
                 round_robin_group: int = 0,
                 tune_cents: float = 0.0,
                 pan: float = 0.0):
        """
        Initializes a SampleMappingItemModel instance.

        Args:
            sample (SampleModel): The sample associated with this mapping.
            note_start (int): MIDI note number for the start of the key range (0-127). Defaults to 0.
            note_end (int): MIDI note number for the end of the key range (0-127). Defaults to 127.
            velocity_start (int): MIDI velocity for the start of the velocity range (0-127). Defaults to 0.
            velocity_end (int): MIDI velocity for the end of the velocity range (0-127). Defaults to 127.
            round_robin_group (int, optional): The round-robin group identifier. Defaults to 0.
            tune_cents (float, optional): Fine-tuning in cents. Defaults to 0.0.
            pan (float, optional): Stereo pan (-1.0 for left, 1.0 for right). Defaults to 0.0.
        """
        if not isinstance(sample, SampleModel):
            raise TypeError("sample must be an instance of SampleModel.")

        if not (isinstance(note_start, int) and 0 <= note_start <= 127):
            raise ValueError("note_start must be an integer between 0 and 127.")
        if not (isinstance(note_end, int) and 0 <= note_end <= 127):
            raise ValueError("note_end must be an integer between 0 and 127.")
        if note_start > note_end:
            raise ValueError("note_start cannot be greater than note_end.")

        if not (isinstance(velocity_start, int) and 0 <= velocity_start <= 127):
            raise ValueError("velocity_start must be an integer between 0 and 127.")
        if not (isinstance(velocity_end, int) and 0 <= velocity_end <= 127):
            raise ValueError("velocity_end must be an integer between 0 and 127.")
        if velocity_start > velocity_end:
            raise ValueError("velocity_start cannot be greater than velocity_end.")

        if not isinstance(round_robin_group, int):
            raise TypeError("round_robin_group must be an integer.")

        if not isinstance(tune_cents, (int, float)):
            raise TypeError("tune_cents must be a number (int or float).")

        if not isinstance(pan, (int, float)):
            raise TypeError("pan must be a number (int or float).")
        if not (-1.0 <= pan <= 1.0):
            raise ValueError("pan must be a float between -1.0 and 1.0.")

        self.sample: SampleModel = sample
        self.note_start: int = note_start
        self.note_end: int = note_end
        self.velocity_start: int = velocity_start
        self.velocity_end: int = velocity_end
        self.round_robin_group: int = round_robin_group
        self.tune_cents: float = float(tune_cents)
        self.pan: float = float(pan)

    def __repr__(self):
        return (f"SampleMappingItemModel(sample={self.sample!r}, "
                f"note_start={self.note_start}, note_end={self.note_end}, "
                f"velocity_start={self.velocity_start}, velocity_end={self.velocity_end}, "
                f"round_robin_group={self.round_robin_group}, "
                f"tune_cents={self.tune_cents}, pan={self.pan})")
