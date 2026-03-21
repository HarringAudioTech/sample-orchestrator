"""
Defines the QualityControlStage for audio processing pipelines.

This stage evaluates sliced samples for quality issues (clipping, silence,
DC offset, low SNR) and annotates or filters them based on configurable
thresholds.
"""

import json
import logging
from typing import Dict, Any, List, Optional

import numpy as np
import librosa

from src.core.processing_stages import AudioProcessingStage
from src.core.stage_runner import register_stage
from src.core.sample_quality import SampleQualityAnalyzer, SampleQualityReport
from src.database.models import SampleModel, SampleStatus
from src.utils.audio_utils import is_test_environment

logger = logging.getLogger(__name__)


class QualityControlStage(AudioProcessingStage):
    """
    A processing stage that evaluates audio sample quality after slicing.

    For each sample in the input list, this stage:
    1. Loads the audio file
    2. Runs quality analysis (clipping, DC offset, silence, SNR, dynamic range)
    3. Annotates the sample dict with quality metrics
    4. Optionally rejects samples below a quality threshold
    5. Updates sample status in the database

    Samples that fail quality checks have their status set to "failed" and
    are excluded from the output (unless reject_below_threshold is False).
    """

    @property
    def name(self) -> str:
        return "quality_control"

    @property
    def description(self) -> str:
        return "Evaluates sample quality and filters out low-quality samples."

    @property
    def input_type(self) -> str:
        return "list_of_sample_data"

    @property
    def output_type(self) -> str:
        return "list_of_sample_data"

    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "min_quality_score": 0.5,
            "reject_below_threshold": True,
            "silence_threshold_db": -60.0,
            "dc_offset_threshold": 0.01,
            "clipping_threshold": 0.99,
            "min_dynamic_range_db": 6.0,
            "min_snr_db": 10.0,
            "target_sr": 44100,
        }

    def process(
        self,
        data: List[Dict[str, Any]],
        params: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Evaluate quality of each sample and filter/annotate results.

        Args:
            data: List of sample data dicts (from slicing stage).
                  Each dict must have 'file_path'.
            params: Quality control parameters.
            context: Optional context with db_session for status updates.

        Returns:
            List of sample data dicts, annotated with quality metrics.
            Samples below quality threshold are excluded if reject_below_threshold is True.
        """
        if params is None:
            params = {}

        merged_params = self.default_params.copy()
        merged_params.update(params)

        min_quality = merged_params["min_quality_score"]
        reject = merged_params["reject_below_threshold"]
        target_sr = merged_params["target_sr"]

        analyzer = SampleQualityAnalyzer(
            silence_threshold_db=merged_params["silence_threshold_db"],
            dc_offset_threshold=merged_params["dc_offset_threshold"],
            clipping_threshold=merged_params["clipping_threshold"],
            min_dynamic_range_db=merged_params["min_dynamic_range_db"],
            min_snr_db=merged_params["min_snr_db"],
        )

        db_session = context.get("db_session") if context else None

        passed_samples = []
        rejected_count = 0

        for sample_data in data:
            file_path = sample_data.get("file_path")
            if not file_path:
                logger.warning("Sample data missing file_path, skipping QC")
                passed_samples.append(sample_data)
                continue

            # Run quality analysis
            report = self._analyze_sample(analyzer, file_path, target_sr)

            # Annotate sample with quality metrics
            sample_data["quality_score"] = report.quality_score
            sample_data["quality_report"] = report.to_dict()

            if report.quality_score < min_quality and reject:
                # Mark as failed
                sample_data["status"] = "failed"
                sample_data["quality_rejected"] = True
                rejected_count += 1

                self._update_sample_status(
                    db_session, sample_data, SampleStatus.FAILED, report
                )

                logger.info(
                    f"Rejected sample {file_path}: "
                    f"quality={report.quality_score:.3f} < {min_quality}"
                )
            else:
                sample_data["quality_rejected"] = False
                passed_samples.append(sample_data)

                self._update_sample_metadata(db_session, sample_data, report)

                if report.issues:
                    logger.debug(
                        f"Sample {file_path} passed QC "
                        f"(score={report.quality_score:.3f}) "
                        f"with {len(report.issues)} warnings"
                    )

        total = len(data)
        passed = len(passed_samples)
        logger.info(
            f"Quality control: {passed}/{total} samples passed "
            f"({rejected_count} rejected)"
        )

        return passed_samples

    def _analyze_sample(
        self,
        analyzer: SampleQualityAnalyzer,
        file_path: str,
        target_sr: int,
    ) -> SampleQualityReport:
        """Load and analyze a single sample file."""
        if is_test_environment():
            return analyzer.analyze_file(file_path, target_sr)

        try:
            return analyzer.analyze_file(file_path, target_sr)
        except Exception as e:
            logger.error(f"QC analysis failed for {file_path}: {e}")
            report = SampleQualityReport()
            report.quality_score = 0.0
            report.issues.append(f"Analysis failed: {str(e)}")
            return report

    def _update_sample_status(
        self,
        db_session,
        sample_data: Dict[str, Any],
        status: SampleStatus,
        report: SampleQualityReport,
    ) -> None:
        """Update sample status in the database."""
        if db_session is None:
            return

        sample_id = sample_data.get("id")
        if sample_id is None:
            return

        try:
            sample = db_session.get(SampleModel, sample_id)
            if sample:
                sample.status = status.value
                # Merge quality report into existing metadata
                existing_meta = {}
                if sample.metadata_json:
                    try:
                        existing_meta = json.loads(sample.metadata_json)
                    except (json.JSONDecodeError, TypeError):
                        pass
                existing_meta["quality_report"] = report.to_dict()
                sample.metadata_json = json.dumps(existing_meta)

                if not is_test_environment():
                    db_session.commit()
                else:
                    db_session.flush()
        except Exception as e:
            logger.error(f"Failed to update sample {sample_id} status: {e}")
            try:
                db_session.rollback()
            except Exception:
                pass

    def _update_sample_metadata(
        self,
        db_session,
        sample_data: Dict[str, Any],
        report: SampleQualityReport,
    ) -> None:
        """Add quality report to sample metadata in the database."""
        if db_session is None:
            return

        sample_id = sample_data.get("id")
        if sample_id is None:
            return

        try:
            sample = db_session.get(SampleModel, sample_id)
            if sample:
                existing_meta = {}
                if sample.metadata_json:
                    try:
                        existing_meta = json.loads(sample.metadata_json)
                    except (json.JSONDecodeError, TypeError):
                        pass
                existing_meta["quality_report"] = report.to_dict()
                sample.metadata_json = json.dumps(existing_meta)

                if not is_test_environment():
                    db_session.commit()
                else:
                    db_session.flush()
        except Exception as e:
            logger.error(f"Failed to update sample {sample_id} metadata: {e}")
            try:
                db_session.rollback()
            except Exception:
                pass


# Register the stage
try:
    register_stage(QualityControlStage)
except Exception as e:
    logger.critical(f"Failed to register QualityControlStage: {e}", exc_info=True)
