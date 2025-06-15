"""
Utility functions and data structures for interacting with libsndfile metadata
via soundfile's CFFI interface (_lib and _ffi).

This module defines Python dataclasses that mirror libsndfile C structures
(like SF_CUES, SF_INSTRUMENT, SF_LOOP_INFO) and provides functions to get/set
these metadata types from/to audio files.
"""
import ctypes
import dataclasses
from typing import List, Tuple, Optional

import soundfile  # type: ignore # pylint: disable=import-error
from soundfile import _lib as sf_lib  # type: ignore # pylint: disable=import-error
from soundfile import _ffi  # type: ignore # pylint: disable=import-error


# Constants for sf_command from soundfile._lib
SFC_GET_LIB_VERSION = sf_lib.SFC_GET_LIB_VERSION
SFC_GET_LOG_INFO = sf_lib.SFC_GET_LOG_INFO
SFC_GET_CURRENT_SF_INFO = sf_lib.SFC_GET_CURRENT_SF_INFO
SFC_GET_NORM_DOUBLE = sf_lib.SFC_GET_NORM_DOUBLE
SFC_GET_NORM_FLOAT = sf_lib.SFC_GET_NORM_FLOAT
SFC_SET_NORM_DOUBLE = sf_lib.SFC_SET_NORM_DOUBLE
SFC_SET_NORM_FLOAT = sf_lib.SFC_SET_NORM_FLOAT
SFC_SET_SCALE_FLOAT_INT_READ = sf_lib.SFC_SET_SCALE_FLOAT_INT_READ
SFC_SET_SCALE_INT_FLOAT_WRITE = sf_lib.SFC_SET_SCALE_INT_FLOAT_WRITE
SFC_GET_SIMPLE_FORMAT_COUNT = sf_lib.SFC_GET_SIMPLE_FORMAT_COUNT
SFC_GET_SIMPLE_FORMAT = sf_lib.SFC_GET_SIMPLE_FORMAT
SFC_GET_FORMAT_INFO = sf_lib.SFC_GET_FORMAT_INFO
SFC_GET_FORMAT_MAJOR_COUNT = sf_lib.SFC_GET_FORMAT_MAJOR_COUNT
SFC_GET_FORMAT_MAJOR = sf_lib.SFC_GET_FORMAT_MAJOR
SFC_GET_FORMAT_SUBTYPE_COUNT = sf_lib.SFC_GET_FORMAT_SUBTYPE_COUNT
SFC_GET_FORMAT_SUBTYPE = sf_lib.SFC_GET_FORMAT_SUBTYPE
SFC_CALC_SIGNAL_MAX = sf_lib.SFC_CALC_SIGNAL_MAX
SFC_CALC_NORM_SIGNAL_MAX = sf_lib.SFC_CALC_NORM_SIGNAL_MAX
SFC_CALC_MAX_ALL_CHANNELS = sf_lib.SFC_CALC_MAX_ALL_CHANNELS
SFC_CALC_NORM_MAX_ALL_CHANNELS = sf_lib.SFC_CALC_NORM_MAX_ALL_CHANNELS
SFC_GET_SIGNAL_MAX = sf_lib.SFC_GET_SIGNAL_MAX
SFC_GET_MAX_ALL_CHANNELS = sf_lib.SFC_GET_MAX_ALL_CHANNELS
SFC_SET_ADD_HEADER_ON_RAW_READ = sf_lib.SFC_SET_ADD_HEADER_ON_RAW_READ
SFC_SET_ADD_HEADER_ON_RAW_WRITE = sf_lib.SFC_SET_ADD_HEADER_ON_RAW_WRITE
SFC_RAW_DATA_NEEDS_ENDSWAP = sf_lib.SFC_RAW_DATA_NEEDS_ENDSWAP
SFC_WAV_AMBISONIC = sf_lib.SFC_WAV_AMBISONIC
SFC_RF64_AUTO_DOWNGRADE = sf_lib.SFC_RF64_AUTO_DOWNGRADE
SFC_SET_VBR_ENCODING_QUALITY = sf_lib.SFC_SET_VBR_ENCODING_QUALITY
SFC_SET_COMPRESSION_LEVEL = sf_lib.SFC_SET_COMPRESSION_LEVEL
SFC_GET_COMPRESSION_LEVEL = sf_lib.SFC_GET_COMPRESSION_LEVEL
SFC_SET_CART_INFO = sf_lib.SFC_SET_CART_INFO
SFC_GET_CART_INFO = sf_lib.SFC_GET_CART_INFO
SFC_SET_BROADCAST_INFO = sf_lib.SFC_SET_BROADCAST_INFO
SFC_GET_BROADCAST_INFO = sf_lib.SFC_GET_BROADCAST_INFO
SFC_GET_INSTRUMENT = sf_lib.SFC_GET_INSTRUMENT
SFC_SET_INSTRUMENT = sf_lib.SFC_SET_INSTRUMENT
SFC_GET_LOOP_INFO = sf_lib.SFC_GET_LOOP_INFO
SFC_SET_LOOP_INFO = sf_lib.SFC_SET_LOOP_INFO
SFC_GET_CUES = (
    sf_lib.SFC_GET_CUES
)
SFC_SET_CUES = (
    sf_lib.SFC_SET_CUES
)

