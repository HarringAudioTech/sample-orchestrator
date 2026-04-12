import logging
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

import mido
from sqlalchemy.orm import Session

from src.core.amanuensis_service import AmanuensisService
from src.core.audio_recorder import AudioRecorder
from src.core.patchlab_service import PatchlabService
from src.core.project_manager import ProjectManager
from src.database.models import RecordingModel, SampleModel, SampleType, SampleStatus

logger = logging.getLogger(__name__)

class LoopOrchestrator:
    """
    Coordinates MIDI generation via Amanuensis, synth control via Patchlab,
    and audio recording via PyAudio.
    """

    def __init__(self, db: Session):
        """
        Initializes the LoopOrchestrator.

        Args:
            db (Session): Database session.
        """
        self.db = db
        self.amanuensis = AmanuensisService(db)
        self.recorder = AudioRecorder()
        self.patchlab = PatchlabService()

    def capture_single_loop(
        self,
        project_id: int,
        label: str,
        engine_id: str,
        midi_port: str,
        audio_device_index: Optional[int] = None,
        patch_data: Optional[Dict[str, Any]] = None,
        capture_tail_seconds: float = 2.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generates a MIDI loop, plays it to a synth, and records the audio output.

        Args:
            project_id (int): Project ID.
            label (str): Label for the loop.
            engine_id (str): Amanuensis engine ID.
            midi_port (str): MIDI output port name.
            audio_device_index (int): Audio input device index.
            patch_data (Dict): Optional patch data to load via Patchlab.
            capture_tail_seconds (float): Time to record after MIDI finishes.
            **kwargs: Arguments for Amanuensis rendering.

        Returns:
            Dict[str, Any]: Metadata about the captured loop.
        """
        # 1. Generate MIDI
        midi_meta = self.amanuensis.generate_monophonic_loop(project_id, label, engine_id, **kwargs)
        midi_path = Path(midi_meta["file_path"])

        # 2. Setup Synth (if patch data provided)
        if patch_data:
            self.patchlab.load_patch(patch_data)

        # 3. Start Recording
        output_wav = midi_path.with_suffix(".wav")
        logger.info(f"Starting audio capture for '{label}'...")
        self.recorder.start_recording(device_index=audio_device_index)

        # 4. Play MIDI
        try:
            logger.info(f"Playing MIDI to '{midi_port}'...")
            mid = mido.MidiFile(str(midi_path))
            
            with mido.open_output(midi_port) as out_port:
                # Brief pre-roll
                time.sleep(0.5)
                
                for msg in mid.play():
                    out_port.send(msg)
                
                # Capture tail
                logger.info(f"MIDI finished. Capturing tail for {capture_tail_seconds}s...")
                time.sleep(capture_tail_seconds)
        except Exception as e:
            logger.error(f"Error during MIDI playback or capture: {e}")
        finally:
            # 5. Stop Recording
            self.recorder.stop_recording(output_wav)

        # 6. Register in Database
        try:
            recording = RecordingModel(
                project_id=project_id,
                name=label,
                file_path=str(output_wav),
                metadata_json=json.dumps({
                    "tempo": midi_meta["tempo"],
                    "key": midi_meta["key"],
                    "meter": midi_meta["meter"],
                    "engine": engine_id,
                    "midi_file_id": midi_meta["midi_file_id"],
                    "source": "amanuensis_loop"
                })
            )
            self.db.add(recording)
            self.db.flush()

            # Duration in seconds
            duration_sec = (midi_meta["duration_beats"] * 60.0 / midi_meta["tempo"]) + capture_tail_seconds

            sample = SampleModel(
                recording_id=recording.id,
                name=label,
                file_path=str(output_wav),
                sample_type=SampleType.LOOP.value,
                status=SampleStatus.PROCESSED.value,
                duration=duration_sec,
                start_time=0.0,
                metadata_json=json.dumps({
                    "tempo": midi_meta["tempo"],
                    "key": midi_meta["key"],
                    "bars": midi_meta["bars"]
                })
            )
            self.db.add(sample)
            self.db.commit()
            
            logger.info(f"Registered loop '{label}' in DB (Sample ID: {sample.id})")
            
            return {
                "midi": midi_meta,
                "audio_file": str(output_wav),
                "label": label,
                "project_id": project_id,
                "sample_id": sample.id,
                "recording_id": recording.id
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to register loop in DB: {e}")
            raise

    def capture_loop_batch(
        self,
        project_id: int,
        batch_label: str,
        engine_id: str,
        count: int,
        midi_port: str,
        audio_device_index: Optional[int] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Generates and captures a batch of loops (variations).
        """
        results = []
        for i in range(count):
            label = f"{batch_label}_v{i+1}"
            res = self.capture_single_loop(
                project_id, label, engine_id, midi_port, audio_device_index, **kwargs
            )
            results.append(res)
        return results
