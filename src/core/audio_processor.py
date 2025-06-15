"""
Core audio processing utilities.
"""
import os
from typing import Tuple, Optional # Added Optional

import numpy as np # type: ignore # pylint: disable=import-error
import soundfile # type: ignore # For dummy file creation in main, pylint: disable=import-error

# pylint: disable=import-error
try:
    from src.core.vocal_chop_evaluator import (
        VocalChopEvaluator,
        VocalChopIdealCharacteristics,
        VocalChopEvaluationResult,
    )
    from src.core.stages.vocal_chop_perfection_stage import VocalChopPerfectionWorkflow
except ImportError:
    # Fallback for direct execution or different project structure
    from vocal_chop_evaluator import ( # type: ignore
        VocalChopEvaluator,
        VocalChopIdealCharacteristics,
        VocalChopEvaluationResult,
    )
    from stages.vocal_chop_perfection_stage import VocalChopPerfectionWorkflow # type: ignore
# pylint: enable=import-error

# pylint: disable=too-few-public-methods
class AudioProcessor:
    """
    Provides methods for processing audio files, including specialized
    workflows like vocal chop evaluation and perfection.
    """

    def __init__(self):
        # Initialization for the processor, if any shared resources are needed.
        pass

    def process_vocal_chop(
        self,
        file_path: str,
        output_dir: str,
        ideal_characteristics: Optional[VocalChopIdealCharacteristics] = None,
    ) -> Tuple[str, str, VocalChopEvaluationResult]:
        """
        Evaluates and attempts to "perfect" a vocal chop audio file.

        Args:
            file_path: Path to the input vocal chop audio file.
            output_dir: Directory where the perfected file and intermediate
                        processing files will be stored.
            ideal_characteristics: Optional custom ideal characteristics for evaluation.
                                   If None, default characteristics will be used.

        Returns:
            A tuple containing:
                - Path to the final "perfected" audio file.
                - Path to the directory containing intermediate processing files.
                - The VocalChopEvaluationResult object.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Input audio file not found: {file_path}")

        os.makedirs(output_dir, exist_ok=True)
        print(f"Ensured output directory exists: {output_dir}")

        # 1. Evaluation
        if ideal_characteristics is None:
            ideal_chars = VocalChopIdealCharacteristics()
        else:
            ideal_chars = ideal_characteristics

        evaluator = VocalChopEvaluator(ideal_chars)
        print(f"Evaluating vocal chop file: {file_path}...")
        evaluation_result = evaluator.evaluate(file_path)

        print("\n--- Evaluation Issues ---")
        if evaluation_result.issues:
            for issue_item in evaluation_result.issues: # Renamed 'issue' to 'issue_item'
                print(f"- {issue_item}")
        else:
            print("No major issues found during initial evaluation.")
        print("-------------------------\n")

        # 2. Perfection Workflow
        print(f"Starting perfection workflow for: {file_path}...")
        workflow = VocalChopPerfectionWorkflow(file_path, evaluation_result)
        # The workflow's run method already creates a subdirectory within output_dir
        perfected_file_path, intermediates_dir_path = workflow.run(output_dir)

        print("Perfection workflow completed.") # Removed f-string
        print(f"Perfected file: {perfected_file_path}")
        print(f"Intermediates in: {intermediates_dir_path}")

        return perfected_file_path, intermediates_dir_path, evaluation_result


if __name__ == "__main__":
    print("Running AudioProcessor example for vocal chop processing...")

    # Create a dummy vocal chop audio file for testing
    DUMMY_FILE_NAME = "dummy_vocal_chop.wav" # UPPER_CASE
    DUMMY_OUTPUT_DIR = "temp_vocal_chop_output" # UPPER_CASE
    SR = 44100 # UPPER_CASE

    # Create some stabs with silence in between
    STAB_DURATION_SAMPLES = int(0.2 * SR)
    SILENCE_DURATION_SAMPLES = int(0.1 * SR)

    stab1 = (
        np.sin(np.linspace(0, 200 * 2 * np.pi, STAB_DURATION_SAMPLES)) * 0.5
    )
    stab2 = (
        np.sin(np.linspace(0, 300 * 2 * np.pi, STAB_DURATION_SAMPLES)) * 0.5
    )
    silence = np.zeros(SILENCE_DURATION_SAMPLES)

    dummy_audio_data = np.concatenate([stab1, silence, stab2]).astype(np.float32)

    try:
        soundfile.write(DUMMY_FILE_NAME, dummy_audio_data, SR)
        print(f"Created dummy audio file: {DUMMY_FILE_NAME}")

        processor = AudioProcessor()

        perfected_file, intermediates_dir, eval_res = processor.process_vocal_chop(
            file_path=DUMMY_FILE_NAME,
            output_dir=DUMMY_OUTPUT_DIR,
        )

        print("\n--- Final Evaluation Result (Post-Processing) ---")
        print(f"Overall Score (placeholder): {eval_res.overall_idealness_score}")
        print("Issues/Log from evaluation and processing stages:")
        for issue_item in eval_res.issues: # Renamed 'issue'
            print(f"- {issue_item}")
        print("Stabs information after processing:")
        for i, stab in enumerate(eval_res.stabs):
            print(
                f"  Stab {i+1}: Start: {stab.start_sample}, End: {stab.end_sample}, "
                f"Duration: {stab.duration_ms:.2f}ms, Label: '{stab.label}'"
            ) # Line broken for length
            if stab.issues:
                for stab_issue in stab.issues:
                    print(f"    - Issue: {stab_issue}")

    except Exception as e: # pylint: disable=broad-except
        print(f"An error occurred during the example run: {e}")
    finally:
        print(f"\nExample finished. Check '{DUMMY_OUTPUT_DIR}' for results.")
        print(
            f"To cleanup, manually delete '{DUMMY_FILE_NAME}' and '{DUMMY_OUTPUT_DIR}'."
        )
