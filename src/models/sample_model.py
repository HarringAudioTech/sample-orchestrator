# src/models/sample_model.py

class SampleModel:
    """
    Represents an individual audio sample file.
    """
    def __init__(self, file_path: str, root_note: int = None):
        """
        Initializes a SampleModel instance.

        Args:
            file_path (str): The path to the audio sample file.
            root_note (int, optional): The MIDI root note of the sample.
                                       Defaults to None if the sample is not pitched
                                       or its pitch is to be determined by mapping.
        """
        if not isinstance(file_path, str) or not file_path:
            raise ValueError("file_path must be a non-empty string.")

        if root_note is not None and not (isinstance(root_note, int) and 0 <= root_note <= 127):
            raise ValueError("root_note must be an integer between 0 and 127, or None.")

        self.file_path: str = file_path
        self.root_note: int = root_note

    def __repr__(self):
        return f"SampleModel(file_path='{self.file_path}', root_note={self.root_note})"
