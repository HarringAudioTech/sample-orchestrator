"""
Amanuensis integration for Sample Orchestrator.

This module provides a service wrapper for generating MIDI loops using the Amanuensis library.
It handles MIDI generation, quantization for looping, and saving to the project's data directory and database.
"""

from __future__ import annotations
import os
import json
import logging
import base64
from pathlib import Path
from fractions import Fraction
from datetime import datetime, timezone
from typing import Any, List, Optional, Dict, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Amanuensis imports
from amanuensis.services.render_service import RenderService
from amanuensis.services.export_service import ExportService
from amanuensis.ir import ScoreIR, NoteEvent, Part, ControlEvent, RationalSpan

from src.database.models import MidiFileModel, MidiCaptureSessionModel, MidiDeviceModel
from src.core.project_manager import ProjectManager

logger = logging.getLogger(__name__)

class AmanuensisService:
    """
    Service for generating MIDI loops and phrases using Amanuensis.
    """

    def __init__(self, db: Session):
        """
        Initializes the AmanuensisService.

        Args:
            db (Session): The SQLAlchemy database session.
        """
        self.db = db
        self.render_svc = RenderService()
        self.export_svc = ExportService()

    def generate_monophonic_loop(
        self,
        project_id: int,
        label: str,
        engine_id: str = "bass",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generates a monophonic MIDI loop.

        Args:
            project_id (int): The ID of the project.
            label (str): A label for the generated loop.
            engine_id (str): The Amanuensis engine to use (e.g., 'bass', 'fretboard').
            **kwargs: Additional parameters for MIDI generation.

        Returns:
            Dict[str, Any]: Metadata about the generated MIDI loop.
        """
        return self._render_and_save(project_id, label, engine_id, **kwargs)

    def generate_polyphonic_loop(
        self,
        project_id: int,
        label: str,
        engine_id: str = "kapellmeister",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generates a polyphonic MIDI loop.

        Args:
            project_id (int): The ID of the project.
            label (str): A label for the generated loop.
            engine_id (str): The Amanuensis engine to use (e.g., 'kapellmeister').
            **kwargs: Additional parameters for MIDI generation.

        Returns:
            Dict[str, Any]: Metadata about the generated MIDI loop.
        """
        return self._render_and_save(project_id, label, engine_id, **kwargs)

    def generate_variations(
        self,
        project_id: int,
        label: str,
        engine_id: str,
        count: int = 4,
        base_seed: int = 42,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Generates a set of variations for a MIDI loop.

        Args:
            project_id (int): The ID of the project.
            label (str): Base label for the variations.
            engine_id (str): The engine to use.
            count (int): Number of variations to generate.
            base_seed (int): Base seed for generation.
            **kwargs: Generation parameters.

        Returns:
            List[Dict[str, Any]]: List of metadata for each generated variation.
        """
        variations = []
        for i in range(count):
            var_label = f"{label}_var{i+1}"
            var_seed = base_seed + i
            variations.append(self._render_and_save(project_id, var_label, engine_id, seed=var_seed, **kwargs))
        return variations

    def _get_midi_dir(self, project_id: int) -> Path:
        """
        Ensures the MIDI directory exists for a project and returns its path.
        """
        project_path = ProjectManager.get_project_dir(project_id)
        midi_dir = project_path / "midi"
        midi_dir.mkdir(parents=True, exist_ok=True)
        return midi_dir

    def _render_and_save(
        self,
        project_id: int,
        label: str,
        engine_id: str,
        key: str = "C",
        meter: str = "4/4",
        tempo: float = 120.0,
        bars: int = 4,
        seed: int = 42,
        chords: Optional[List[Dict[str, str]]] = None,
        engine_options: Optional[Dict[str, Any]] = None,
        quantize_grid: Optional[Fraction] = Fraction(1, 4),
        loop_strict: bool = True,
        max_tweak_passes: int = 2,
        min_loop_fitness: float = 0.7,
        export_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Internal method to render MIDI and save it to disk and DB.
        """
        duration_beats = self._bars_to_beats(bars, meter)
        loop_dur = Fraction(duration_beats, 4)

        best_score: ScoreIR | None = None
        best_fitness = -1.0
        best_dropped = 0
        best_clipped = 0
        final_attempts = 0

        logger.info(f"Generating MIDI loop '{label}' with engine '{engine_id}' for project {project_id}")

        for attempt in range(1 + max_tweak_passes):
            attempt_seed = seed + attempt * 1000
            final_attempts = attempt + 1

            try:
                score, _ = self.render_svc.render(
                    engine_id,
                    engine_options=engine_options,
                    key=key,
                    meter=meter,
                    tempo=tempo,
                    duration_beats=duration_beats,
                    seed=attempt_seed,
                    chords=chords
                )

                dropped = 0
                clipped = 0
                if quantize_grid or loop_strict:
                    score, dropped, clipped = self._quantize_to_loop(
                        score, loop_dur, quantize_grid, loop_strict
                    )

                fitness = self._score_loop_fitness(score, loop_dur)

                if fitness > best_fitness:
                    best_score = score
                    best_fitness = fitness
                    best_dropped = dropped
                    best_clipped = clipped

                if fitness >= min_loop_fitness:
                    break
            except Exception as e:
                logger.error(f"Error during Amanuensis rendering attempt {attempt}: {e}")
                if attempt == max_tweak_passes and best_score is None:
                    raise

        if best_score is None:
            raise RuntimeError(f"Failed to generate MIDI loop '{label}' after {final_attempts} attempts.")

        # Export to file
        midi_dir = self._get_midi_dir(project_id)
        filename = f"{label}_s{seed}.mid"
        
        # Default HW export settings adapted from batch_loops.py
        hw_export = {
            "uniform_velocity": 100,
            "include_tempo_track": False,
            "strip_pitch_bends": False,
            "inject_expression": False,
            "apply_articulations": False,
            "auto_program_change": False,
        }
        if export_options:
            hw_export.update(export_options)

        result, _, _ = self.export_svc.export_midi(
            best_score, midi_dir, filename, **hw_export
        )

        # Save to Database
        try:
            # 1. Ensure "Amanuensis" device exists
            amanuensis_device = self.db.query(MidiDeviceModel).filter(MidiDeviceModel.name == "Amanuensis").first()
            if not amanuensis_device:
                amanuensis_device = MidiDeviceModel(
                    name="Amanuensis", 
                    description="Internal generative MIDI engine",
                    is_available=True
                )
                self.db.add(amanuensis_device)
                self.db.flush()

            # 2. Create a session for this generation
            # We use a timestamp to make it unique or just group by label
            session_name = f"Amanuensis Generation {label} {datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            session = MidiCaptureSessionModel(
                project_id=project_id,
                name=session_name,
                status="completed",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc)
            )
            self.db.add(session)
            self.db.flush()

            # 3. Save MIDI data to DB
            midi_path = midi_dir / filename
            with open(midi_path, "rb") as f:
                midi_data = f.read()
                
            midi_file_record = MidiFileModel(
                capture_session_id=session.id,
                device_id=amanuensis_device.id,
                channel=0,
                file_data=base64.b64encode(midi_data).decode("utf-8")
            )
            self.db.add(midi_file_record)
            self.db.commit()
            
            logger.info(f"Successfully generated and saved MIDI loop '{label}' (ID: {midi_file_record.id})")

            return {
                "project_id": project_id,
                "label": label,
                "filename": filename,
                "file_path": str(midi_path),
                "fitness": round(best_fitness, 4),
                "attempts": final_attempts,
                "midi_file_id": midi_file_record.id,
                "session_id": session.id,
                "events_dropped": best_dropped,
                "events_clipped": best_clipped,
                "tempo": tempo,
                "key": key,
                "meter": meter,
                "bars": bars,
                "duration_beats": duration_beats
            }

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error while saving generated MIDI: {e}")
            raise

    # --- Helper methods adapted from amanuensis session_output scripts ---

    def _bars_to_beats(self, bars: int, meter: str) -> int:
        """Convert bar count + meter string to quarter-note beats."""
        num_str, den_str = meter.split("/")
        numerator = int(num_str)
        denominator = int(den_str)
        beats_per_bar = numerator * 4 // denominator
        return bars * beats_per_bar

    def _score_loop_fitness(self, score: ScoreIR, loop_dur: Fraction) -> float:
        """Score how well a clip loops (0.0-1.0)."""
        if not score.parts:
            return 0.0

        all_notes: list[NoteEvent] = []
        for part in score.parts:
            for ev in part.events:
                if isinstance(ev, NoteEvent):
                    all_notes.append(ev)

        if not all_notes:
            return 0.0

        # Boundary cleanliness (0.4)
        clean_count = sum(
            1 for n in all_notes
            if n.span.start + n.span.duration <= loop_dur
        )
        boundary_score = clean_count / len(all_notes)

        # Downbeat presence (0.3)
        near_zero = Fraction(1, 16)
        has_downbeat = any(n.span.start <= near_zero for n in all_notes)
        downbeat_score = 1.0 if has_downbeat else 0.0

        # Tail fill (0.3)
        tail_start = loop_dur * Fraction(3, 4)
        tail_notes = [
            n for n in all_notes
            if n.span.start + n.span.duration > tail_start
            and n.span.start < loop_dur
        ]
        if loop_dur > 0:
            tail_coverage = min(1.0, len(tail_notes) / max(1, len(all_notes) // 4))
        else:
            tail_coverage = 0.0

        return (
            0.4 * boundary_score
            + 0.3 * downbeat_score
            + 0.3 * tail_coverage
        )

    def _quantize_to_loop(
        self,
        score: ScoreIR,
        loop_dur: Fraction,
        grid: Fraction | None,
        strict: bool,
    ) -> tuple[ScoreIR, int, int]:
        """Quantize events to loop boundaries."""
        events_dropped = 0
        events_clipped = 0
        new_parts: list[Part] = []

        for part in score.parts:
            new_events = []
            for ev in part.events:
                if isinstance(ev, NoteEvent):
                    start = ev.span.start
                    dur = ev.span.duration

                    if grid is not None and grid > 0:
                        start = self._snap_to_grid(start, grid)

                    end = start + dur

                    if strict and end > loop_dur:
                        end = loop_dur
                        events_clipped += 1
                    elif end > loop_dur and grid and end - loop_dur < grid:
                        end = loop_dur
                        events_clipped += 1

                    new_dur = end - start
                    if new_dur <= 0:
                        events_dropped += 1
                        continue

                    if start != ev.span.start or new_dur != ev.span.duration:
                        new_span = RationalSpan(start=start, duration=new_dur)
                        new_events.append(ev.model_copy(update={"span": new_span}))
                    else:
                        new_events.append(ev)

                elif isinstance(ev, ControlEvent):
                    if strict and ev.span.start >= loop_dur:
                        events_dropped += 1
                        continue
                    new_events.append(ev)
                else:
                    new_events.append(ev)

            new_parts.append(part.model_copy(update={"events": new_events}))

        new_score = score.model_copy(update={"parts": new_parts})
        return new_score, events_dropped, events_clipped

    def _snap_to_grid(self, value: Fraction, grid: Fraction) -> Fraction:
        """Snap a Fraction value to the nearest grid point."""
        steps = round(value / grid)
        return grid * steps