# Loop modes from soundfile._lib
SF_LOOP_NONE = sf_lib.SF_LOOP_NONE
SF_LOOP_FORWARD = sf_lib.SF_LOOP_FORWARD
SF_LOOP_BACKWARD = sf_lib.SF_LOOP_BACKWARD
SF_LOOP_ALTERNATING = sf_lib.SF_LOOP_ALTERNATING


# pylint: disable=too-few-public-methods
class _SFCuePointCTypes(ctypes.Structure):
    """Internal ctypes mirror for SF_CUE_POINT."""
    _fields_ = [
        ("indx", ctypes.c_int),
        ("position", ctypes.c_uint32),
        ("fcc_chunk", ctypes.c_int32),
        ("chunk_start", ctypes.c_int32),
        ("block_start", ctypes.c_int32),
        ("sample_offset", ctypes.c_uint32),
        ("name", ctypes.c_char * 256),
    ]

MAX_CUE_POINTS = 100

class _SFCuesCTypes(ctypes.Structure):
    """Internal ctypes mirror for SF_CUES."""
    _fields_ = [
        (
            "cue_count",
            ctypes.c_uint32,
        ),
        ("cue_points", _SFCuePointCTypes * MAX_CUE_POINTS),
    ]

class _SFInstrumentLoopCTypes(ctypes.Structure):
    """Internal ctypes mirror for SF_INSTRUMENT loop substructure."""
    _fields_ = [
        ("mode", ctypes.c_int),
        ("start", ctypes.c_uint32),
        ("end", ctypes.c_uint32),
        ("count", ctypes.c_uint32),
    ]

class _SFInstrumentInfoCTypes(ctypes.Structure):
    """Internal ctypes mirror for SF_INSTRUMENT."""
    _fields_ = [
        ("gain", ctypes.c_int),
        ("basenote", ctypes.c_char),
        ("detune", ctypes.c_char),
        ("velocity_lo", ctypes.c_char),
        ("velocity_hi", ctypes.c_char),
        ("key_lo", ctypes.c_char),
        ("key_hi", ctypes.c_char),
        ("loop_count", ctypes.c_int),
        ("loops", _SFInstrumentLoopCTypes * 16),
    ]

class _SFLoopInfoCTypes(ctypes.Structure):
    """Internal ctypes mirror for SF_LOOP_INFO."""
    _fields_ = [
        ("time_sig_num", ctypes.c_short),
        ("time_sig_den", ctypes.c_short),
        ("loop_mode", ctypes.c_int),
        ("num_beats", ctypes.c_int),
        ("bpm", ctypes.c_float),
        ("root_key", ctypes.c_int),
        ("future", ctypes.c_int * 6),
    ]
# pylint: enable=too-few-public-methods

