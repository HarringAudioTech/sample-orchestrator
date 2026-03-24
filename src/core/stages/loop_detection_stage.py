"""
Defines the LoopDetectionStage for audio processing pipelines.

This stage detects multiple candidate loops from a larger audio segment,
scores them using heuristics, and selects the best N candidates.
"""

import dataclasses
import logging
from typing import Dict, Any, List, Optional

from src.core.processing_stages import (
    AudioProcessingStage,
    DATA_TYPE_FILE_PATH,
    register_stage,
)
from src.core.loop_evaluator import LoopEvaluator

logger = logging.getLogger(__name__)


class LoopDetectionStage(AudioProcessingStage):
    """
    A processing stage that detects and scores multiple candidate loops.

    Input:  file path to an audio file
    Output: list of slice-point dicts (same format as SlicePlanningStage output)
            sorted by score, with loop scoring metadata attached.
    """

    @property
    def name(self) -> str:
        return "loop_detection"

    @property
    def description(self) -> str:
        return "Detects and scores multiple candidate loops from audio"

    @property
    def input_type(self) -> str:
        return DATA_TYPE_FILE_PATH

    @property
    def output_type(self) -> str:
        return "slice_points"

    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "max_candidates": 5,
            "min_loop_duration": 0.5,
            "max_loop_duration": 32.0,
            "min_score": 0.3,
            "overlap_threshold": 0.5,
            "weights": None,
        }

    def process(
        self,
        data: str,
        params: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Detect loops, score them, and return the best candidates as slice points.

        Args:
            data: Path to an audio file.
            params: Processing parameters (see default_params).
            context: Optional context dict; the full LoopDetectionResult is
                     stored under context['loop_detection_result'].

        Returns:
            List of slice-point dicts compatible with downstream stages::

                [{'start_time': float, 'end_time': float, 'type': 'loop',
                  'metadata': {'confidence': float, 'source': 'loop_detection',
                               'loop_scores': dict, 'rank': int}}]
        """
        if params is None:
            params = {}

        merged = self.default_params.copy()
        merged.update(params)

        evaluator = LoopEvaluator(
            weights=merged.get("weights"),
            min_loop_duration=merged["min_loop_duration"],
            max_loop_duration=merged["max_loop_duration"],
        )

        result = evaluator.evaluate(
            audio_path=data,
            n=merged["max_candidates"],
            min_score=merged["min_score"],
            overlap_threshold=merged["overlap_threshold"],
        )

        # Stash the full result in context for downstream consumers
        if context is not None:
            context["loop_detection_result"] = result

        if result.issues:
            for issue in result.issues:
                logger.info("Loop detection: %s", issue)

        # Convert selected candidates to the standard slice-point format
        slice_points: List[Dict[str, Any]] = []
        for sc in result.selected_candidates:
            slice_points.append({
                "start_time": sc.candidate.start_time,
                "end_time": sc.candidate.end_time,
                "type": "loop",
                "metadata": {
                    "confidence": sc.overall_score,
                    "source": "loop_detection",
                    "loop_scores": dataclasses.asdict(sc.scores),
                    "rank": sc.rank,
                    "duration_bars": sc.candidate.duration_bars,
                    "bpm": sc.candidate.bpm,
                },
            })

        return slice_points


# Register the stage when this module is imported
register_stage(LoopDetectionStage)
