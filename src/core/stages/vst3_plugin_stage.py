"""
Defines the VST3PluginStage for audio processing pipelines.
This stage allows hosting VST3 plugins using the pedalboard library.
"""

import logging
import os
import numpy as np
from typing import Any, Dict, Optional
from pedalboard import Pedalboard, VST3Plugin

from src.core.processing_stages import AudioProcessingStage, DATA_TYPE_AUDIO_BUFFER_MONO
from src.core.stage_runner import register_stage

# Logger for this stage
logger = logging.getLogger(__name__)


class VST3PluginStage(AudioProcessingStage):
    """
    An audio processing stage that hosts a VST3 plugin.
    
    Parameters:
        plugin_path (str): Absolute path to the .vst3 file/bundle.
        plugin_settings (Dict[str, float]): Dictionary of parameter names and values.
    """

    @property
    def name(self) -> str:
        return "vst3_plugin"

    @property
    def description(self) -> str:
        return "Hosts and processes audio through a VST3 plugin using pedalboard."

    @property
    def input_type(self) -> str:
        return DATA_TYPE_AUDIO_BUFFER_MONO

    @property
    def output_type(self) -> str:
        return DATA_TYPE_AUDIO_BUFFER_MONO

    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "plugin_path": "",
            "plugin_settings": {},
        }

    def process(
        self,
        data: np.ndarray,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """Processes audio through a VST3 plugin.

        Args:
            data: The input mono audio buffer (NumPy array).
            params: Parameters including 'plugin_path' and 'plugin_settings'.
            context: Shared context, expected to contain 'sample_rate'.

        Returns:
            The processed mono audio buffer (NumPy array).
        """
        if not isinstance(data, np.ndarray):
            raise TypeError(f"Input data for {self.name} must be a NumPy array.")

        plugin_path = params.get("plugin_path")
        if not plugin_path:
            logger.warning(f"[{self.name}] No plugin_path provided. Passing audio through.")
            return data

        if not os.path.exists(plugin_path):
            logger.error(f"[{self.name}] Plugin path does not exist: {plugin_path}")
            raise FileNotFoundError(f"VST3 plugin not found at: {plugin_path}")

        sr = 44100
        if context and "sample_rate" in context:
            sr = context["sample_rate"]

        try:
            logger.info(f"[{self.name}] Loading VST3 plugin: {plugin_path}")
            plugin = VST3Plugin(plugin_path)
            
            # Apply settings
            settings = params.get("plugin_settings", {})
            for param_name, value in settings.items():
                if hasattr(plugin, param_name):
                    setattr(plugin, param_name, value)
                    logger.debug(f"[{self.name}] Set plugin parameter '{param_name}' to {value}")
                else:
                    logger.warning(f"[{self.name}] Plugin does not have parameter: {param_name}")

            # Run the plugin
            with Pedalboard([plugin]) as board:
                # Pedalboard expects (num_channels, num_samples) or (num_samples,)
                # Our data is mono (num_samples,)
                processed = board(data, sr)
                
            logger.info(f"[{self.name}] Successfully processed audio through {plugin.plugin_name}")
            return processed

        except Exception as e:
            logger.error(f"[{self.name}] Error during VST3 processing: {e}", exc_info=True)
            raise


# Register the stage
try:
    register_stage(VST3PluginStage)
except Exception as e:
    logger.critical(f"Failed to register VST3PluginStage: {e}", exc_info=True)
