import xml.etree.ElementTree as ET
import os
import shutil
from src.core.project import Project
from src.core.instrument_data import InstrumentData
from src.database.models import (
    Recording as RecordingModel,
    Sample as SampleModel,
    # SampleMapping as SampleMappingModel, # Not directly used in this file
    SampleMappingItem as SampleMappingItemModel
)
from typing import List # For type hinting

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

    def __init__(self, project: Project, instrument_data: InstrumentData, output_base_dir: str):
        """Initializes the DecentSamplerPresetGenerator.

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
        """Sanitizes a string to be suitable for use as a filename or directory name.
        Replaces spaces with underscores and converts to lowercase.

        Args:
            name: The string to sanitize.

        Returns:
            The sanitized string.
        """
        return name.replace(" ", "_").lower()

    def generate_preset(self) -> None:
        """Generates the complete Decent Sampler instrument.

        This method orchestrates the creation of the instrument directory,
        subdirectories for Samples and Artwork, copies the necessary files
        (samples, UI background), and generates the .dspreset XML file.

        Prints status messages and warnings to stdout.
        Possible OSErrors during directory or file operations will be caught and
        reported, potentially halting parts of the generation.
        """
        instrument_name_fs = self._sanitize_filename(self.instrument_data.name)
        instrument_dir = os.path.join(self.output_base_dir, instrument_name_fs)
        samples_dir = os.path.join(instrument_dir, "Samples")
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
            return # Stop if base directories can't be made

        # Copy Artwork
        if self.instrument_data.ui_background_image_path:
            source_artwork_path = self.instrument_data.ui_background_image_path
            artwork_filename = os.path.basename(source_artwork_path)
            dest_artwork_path = os.path.join(artwork_dir, artwork_filename)
            if os.path.exists(source_artwork_path):
                try:
                    shutil.copy2(source_artwork_path, dest_artwork_path)
                    print(f"INFO: Copied artwork: {source_artwork_path} to {dest_artwork_path}")
                except IOError as e:
                    print(f"ERROR: Could not copy artwork file {artwork_filename}: {e}")
            else:
                print(f"WARNING: Artwork source file not found: {source_artwork_path}")
        
        # Create XML structure
        # Samples are copied within _create_groups_element, which needs samples_dir
        root_element = self._create_root_element()
        ui_element = self._create_ui_element(artwork_dir) # Pass artwork_dir for context if needed
        root_element.append(ui_element)

        groups_element = self._create_groups_element(samples_dir)
        root_element.append(groups_element)

        effects_element = self._create_effects_element()
        root_element.append(effects_element)

        # Write .dspreset file
        dspreset_filename = instrument_name_fs + ".dspreset"
        dspreset_path = os.path.join(instrument_dir, dspreset_filename)
        try:
            tree = ET.ElementTree(root_element)
            # ET.indent(tree, space="\t", level=0) # For pretty printing, Python 3.9+
            tree.write(dspreset_path, encoding="UTF-8", xml_declaration=True)
            print(f"INFO: Generated preset file: {dspreset_path}")
        except IOError as e:
            print(f"ERROR: Could not write .dspreset file: {e}")

    def _create_root_element(self) -> ET.Element:
        """Creates the root <DecentSampler> XML element.

        The root element includes the `minVersion` attribute.
        It can optionally include a `version` attribute based on `instrument_data`.

        Returns:
            The `ET.Element` for the root of the DecentSampler preset.
        """
        root = ET.Element("DecentSampler")
        root.set("minVersion", "1.0.0")
        if self.instrument_data.version:
            root.set("version", self.instrument_data.version)
        # Consider adding author and website as comments or custom tags if desired,
        # though not standard in DecentSampler format for the root.
        # root.append(ET.Comment(f"Author: {self.instrument_data.author}"))
        # if self.instrument_data.website:
        #     root.append(ET.Comment(f"Website: {self.instrument_data.website}"))
        return root

    def _create_ui_element(self, artwork_output_dir: str) -> ET.Element:
        """Creates the <ui> XML element, including background image if specified.

        Args:
            artwork_output_dir: The absolute path to the 'Artwork' directory where UI
                                 elements are stored. Used for context if needed,
                                 though paths in XML are relative.

        Returns:
            The `ET.Element` for the <ui> section.
        """
        ui_element = ET.Element("ui")
        if self.instrument_data.ui_background_image_path:
            # Ensure the source file exists before referencing it in XML
            # (actual copy happens in generate_preset)
            source_artwork_path = self.instrument_data.ui_background_image_path
            if os.path.exists(source_artwork_path):
                artwork_filename = os.path.basename(source_artwork_path)
                # XML path should be relative to the .dspreset file location
                relative_image_path = os.path.join("Artwork", artwork_filename)

                tab_element = ET.SubElement(ui_element, "tab")
                tab_element.set("name", "main") # Default tab name
                background_element = ET.SubElement(tab_element, "background")
                background_element.set("image", relative_image_path)
            # else:
                # Warning about missing artwork source is handled in generate_preset()
                # No need to duplicate here, as this method only builds XML structure.
        return ui_element

    def _create_groups_element(self, samples_output_dir: str) -> ET.Element:
        """Creates the <groups> XML element, populating it with <group> and <sample> tags.

        This method iterates through recordings and their associated samples from the
        project model. For each sample, it attempts to copy the audio file to the
        `Samples` directory and then creates a corresponding `<sample>` XML element
        with attributes for path, root note, key range, and velocity range.

        Args:
            samples_output_dir: The absolute path to the 'Samples' directory where
                                audio files will be copied.

        Returns:
            The `ET.Element` for the <groups> section.
        """
        groups_element = ET.Element("groups")

        if not self.project.project_model or not self.project.project_model.recordings:
            print("INFO: No recordings found in the project. Groups element will be empty.")
            return groups_element

        for recording_model in self.project.project_model.recordings:
            # Create a <group> for each recording.
            # You could add attributes to the group here, e.g., name
            group_element = ET.SubElement(groups_element, "group")
            if recording_model.name: # Add group name if available
                 group_element.set("name", recording_model.name)

            if not recording_model.samples:
                print(f"INFO: No samples found for recording '{recording_model.name}'. Group will be empty.")
                continue

            for sample_model in recording_model.samples:
                source_sample_path = sample_model.file_path
                sample_filename = os.path.basename(source_sample_path)
                dest_sample_path = os.path.join(samples_output_dir, sample_filename)

                # Attempt to copy the sample file
                if os.path.exists(source_sample_path):
                    try:
                        shutil.copy2(source_sample_path, dest_sample_path)
                        # print(f"INFO: Copied sample: {source_sample_path} to {dest_sample_path}")
                    except IOError as e:
                        print(f"ERROR: Could not copy sample file {sample_filename}: {e}")
                        continue # Skip this sample if copy fails
                else:
                    print(f"WARNING: Sample source file not found, skipping: {source_sample_path}")
                    continue # Skip this sample if source doesn't exist

                # Create the <sample> XML element
                sample_element = ET.SubElement(group_element, "sample")
                
                # Path is relative to the .dspreset file, within the 'Samples' subdirectory
                xml_sample_path = os.path.join("Samples", sample_filename)
                sample_element.set("path", xml_sample_path)

                # Root note (MIDI note number)
                root_note_val = sample_model.midi_pitch
                root_note_str = str(root_note_val) if root_note_val is not None else "60" # Default to C3 (MIDI 60)
                sample_element.set("rootNote", root_note_str)

                # Key range (loKey, hiKey)
                lo_key_str = root_note_str
                hi_key_str = root_note_str
                if sample_model.sample_mapping_items:
                    # Assuming the first mapping item dictates the key range for this sample.
                    # More complex logic might be needed if multiple items or complex mappings exist.
                    mapping_item = sample_model.sample_mapping_items[0]
                    if mapping_item.key_range_start is not None:
                        lo_key_str = str(mapping_item.key_range_start)
                    if mapping_item.key_range_end is not None:
                        hi_key_str = str(mapping_item.key_range_end)
                
                sample_element.set("loKey", lo_key_str)
                sample_element.set("hiKey", hi_key_str)

                # Velocity range (loVel, hiVel) - defaults to full range
                lo_vel_str = "0"
                hi_vel_str = "127"
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
        """Creates the <effects> XML element.

        Currently, this is a placeholder and returns an empty <effects> tag,
        as effects definition is not yet implemented.

        Returns:
            The `ET.Element` for the <effects> section.
        """
        effects_element = ET.Element("effects")
        # Example: ET.SubElement(effects_element, "effect", type="reverb", wetLevel="0.5")
        # ET.Comment("Effects can be added here, e.g., reverb, delay.")
        return effects_element