# pylint: disable=too-few-public-methods
@dataclasses.dataclass
class SFCuePoint:
    """
    Pythonic representation of a libsndfile SF_CUE_POINT structure.

    Attributes:
        indx: Unique identifier for this cue point.
        position: Position of the cue point in samples from the start of the audio.
        fcc_chunk: Four Character Code of the RIFF chunk containing the cue point.
                   Usually 'data' for cues in the main audio data.
        chunk_start: Start position of the RIFF chunk containing the cue point.
        block_start: Start position of the block containing the cue point.
        sample_offset: Offset of the cue point within the block, in samples.
        name: Name of the cue point (up to 255 bytes + null terminator).
    """
    indx: int = 0
    position: int = 0
    fcc_chunk: int = 0
    chunk_start: int = 0
    block_start: int = 0
    sample_offset: int = 0
    name: bytes = b"\x00" * 256

    @classmethod
    def from_ctypes_struct(cls, ct_struct: _SFCuePointCTypes) -> 'SFCuePoint':
        """Creates an SFCuePoint dataclass instance from a ctypes structure."""
        return cls(
            indx=ct_struct.indx,
            position=ct_struct.position,
            fcc_chunk=ct_struct.fcc_chunk,
            chunk_start=ct_struct.chunk_start,
            block_start=ct_struct.block_start,
            sample_offset=ct_struct.sample_offset,
            name=ct_struct.name,
        )

    def to_ctypes_struct(self) -> _SFCuePointCTypes:
        """Converts this dataclass instance to a ctypes SF_CUE_POINT structure."""
        name_bytes_val = self.name[:255]
        if not name_bytes_val.endswith(b"\x00"):
            name_bytes_val += b"\x00"
        return _SFCuePointCTypes(
            indx=self.indx,
            position=self.position,
            fcc_chunk=self.fcc_chunk,
            chunk_start=self.chunk_start,
            block_start=self.block_start,
            sample_offset=self.sample_offset,
            name=name_bytes_val,
        )

# pylint: disable=too-few-public-methods
@dataclasses.dataclass
class SFLoopInfo:
    """
    Pythonic representation of a libsndfile SF_LOOP_INFO structure.

    Contains information for sampler loops.

    Attributes:
        time_sig_num: Numerator of the time signature (e.g., 3 for 3/4 time).
        time_sig_den: Denominator of the time signature (e.g., 4 for 3/4 time).
        loop_mode: Loop mode (e.g., SF_LOOP_NONE, SF_LOOP_FORWARD). See libsndfile docs.
        num_beats: Number of beats in the loop.
        bpm: Beats per minute of the loop.
        root_key: MIDI root note of the sample (0-127, or -1 if not set).
        future: Reserved for future use by libsndfile.
    """
    time_sig_num: int = 0
    time_sig_den: int = 0
    loop_mode: int = SF_LOOP_NONE
    num_beats: int = 0
    bpm: float = 0.0
    root_key: int = -1
    future: Tuple[int, int, int, int, int, int] = dataclasses.field(
        default_factory=lambda: (0, 0, 0, 0, 0, 0)
    )

    @classmethod
    def from_ctypes_struct(cls, ct_struct: _SFLoopInfoCTypes) -> 'SFLoopInfo':
        """Creates an SFLoopInfo dataclass instance from a ctypes structure."""
        return cls(
            time_sig_num=ct_struct.time_sig_num,
            time_sig_den=ct_struct.time_sig_den,
            loop_mode=ct_struct.loop_mode,
            num_beats=ct_struct.num_beats,
            bpm=ct_struct.bpm,
            root_key=ct_struct.root_key,
            future=tuple(ct_struct.future),
        )

    def to_ctypes_struct(self) -> _SFLoopInfoCTypes:
        """Converts this dataclass instance to a ctypes SF_LOOP_INFO structure."""
        return _SFLoopInfoCTypes(
            time_sig_num=self.time_sig_num,
            time_sig_den=self.time_sig_den,
            loop_mode=self.loop_mode,
            num_beats=self.num_beats,
            bpm=self.bpm,
            root_key=self.root_key,
            future=(ctypes.c_int * 6)(*self.future),
        )

# pylint: disable=too-few-public-methods
@dataclasses.dataclass
class SFInstrumentLoop:
    """
    Pythonic representation of a loop within an SF_INSTRUMENT structure.

    Attributes:
        mode: Loop mode for this specific loop (e.g., SF_LOOP_FORWARD).
        start: Start sample of the loop.
        end: End sample of the loop.
        count: Loop count (0 for infinite).
    """
    mode: int = SF_LOOP_NONE
    start: int = 0
    end: int = 0
    count: int = 0

    @classmethod
    def from_ctypes_struct(cls, ct_struct: _SFInstrumentLoopCTypes) -> 'SFInstrumentLoop':
        """Creates an SFInstrumentLoop dataclass instance from a ctypes structure."""
        return cls(
            mode=ct_struct.mode,
            start=ct_struct.start,
            end=ct_struct.end,
            count=ct_struct.count,
        )

    def to_ctypes_struct(self) -> _SFInstrumentLoopCTypes:
        """Converts this dataclass instance to a ctypes instrument loop structure."""
        return _SFInstrumentLoopCTypes(
            mode=self.mode, start=self.start, end=self.end, count=self.count
        )

