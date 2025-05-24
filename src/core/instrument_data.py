from dataclasses import dataclass
from typing import Optional


@dataclass
class InstrumentData:
    """Represents metadata for a musical instrument preset.

    This dataclass stores information about the instrument, such as its name,
    author, version, and associated files like UI background images.
    It is used to populate the metadata in the generated preset files.

    Attributes:
        name: The full name of the instrument (e.g., "My Grand Piano").
        author: The name of the author or creator of the instrument.
        version: The version string of the instrument (e.g., "1.0.0"). Defaults to None.
        website: An optional URL for the instrument's or author's website. Defaults to None.
        ui_background_image_path: An optional absolute or relative path to an image file
                                  to be used as the UI background. Defaults to None.
    """

    name: str
    author: str
    version: Optional[str] = None
    website: Optional[str] = None
    ui_background_image_path: Optional[str] = None
