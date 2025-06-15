"""
Core audio processing utilities.
"""
import os
import numpy as np
import soundfile # For dummy file creation in main
from typing import Tuple

try:
    from src.core.vocal_chop_evaluator import VocalChopEvaluator, VocalChopIdealCharacteristics, VocalChopEvaluationResult
    from src.core.stages.vocal_chop_perfection_stage import VocalChopPerfectionWorkflow
except ImportError:
    # Fallback for direct execution or different project structure
    from vocal_chop_evaluator import VocalChopEvaluator, VocalChopIdealCharacteristics, VocalChopEvaluationResult
    from stages.vocal_chop_perfection_stage import VocalChopPerfectionWorkflow


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
        ideal_characteristics: Optional[VocalChopIdealCharacteristics] = None
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
            for issue in evaluation_result.issues:
                print(f"- {issue}")
        else:
            print("No major issues found during initial evaluation.")
        print("-------------------------\n")

        # 2. Perfection Workflow
        print(f"Starting perfection workflow for: {file_path}...")
        workflow = VocalChopPerfectionWorkflow(file_path, evaluation_result)
        # The workflow's run method already creates a subdirectory within output_dir
        perfected_file_path, intermediates_dir_path = workflow.run(output_dir)

        print(f"Perfection workflow completed.")
        print(f"Perfected file: {perfected_file_path}")
        print(f"Intermediates in: {intermediates_dir_path}")

        return perfected_file_path, intermediates_dir_path, evaluation_result


if __name__ == '__main__':
    print("Running AudioProcessor example for vocal chop processing...")

    # Create a dummy vocal chop audio file for testing
    dummy_file_name = "dummy_vocal_chop.wav"
    dummy_output_dir = "temp_vocal_chop_output"
    sr = 44100

    # Create some stabs with silence in between
    stab_duration_samples = int(0.2 * sr) # 200ms stabs
    silence_duration_samples = int(0.1 * sr) # 100ms silence

    stab1 = np.sin(np.linspace(0, 200 * 2 * np.pi, stab_duration_samples)) * 0.5 # A tone
    stab2 = np.sin(np.linspace(0, 300 * 2 * np.pi, stab_duration_samples)) * 0.5 # Different tone
    silence = np.zeros(silence_duration_samples)

    dummy_audio_data = np.concatenate([stab1, silence, stab2]).astype(np.float32)

    try:
        soundfile.write(dummy_file_name, dummy_audio_data, sr)
        print(f"Created dummy audio file: {dummy_file_name}")

        processor = AudioProcessor()

        # Define custom ideal characteristics if needed for testing
        # custom_ideals = VocalChopIdealCharacteristics()
        # custom_ideals.min_silence_duration_ms = 150

        perfected_file, intermediates_dir, eval_res = processor.process_vocal_chop(
            file_path=dummy_file_name,
            output_dir=dummy_output_dir
            # ideal_characteristics=custom_ideals # Uncomment to use custom ideals
        )

        print("\n--- Final Evaluation Result (Post-Processing) ---")
        print(f"Overall Score (placeholder): {eval_res.overall_idealness_score}")
        print("Issues/Log from evaluation and processing stages:")
        for issue in eval_res.issues:
            print(f"- {issue}")
        print("Stabs information after processing:")
        for i, stab in enumerate(eval_res.stabs):
            print(f"  Stab {i+1}: Start: {stab.start_sample}, End: {stab.end_sample}, Duration: {stab.duration_ms:.2f}ms, Label: '{stab.label}'")
            if stab.issues:
                for stab_issue in stab.issues:
                    print(f"    - Issue: {stab_issue}")

    except Exception as e:
        print(f"An error occurred during the example run: {e}")
    finally:
        # Clean up the dummy file and output directory
        # if os.path.exists(dummy_file_name):
        #     os.remove(dummy_file_name)
        # if os.path.exists(dummy_output_dir):
        #     shutil.rmtree(dummy_output_dir) # Use with caution
        print(f"\nExample finished. Check '{dummy_output_dir}' for results.")
        print(f"To cleanup, manually delete '{dummy_file_name}' and '{dummy_output_dir}'.")