MAX_INSTRUMENT_LOOPS = 16

# pylint: disable=too-few-public-methods,too-many-instance-attributes
@dataclasses.dataclass
class SFInstrumentInfo:
    """
    Pythonic representation of a libsndfile SF_INSTRUMENT structure.

    Contains information about how a sample should be played by a sampler.

    Attributes:
        gain: Gain to be applied to the sample (usually in dB).
        basenote: MIDI note number at which the sample plays at its original pitch.
        detune: Detuning from the basenote in cents.
        velocity_lo: Lowest MIDI velocity for which this instrument should play.
        velocity_hi: Highest MIDI velocity for which this instrument should play.
        key_lo: Lowest MIDI key for which this instrument should play.
        key_hi: Highest MIDI key for which this instrument should play.
        loop_count: Number of defined loops for this instrument.
        loops: List of SFInstrumentLoop objects.
    """
    gain: int = 0
    basenote: int = 0
    detune: int = 0
    velocity_lo: int = 0
    velocity_hi: int = 0
    key_lo: int = 0
    key_hi: int = 0
    loop_count: int = 0
    loops: List[SFInstrumentLoop] = dataclasses.field(default_factory=list)

    @classmethod
    def from_ctypes_struct(cls, ct_struct: _SFInstrumentInfoCTypes) -> 'SFInstrumentInfo':
        """Creates an SFInstrumentInfo dataclass instance from a ctypes structure."""
        loops_data = [
            SFInstrumentLoop.from_ctypes_struct(l)
            for l in ct_struct.loops[: ct_struct.loop_count]
            if ct_struct.loop_count > 0
        ]
        return cls(
            gain=ct_struct.gain,
            basenote=ct_struct.basenote,
            detune=ct_struct.detune,
            velocity_lo=ct_struct.velocity_lo,
            velocity_hi=ct_struct.velocity_hi,
            key_lo=ct_struct.key_lo,
            key_hi=ct_struct.key_hi,
            loop_count=ct_struct.loop_count,
            loops=loops_data,
        )

    def to_ctypes_struct(self) -> _SFInstrumentInfoCTypes:
        """Converts this dataclass instance to a ctypes SF_INSTRUMENT structure."""
        ct_loops_array = (_SFInstrumentLoopCTypes * MAX_INSTRUMENT_LOOPS)()
        num_loops_to_write = min(len(self.loops), MAX_INSTRUMENT_LOOPS)

        for i in range(num_loops_to_write):
            ct_loops_array[i] = self.loops[i].to_ctypes_struct()

        return _SFInstrumentInfoCTypes(
            gain=self.gain,
            basenote=self.basenote,
            detune=self.detune,
            velocity_lo=self.velocity_lo,
            velocity_hi=self.velocity_hi,
            key_lo=self.key_lo,
            key_hi=self.key_hi,
            loop_count=num_loops_to_write,
            loops=ct_loops_array,
        )

# --- Utility functions for metadata ---

def get_cue_markers(file_path: str) -> List[SFCuePoint]:
    """
    Reads cue markers from an audio file using libsndfile's SFC_GET_CUES command.

    Args:
        file_path: Path to the audio file.

    Returns:
        A list of SFCuePoint objects, or an empty list if no cues are found
        or an error occurs.
    """
    cues_data = []
    try:
        with soundfile.SoundFile(file_path, "r") as sf_obj:
            c_cues_ptr = _ffi.new("SF_CUES*")
            success = sf_obj.command(SFC_GET_CUES, c_cues_ptr, _ffi.sizeof("SF_CUES"))

            if success:
                num_cues = c_cues_ptr.cue_count
                num_cues_to_read = min(num_cues, MAX_CUE_POINTS)
                for i in range(num_cues_to_read):
                    cue_point_ct = c_cues_ptr.cue_points[i]
                    name_bytes = bytes(cue_point_ct.name).split(b"\x00", 1)[0]
                    cues_data.append(
                        SFCuePoint(
                            indx=cue_point_ct.indx,
                            position=cue_point_ct.position,
                            fcc_chunk=cue_point_ct.fcc_chunk,
                            chunk_start=cue_point_ct.chunk_start,
                            block_start=cue_point_ct.block_start,
                            sample_offset=cue_point_ct.sample_offset,
                            name=name_bytes,
                        )
                    )
    except soundfile.LibsndfileError:
        pass
    return cues_data

