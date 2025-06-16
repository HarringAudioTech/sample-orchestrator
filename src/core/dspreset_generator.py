import xml.etree.ElementTree as ET
import os
import shutil
from src.core.project import Project
from src.core.instrument_data import InstrumentData
from src.database.models import (
    Recording as RecordingModel,
    Sample as SampleModel,
    # SampleMapping as SampleMappingModel, # Not directly used in this file
    SampleMappingItem as SampleMappingItemModel,
)
from typing import List, Optional  # For type hinting


class DecentSamplerPresetGenerator:
    """Generates Decent Sampler preset files (.dspreset) and associated file structure.

    This class takes a Project (containing sample data) and InstrumentData (metadata)
    to create a self-contained instrument preset for the Decent Sampler plugin.
    It handles directory creation, copying of sample files and artwork, and
    generation of the XML-based .dspreset file.

    Attributes:
        project: The `Project` object, which provides access to the underlying
                 database models for recordings and samples.
        instrument_data: An `InstrumentData` object containing metadata for the
                         instrument, such as name, author, and UI image path.
        output_base_dir: The root directory where the instrument's folder structure
                         will be created.
    """

    def __init__(
        self, project: Project, instrument_data: InstrumentData, output_base_dir: str
    ) -> None:
        """Initializes the DecentSamplerPresetGenerator with project data and output directory.

        Args:
            project: The `Project` object containing the sample data and structure.
            instrument_data: The `InstrumentData` object with metadata for the instrument.
            output_base_dir: The base path where the instrument's output directory
                             will be created.
        """
        self.project: Project = project
        self.instrument_data: InstrumentData = instrument_data
        self.output_base_dir: str = output_base_dir

    def _sanitize_filename(self, name: str) -> str:
        """Sanitizes a string for use as a filename or directory name.

        This method performs the following operations:
        1. Replaces all occurrences of spaces (" ") with underscores ("_").
        2. Converts the entire string to lowercase.

        Args:
            name (str): The input string to be sanitized.

        Returns:
            str: The sanitized string, suitable for file or directory names.
        """
        return name.replace(" ", "_").lower()

    def generate_preset(self) -> None:
        """Generates the complete Decent Sampler instrument preset and file structure.

        This method orchestrates the entire process of creating a Decent Sampler
        instrument. It performs the following steps:
        1. Sanitizes the instrument name to create a filesystem-friendly name.
        2. Creates the main instrument directory and subdirectories for 'Samples'
           and 'Artwork'.
        3. Copies the UI background image (if specified and found) into the
           'Artwork' directory.
        4. Generates the .dspreset XML file by:
            - Creating the root <DecentSampler> element.
            - Creating and appending the <ui> element (including background image).
            - Creating and appending the <groups> element (which involves copying
              sample files into the 'Samples' directory and creating <sample> tags).
            - Creating and appending an empty <effects> element.
        5. Writes the generated XML structure to a .dspreset file in the main
           instrument directory.

        Prints informational messages, warnings, and error messages to standard
        output during the generation process. File operations (directory creation,
        file copying, file writing) are susceptible to `OSError` exceptions, which
        are caught and reported. An error in creating base directories will halt
        the process. Errors in copying artwork or individual samples, or writing
        the final preset file, will be reported but the process may attempt to
        continue with other parts if feasible.

        Args:
            None.

        Returns:
            None.
        """
        instrument_name_fs: str = self._sanitize_filename(self.instrument_data.name)
        instrument_dir: str = os.path.join(self.output_base_dir, instrument_name_fs)
        samples_dir: str = os.path.join(instrument_dir, "Samples")
        artwork_dir = os.path.join(instrument_dir, "Artwork")

        try:
            os.makedirs(instrument_dir, exist_ok=True)
            os.makedirs(samples_dir, exist_ok=True)
            os.makedirs(artwork_dir, exist_ok=True)
            print(f"INFO: Created instrument directory: {instrument_dir}")
            print(f"INFO: Created Samples directory: {samples_dir}")
            print(f"INFO: Created Artwork directory: {artwork_dir}")
        except OSError as e:
            print(f"ERROR: Could not create instrument directories: {e}")
            return  # Stop if base directories can't be made

        # Copy Artwork
        artwork_copied_successfully = False  # Initialize flag
        if self.instrument_data.ui_background_image_path:
            source_artwork_path: str = self.instrument_data.ui_background_image_path
            artwork_filename: str = os.path.basename(source_artwork_path)
            dest_artwork_path: str = os.path.join(artwork_dir, artwork_filename)
            if os.path.exists(source_artwork_path):
                try:
                    shutil.copy2(source_artwork_path, dest_artwork_path)
                    print(
                        f"INFO: Copied artwork: {source_artwork_path} to {dest_artwork_path}"
                    )
                    artwork_copied_successfully = True  # Set flag on success
                except IOError as e:
                    print(f"ERROR: Could not copy artwork file {artwork_filename}: {e}")
                    # artwork_copied_successfully remains False
            else:
                print(f"WARNING: Artwork source file not found: {source_artwork_path}")
                # artwork_copied_successfully remains False

        # Create XML structure
        # Samples are copied within _create_groups_element, which needs
        # samples_dir
        root_element: ET.Element = self._create_root_element()
        ui_element: ET.Element = self._create_ui_element(
            artwork_output_dir=artwork_dir,
            artwork_successfully_copied=artwork_copied_successfully,
        )
        root_element.append(ui_element)

        groups_element: ET.Element = self._create_groups_element(samples_dir)
        root_element.append(groups_element)

        effects_element: ET.Element = self._create_effects_element()
        root_element.append(effects_element)

        # Write .dspreset file
        dspreset_filename: str = instrument_name_fs + ".dspreset"
        dspreset_path: str = os.path.join(instrument_dir, dspreset_filename)
        try:
            tree: ET.ElementTree = ET.ElementTree(root_element)
            # ET.indent(tree, space="\t", level=0) # For pretty printing,
            # Python 3.9+
            tree.write(dspreset_path, encoding="UTF-8", xml_declaration=True)
            print(f"INFO: Generated preset file: {dspreset_path}")
        except IOError as e:
            print(f"ERROR: Could not write .dspreset file: {e}")

    def _create_root_element(self) -> ET.Element:
        """Creates the root <DecentSampler> XML element for the preset.

        This element serves as the top-level container for the entire preset
        definition. It includes a mandatory `minVersion` attribute indicating
        the minimum version of Decent Sampler required to interpret the preset.
        Optionally, if a version is specified in the `instrument_data`, a
        `version` attribute is also added to the root element.

        Args:
            None.

        Returns:
            xml.etree.ElementTree.Element: The configured root <DecentSampler>
            XML element.
        """
        root: ET.Element = ET.Element("DecentSampler")
        root.set("minVersion", "1.0.0")
        if self.instrument_data.version:
            root.set("version", self.instrument_data.version)
        # Consider adding author and website as comments or custom tags if desired,
        # though not standard in DecentSampler format for the root.
        # root.append(ET.Comment(f"Author: {self.instrument_data.author}"))
        # if self.instrument_data.website:
        #     root.append(ET.Comment(f"Website: {self.instrument_data.website}"))
        return root

    def _create_ui_element(
        self,
        artwork_output_dir: Optional[str] = None,
        artwork_successfully_copied: bool = False,
    ) -> ET.Element:
        """Creates the <ui> XML element for the Decent Sampler preset.

        This element defines the user interface of the instrument. If a UI
        background image is specified in `instrument_data` and was successfully
        copied to the 'Artwork' directory, a <tab> element named "main" is
        created with a <background> sub-element pointing to this image.
        The image path in the XML is relative to the .dspreset file.

        Args:
            artwork_output_dir (Optional[str]): The absolute path to the 'Artwork'
                directory. Currently, this argument is noted for potential future
                use but does not directly affect the image path written to the XML,
                as the XML path is relative. Defaults to None.
            artwork_successfully_copied (bool): A flag indicating whether the
                artwork file was successfully copied. If False, or if no
                UI background image path is set in `instrument_data`, the
                background image tag will not be added. Defaults to False.

        Returns:
            xml.etree.ElementTree.Element: The configured <ui> XML element,
            potentially including a background image definition.
        """
        ui_element: ET.Element = ET.Element("ui")
        if (
            self.instrument_data.ui_background_image_path
            and artwork_successfully_copied
        ):
            source_artwork_path: str = self.instrument_data.ui_background_image_path
            artwork_filename: str = os.path.basename(source_artwork_path)
            # XML path should be relative to the .dspreset file location
            relative_image_path: str = os.path.join("Artwork", artwork_filename)

            tab_element: ET.Element = ET.SubElement(ui_element, "tab")
            tab_element.set("name", "main")  # Default tab name
            background_element: ET.Element = ET.SubElement(tab_element, "background")
            background_element.set("image", relative_image_path)
        return ui_element

    def _create_groups_element(self, samples_output_dir: str) -> ET.Element:
        """Creates the <groups> XML element and populates it with sample data.

        This method constructs the <groups> section of the .dspreset file.
        It iterates through each recording in the project. For each recording,
        a <group> XML element is created. Within each group, it processes every
        associated sample:
        1. The sample's audio file is copied from its source location to the
           instrument's 'Samples' subdirectory (created within `samples_output_dir`).
           If copying fails or the source file doesn't exist, a warning is printed
           and the sample is skipped.
        2. A <sample> XML element is created with attributes:
            - `path`: Relative path to the copied sample file (e.g., "Samples/sample_name.wav").
            - `rootNote`: MIDI note number of the sample's root pitch. Defaults to 60 (C3)
              if not specified in the sample model.
            - `loKey`, `hiKey`: MIDI note numbers defining the keyboard range for this
              sample. Derived from `sample_mapping_items` if available, otherwise
              defaults to the `rootNote`.
            - `loVel`, `hiVel`: Velocity range (0-127) for this sample. Defaults to
              the full range (0-127).
        If no recordings are found in the project, an empty <groups> element is returned.

        Args:
            samples_output_dir (str): The absolute path to the 'Samples' directory
                where sample audio files will be copied and referenced from.

        Returns:
            xml.etree.ElementTree.Element: The configured <groups> XML element,
            containing all <group> and <sample> sub-elements.
        """
        groups_element: ET.Element = ET.Element("groups")

        if not self.project.project_model or not self.project.project_model.recordings:
            print(
                "INFO: No recordings found in the project. Groups element will be empty."
            )
            return groups_element

        for recording_model in self.project.project_model.recordings:
            # Create a <group> for each recording.
            # You could add attributes to the group here, e.g., name
            group_element: ET.Element = ET.SubElement(groups_element, "group")
            if recording_model.name:  # Add group name if available
                group_element.set("name", recording_model.name)

            if not recording_model.samples:
                # Drastically simplified f-string for pylint testing
                print(f"INFO: Rec {recording_model.name} empty.")
                continue

            for sample_model in recording_model.samples:
                source_sample_path: str = sample_model.file_path
                sample_filename: str = os.path.basename(source_sample_path)
                dest_sample_path: str = os.path.join(
                    samples_output_dir, sample_filename
                )

                # Attempt to copy the sample file
                if os.path.exists(source_sample_path):
                    try:
                        shutil.copy2(source_sample_path, dest_sample_path)
                        # print(f"INFO: Copied sample: {source_sample_path} to {dest_sample_path}")
                    except IOError as e:
                        print(
                            f"ERROR: Could not copy sample file {sample_filename}: {e}"
                        )
                        continue  # Skip this sample if copy fails
                else:
                    print(
                        f"WARNING: Sample source file not found, skipping: {source_sample_path}"
                    )
                    continue  # Skip this sample if source doesn't exist

                # Create the <sample> XML element
                sample_element: ET.Element = ET.SubElement(group_element, "sample")

                # Path is relative to the .dspreset file, within the 'Samples'
                # subdirectory
                xml_sample_path: str = os.path.join("Samples", sample_filename)
                sample_element.set("path", xml_sample_path)

                # Root note (MIDI note number)
                root_note_val: int = sample_model.midi_pitch
                root_note_str: str = (
                    str(root_note_val) if root_note_val is not None else "60"
                )  # Default to C3 (MIDI 60)
                sample_element.set("rootNote", root_note_str)

                # Key range (loKey, hiKey)
                lo_key_str: str = root_note_str
                hi_key_str: str = root_note_str
                if sample_model.sample_mapping_items:
                    # Assuming the first mapping item dictates the key range for this sample.
                    # More complex logic might be needed if multiple items or
                    # complex mappings exist.
                    mapping_item: SampleMappingItemModel = (
                        sample_model.sample_mapping_items[0]
                    )
                    if mapping_item.key_range_start is not None:
                        lo_key_str = str(mapping_item.key_range_start)
                    if mapping_item.key_range_end is not None:
                        hi_key_str = str(mapping_item.key_range_end)

                sample_element.set("loKey", lo_key_str)
                sample_element.set("hiKey", hi_key_str)

                # Velocity range (loVel, hiVel) - defaults to full range
                lo_vel_str: str = "0"
                hi_vel_str: str = "127"
                # Example of how to integrate velocity from mapping_item if it were available:
                # if sample_model.sample_mapping_items:
                #     mapping_item = sample_model.sample_mapping_items[0]
                #     if mapping_item.velocity_range_start is not None:
                #         lo_vel_str = str(mapping_item.velocity_range_start)
                #     if mapping_item.velocity_range_end is not None:
                #         hi_vel_str = str(mapping_item.velocity_range_end)
                sample_element.set("loVel", lo_vel_str)
                sample_element.set("hiVel", hi_vel_str)

                # Other potential sample attributes (e.g., volume, pan, loop settings)
                # sample_element.set("volume", "0dB") # Example

        return groups_element

    def _create_effects_element(self) -> ET.Element:
        """Creates the <effects> XML element for the Decent Sampler preset.

        This method is responsible for defining any built-in effects (like
        reverb, delay, etc.) for the instrument. Currently, it serves as a
        placeholder and returns an empty <effects> tag, as the definition
        and inclusion of specific effects are not yet implemented.
        Future enhancements could involve parsing effect configurations from
        `instrument_data` or other sources to populate this section.

        Args:
            None.

        Returns:
            xml.etree.ElementTree.Element: An empty <effects> XML element.
        """
        effects_element: ET.Element = ET.Element("effects")
        # Example: ET.SubElement(effects_element, "effect", type="reverb", wetLevel="0.5")
        # ET.Comment("Effects can be added here, e.g., reverb, delay.")
        return effects_element