def set_cue_markers(file_path: str, cues: List[SFCuePoint]) -> bool:
    """
    Writes cue markers to an audio file using libsndfile's SFC_SET_CUES command.

    Args:
        file_path: Path to the audio file (must be writable).
        cues: A list of SFCuePoint objects to write.

    Returns:
        True if successful, False otherwise.

    Raises:
        ValueError: If the number of cues exceeds MAX_CUE_POINTS.
    """
    if len(cues) > MAX_CUE_POINTS:
        raise ValueError(
            f"Number of cues ({len(cues)}) exceeds maximum "
            f"allowed ({MAX_CUE_POINTS})."
        )
    try:
        with soundfile.SoundFile(file_path, "r+") as sf_obj:
            c_cues_ptr = _ffi.new("SF_CUES*")
            c_cues_ptr.cue_count = len(cues)

            for i, py_cue in enumerate(cues):
                c_cue_point_struct = py_cue.to_ctypes_struct()
                c_cues_ptr.cue_points[i].indx = c_cue_point_struct.indx
                c_cues_ptr.cue_points[i].position = c_cue_point_struct.position
                c_cues_ptr.cue_points[i].fcc_chunk = c_cue_point_struct.fcc_chunk
                c_cues_ptr.cue_points[i].chunk_start = c_cue_point_struct.chunk_start
                c_cues_ptr.cue_points[i].block_start = c_cue_point_struct.block_start
                c_cues_ptr.cue_points[i].sample_offset = c_cue_point_struct.sample_offset
                name_bytes_prepared = c_cue_point_struct.name
                for j, byte_val in enumerate(name_bytes_prepared):
                    if j < 256:
                        c_cues_ptr.cue_points[i].name[j] = byte_val
                    else:
                        break
                if len(name_bytes_prepared) < 256:
                    c_cues_ptr.cue_points[i].name[len(name_bytes_prepared)] = b"\x00"

            if not sf_obj.command(SFC_SET_CUES, c_cues_ptr, _ffi.sizeof("SF_CUES")):
                return False
            sf_obj.flush()
            return True
    except soundfile.LibsndfileError:
        return False
    except ValueError:
        raise
    except Exception: # pylint: disable=broad-except
        return False

def get_instrument_info(file_path: str) -> Optional[SFInstrumentInfo]:
    """
    Reads SF_INSTRUMENT metadata from an audio file.

    Args:
        file_path: Path to the audio file.

    Returns:
        An SFInstrumentInfo object if instrument data is found, else None.
    """
    try:
        with soundfile.SoundFile(file_path, "r") as sf_obj:
            c_instr_ptr = _ffi.new("SF_INSTRUMENT*")
            if sf_obj.command(
                SFC_GET_INSTRUMENT, c_instr_ptr, _ffi.sizeof("SF_INSTRUMENT")
            ):
                loops_data = []
                if c_instr_ptr.loop_count > 0:
                    num_loops = min(
                        c_instr_ptr.loop_count, MAX_INSTRUMENT_LOOPS
                    )
                    for i in range(num_loops):
                        cloop = c_instr_ptr.loops[i]
                        loops_data.append(
                            SFInstrumentLoop(
                                mode=cloop.mode, start=cloop.start,
                                end=cloop.end, count=cloop.count
                            )
                        )
                return SFInstrumentInfo(
                    gain=c_instr_ptr.gain,
                    basenote=c_instr_ptr.basenote,
                    detune=c_instr_ptr.detune,
                    velocity_lo=c_instr_ptr.velocity_lo,
                    velocity_hi=c_instr_ptr.velocity_hi,
                    key_lo=c_instr_ptr.key_lo,
                    key_hi=c_instr_ptr.key_hi,
                    loop_count=c_instr_ptr.loop_count,
                    loops=loops_data,
                )
            return None
    except soundfile.LibsndfileError:
        return None

def set_instrument_info(file_path: str, instr_info: SFInstrumentInfo) -> bool:
    """
    Writes SF_INSTRUMENT metadata to an audio file.

    Args:
        file_path: Path to the audio file (must be writable).
        instr_info: An SFInstrumentInfo object containing the data to write.

    Returns:
        True if successful, False otherwise.
    """
    try:
        with soundfile.SoundFile(file_path, "r+") as sf_obj:
            c_instr_ptr = _ffi.new("SF_INSTRUMENT*")
            c_instr_ptr.gain = instr_info.gain
            c_instr_ptr.basenote = instr_info.basenote
            c_instr_ptr.detune = instr_info.detune
            c_instr_ptr.velocity_lo = instr_info.velocity_lo
            c_instr_ptr.velocity_hi = instr_info.velocity_hi
            c_instr_ptr.key_lo = instr_info.key_lo
            c_instr_ptr.key_hi = instr_info.key_hi
            num_loops = min(len(instr_info.loops), MAX_INSTRUMENT_LOOPS)
            c_instr_ptr.loop_count = num_loops
            for i in range(num_loops):
                py_loop = instr_info.loops[i]
                c_instr_ptr.loops[i].mode = py_loop.mode
                c_instr_ptr.loops[i].start = py_loop.start
                c_instr_ptr.loops[i].end = py_loop.end
                c_instr_ptr.loops[i].count = py_loop.count
            if not sf_obj.command(
                SFC_SET_INSTRUMENT, c_instr_ptr, _ffi.sizeof("SF_INSTRUMENT")
            ):
                return False
            sf_obj.flush()
            return True
    except soundfile.LibsndfileError:
        return False

def get_loop_info(file_path: str) -> Optional[SFLoopInfo]:
    """
    Reads SF_LOOP_INFO metadata (sampler loop information) from an audio file.

    Args:
        file_path: Path to the audio file.

    Returns:
        An SFLoopInfo object if loop data is found, else None.
    """
    try:
        with soundfile.SoundFile(file_path, "r") as sf_obj:
            c_loop_ptr = _ffi.new("SF_LOOP_INFO*")
            if sf_obj.command(
                SFC_GET_LOOP_INFO, c_loop_ptr, _ffi.sizeof("SF_LOOP_INFO")
            ):
                return SFLoopInfo(
                    time_sig_num=c_loop_ptr.time_sig_num,
                    time_sig_den=c_loop_ptr.time_sig_den,
                    loop_mode=c_loop_ptr.loop_mode,
                    num_beats=c_loop_ptr.num_beats,
                    bpm=c_loop_ptr.bpm,
                    root_key=c_loop_ptr.root_key,
                    future=tuple(c_loop_ptr.future),
                )
            return None
    except soundfile.LibsndfileError:
        return None

def set_loop_info(file_path: str, loop_info: SFLoopInfo) -> bool:
    """
    Writes SF_LOOP_INFO metadata (sampler loop information) to an audio file.

    Args:
        file_path: Path to the audio file (must be writable).
        loop_info: An SFLoopInfo object containing the data to write.

    Returns:
        True if successful, False otherwise.
    """
    try:
        with soundfile.SoundFile(file_path, "r+") as sf_obj:
            c_loop_ptr = _ffi.new("SF_LOOP_INFO*")
            c_loop_ptr.time_sig_num = loop_info.time_sig_num
            c_loop_ptr.time_sig_den = loop_info.time_sig_den
            c_loop_ptr.loop_mode = loop_info.loop_mode
            c_loop_ptr.num_beats = loop_info.num_beats
            c_loop_ptr.bpm = loop_info.bpm
            c_loop_ptr.root_key = loop_info.root_key
            for i in range(6):
                c_loop_ptr.future[i] = loop_info.future[i]
            if not sf_obj.command(
                SFC_SET_LOOP_INFO, c_loop_ptr, _ffi.sizeof("SF_LOOP_INFO")
            ):
                return False
            sf_obj.flush()
            return True
    except soundfile.LibsndfileError:
        return False

# TODO:
# - Refine CFFI struct interaction (current manual field assignment is okay but verbose).
# - Test thoroughly with actual audio files.
# - Add more robust error handling and logging.
# - Confirm encoding for SFCuePoint.name (UTF-8 assumed).
# - Clarify char to int conversion for SFInstrumentInfo fields (basenote, etc.)
#   The current code assumes CFFI handles char as int (ASCII value), which is typical.
