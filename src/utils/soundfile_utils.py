import ctypes
import dataclasses
import soundfile
from soundfile import _lib as sf_lib
from soundfile import _ffi as _ffi
from typing import List, Tuple, Optional

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
SFC_GET_CUES = sf_lib.SFC_GET_CUES # Note: SFC_GET_CUES is the correct command for getting all cues
SFC_SET_CUES = sf_lib.SFC_SET_CUES # Note: SFC_SET_CUES is the correct command for setting all cues
# SFC_GET_CUE_COUNT and SFC_GET_CUE (singular) might not be standard or as useful as SFC_GET_CUES
# For individual cue access if needed, one would typically iterate through the SF_CUES struct.
# We will use SFC_GET_CUES and SFC_SET_CUES which operate on an SF_CUES structure.

# Loop modes from soundfile._lib (ensure these match the previous integer values if used interchangeably)
SF_LOOP_NONE = sf_lib.SF_LOOP_NONE
SF_LOOP_FORWARD = sf_lib.SF_LOOP_FORWARD
SF_LOOP_BACKWARD = sf_lib.SF_LOOP_BACKWARD
SF_LOOP_ALTERNATING = sf_lib.SF_LOOP_ALTERNATING

# Define internal ctypes Structure for SF_CUE_POINT for command usage
class _SFCuePointCTypes(ctypes.Structure):
    _fields_ = [
        ("indx", ctypes.c_int),
        ("position", ctypes.c_uint32),
        ("fcc_chunk", ctypes.c_int32),
        ("chunk_start", ctypes.c_int32),
        ("block_start", ctypes.c_int32),
        ("sample_offset", ctypes.c_uint32),
        ("name", ctypes.c_char * 256),
    ]

# Define internal ctypes Structure for SF_CUES for command usage
# libsndfile has a limit of 100 cue points in the SF_CUES struct,
# but can handle more with SF_CUES_VAR, which is more complex.
# We'll define for a fixed reasonable maximum for now.
MAX_CUE_POINTS = 100 # Default SF_CUES limit

class _SFCuesCTypes(ctypes.Structure):
    _fields_ = [
        ("cue_count", ctypes.c_uint32), # Changed to uint32_t to match common practice for counts
        ("cue_points", _SFCuePointCTypes * MAX_CUE_POINTS)
    ]

# Define internal ctypes Structure for SF_INSTRUMENT_LOOP
class _SFInstrumentLoopCTypes(ctypes.Structure):
    _fields_ = [
        ("mode", ctypes.c_int),
        ("start", ctypes.c_uint32),
        ("end", ctypes.c_uint32),
        ("count", ctypes.c_uint32),
    ]

# Define internal ctypes Structure for SF_INSTRUMENT
class _SFInstrumentInfoCTypes(ctypes.Structure):
    _fields_ = [
        ("gain", ctypes.c_int),
        ("basenote", ctypes.c_char),
        ("detune", ctypes.c_char),
        ("velocity_lo", ctypes.c_char),
        ("velocity_hi", ctypes.c_char),
        ("key_lo", ctypes.c_char),
        ("key_hi", ctypes.c_char),
        ("loop_count", ctypes.c_int),
        ("loops", _SFInstrumentLoopCTypes * 16), # Max 16 loops
    ]

# Define internal ctypes Structure for SF_LOOP_INFO
class _SFLoopInfoCTypes(ctypes.Structure):
    _fields_ = [
        ("time_sig_num", ctypes.c_short),
        ("time_sig_den", ctypes.c_short),
        ("loop_mode", ctypes.c_int),
        ("num_beats", ctypes.c_int),
        ("bpm", ctypes.c_float),
        ("root_key", ctypes.c_int),
        ("future", ctypes.c_int * 6),
    ]


@dataclasses.dataclass
class SFCuePoint:
    """
    Mirrors the SF_CUE_POINT struct from libsndfile's sndfile.h.
    This is the inner struct within SF_CUES.
    typedef struct
    {   int     indx ;
        uint32_t    position ;
        int32_t     fcc_chunk ;
        int32_t     chunk_start ;
        int32_t     block_start ;
        uint32_t    sample_offset ;
        char        name [256] ;
    } SF_CUE_POINT ;
    """
    indx: int = 0
    position: int = 0  # uint32_t
    fcc_chunk: int = 0  # int32_t
    chunk_start: int = 0  # int32_t
    block_start: int = 0  # int32_t
    sample_offset: int = 0  # uint32_t
    name: bytes = b'\x00' * 256 # char[256]

    # Helper to create from a ctypes structure if needed later
    @classmethod
    def from_ctypes_struct(cls, ct_struct):
        return cls(
            indx=ct_struct.indx,
            position=ct_struct.position,
            fcc_chunk=ct_struct.fcc_chunk,
            chunk_start=ct_struct.chunk_start,
            block_start=ct_struct.block_start,
            sample_offset=ct_struct.sample_offset,
            name=ct_struct.name
        )

    # Helper to convert to a ctypes structure if needed later
    def to_ctypes_struct(self) -> _SFCuePointCTypes:
        # Ensure name is correctly null-terminated and fits
        name_bytes = self.name[:255] # Truncate if necessary
        if not name_bytes.endswith(b'\x00'):
            name_bytes += b'\x00'

        return _SFCuePointCTypes(
            indx=self.indx,
            position=self.position,
            fcc_chunk=self.fcc_chunk,
            chunk_start=self.chunk_start,
            block_start=self.block_start,
            sample_offset=self.sample_offset,
            name=name_bytes
        )

@dataclasses.dataclass
class SFLoopInfo:
    """
    Mirrors the SF_LOOP_INFO struct from libsndfile's sndfile.h.
    typedef struct
    {   short   time_sig_num ;      // Eg 3 for 3/4 time, 0 for no time signature. *
        short   time_sig_den ;      // Eg 4 for 3/4 time, 0 for no time signature. *
        int     loop_mode ;         // See SF_LOOP enum. *
        int     num_beats ;         // Eg 4 for a loop of 4 beats. *
        float   bpm ;               // Eg 120.0 for 120 beats per minute. *
        int     root_key ;          // MIDI note, 0-127, -1 for None. *
        int     future [6] ;
    } SF_LOOP_INFO ;
    """
    time_sig_num: int = 0  # short
    time_sig_den: int = 0  # short
    loop_mode: int = SF_LOOP_NONE  # int (e.g., SF_LOOP_NONE, SF_LOOP_FORWARD)
    num_beats: int = 0  # int
    bpm: float = 0.0  # float
    root_key: int = -1  # int (MIDI note, -1 for None)
    future: Tuple[int, int, int, int, int, int] = dataclasses.field(default_factory=lambda: (0,0,0,0,0,0)) # int[6]

    @classmethod
    def from_ctypes_struct(cls, ct_struct: _SFLoopInfoCTypes):
        return cls(
            time_sig_num=ct_struct.time_sig_num,
            time_sig_den=ct_struct.time_sig_den,
            loop_mode=ct_struct.loop_mode,
            num_beats=ct_struct.num_beats,
            bpm=ct_struct.bpm,
            root_key=ct_struct.root_key,
            future=tuple(ct_struct.future)
        )

    def to_ctypes_struct(self) -> _SFLoopInfoCTypes:
        return _SFLoopInfoCTypes(
            time_sig_num=self.time_sig_num,
            time_sig_den=self.time_sig_den,
            loop_mode=self.loop_mode,
            num_beats=self.num_beats,
            bpm=self.bpm,
            root_key=self.root_key,
            future=(ctypes.c_int * 6)(*self.future)
        )

@dataclasses.dataclass
class SFInstrumentLoop:
    """
    Mirrors the inner loop structure in SF_INSTRUMENT from libsndfile's sndfile.h.
    Part of:
    typedef struct
    {   ...
        struct
        {   int mode ;
            uint32_t start ;
            uint32_t end ;
            uint32_t count ;
        } loops [16] ;
    } SF_INSTRUMENT ;
    """
    mode: int = SF_LOOP_NONE
    start: int = 0  # uint32_t
    end: int = 0    # uint32_t
    count: int = 0  # uint32_t

    @classmethod
    def from_ctypes_struct(cls, ct_struct: _SFInstrumentLoopCTypes):
        return cls(
            mode=ct_struct.mode,
            start=ct_struct.start,
            end=ct_struct.end,
            count=ct_struct.count
        )

    def to_ctypes_struct(self) -> _SFInstrumentLoopCTypes:
        return _SFInstrumentLoopCTypes(
            mode=self.mode,
            start=self.start,
            end=self.end,
            count=self.count
        )


MAX_INSTRUMENT_LOOPS = 16 # As defined by `loops [16]` in SF_INSTRUMENT

@dataclasses.dataclass
class SFInstrumentInfo:
    """
    Mirrors the SF_INSTRUMENT struct from libsndfile's sndfile.h.
    typedef struct
    {   int gain ;
        char basenote, detune ;
        char velocity_lo, velocity_hi ;
        char key_lo, key_hi ;
        int loop_count ;

        struct
        {   int mode ;
            uint32_t start ;
            uint32_t end ;
            uint32_t count ;
        } loops [16] ;
    } SF_INSTRUMENT ;
    """
    gain: int = 0
    basenote: int = 0  # char
    detune: int = 0    # char
    velocity_lo: int = 0 # char
    velocity_hi: int = 0 # char
    key_lo: int = 0      # char
    key_hi: int = 0      # char
    loop_count: int = 0
    loops: List[SFInstrumentLoop] = dataclasses.field(default_factory=list)

    @classmethod
    def from_ctypes_struct(cls, ct_struct: _SFInstrumentInfoCTypes):
        loops_data = [
            SFInstrumentLoop.from_ctypes_struct(l) for l in ct_struct.loops[:ct_struct.loop_count]
            if ct_struct.loop_count > 0 # Ensure loop_count is positive
        ]
        return cls(
            gain=ct_struct.gain,
            basenote=ct_struct.basenote, # will be int from char
            detune=ct_struct.detune,     # will be int from char
            velocity_lo=ct_struct.velocity_lo,
            velocity_hi=ct_struct.velocity_hi,
            key_lo=ct_struct.key_lo,
            key_hi=ct_struct.key_hi,
            loop_count=ct_struct.loop_count,
            loops=loops_data
        )

    def to_ctypes_struct(self) -> _SFInstrumentInfoCTypes:
        ct_loops_array = (_SFInstrumentLoopCTypes * MAX_INSTRUMENT_LOOPS)()
        num_loops_to_write = min(len(self.loops), MAX_INSTRUMENT_LOOPS)

        for i in range(num_loops_to_write):
            ct_loops_array[i] = self.loops[i].to_ctypes_struct()

        return _SFInstrumentInfoCTypes(
            gain=self.gain,
            basenote=self.basenote, # ctypes handles char conversion
            detune=self.detune,
            velocity_lo=self.velocity_lo,
            velocity_hi=self.velocity_hi,
            key_lo=self.key_lo,
            key_hi=self.key_hi,
            loop_count=num_loops_to_write,
            loops=ct_loops_array
        )

# --- Utility functions for metadata ---

def get_cue_markers(file_path: str) -> List[SFCuePoint]:
    """Reads cue markers from an audio file."""
    cues_data = []
    try:
        with soundfile.SoundFile(file_path, 'r') as sf_obj:
            # Create a CTypes SF_CUES structure instance
            c_cues = _SFCuesCTypes()

            # Pass the structure to sf_command
            # The pointer to the struct is obtained via ctypes.byref()
            # The size of the struct is obtained via ctypes.sizeof()
            # Note: soundfile's command wrapper might handle some _ffi details internally
            # For direct CFFI interaction if soundfile.command is not enough:
            # c_cues_ptr = _ffi.new("SF_CUES*") # Allocate memory for SF_CUES
            # result = sf_lib.sf_command(sf_obj._file.ptr, SFC_GET_CUES, c_cues_ptr, _ffi.sizeof("SF_CUES"))
            # For now, assuming soundfile.command can handle ctypes struct pointers.
            # This is an area that might need refinement based on soundfile's exact CFFI interface.

            # Let's try with a CFFI pointer directly as per soundfile examples for other structs
            c_cues_ptr = _ffi.new("SF_CUES*")

            if sf_obj.command(SFC_GET_CUES, c_cues_ptr, _ffi.sizeof("SF_CUES")):
                num_cues = c_cues_ptr.cue_count
                # Ensure we don't read beyond MAX_CUE_POINTS or allocated memory
                num_cues_to_read = min(num_cues, MAX_CUE_POINTS)
                for i in range(num_cues_to_read):
                    cue_point_ct = c_cues_ptr.cue_points[i]
                    # Ensure name is properly decoded, handling potential null bytes earlier
                    name_bytes = bytes(cue_point_ct.name).split(b'\x00', 1)[0]
                    cues_data.append(SFCuePoint(
                        indx=cue_point_ct.indx,
                        position=cue_point_ct.position,
                        fcc_chunk=cue_point_ct.fcc_chunk,
                        chunk_start=cue_point_ct.chunk_start,
                        block_start=cue_point_ct.block_start,
                        sample_offset=cue_point_ct.sample_offset,
                        name=name_bytes # Store as bytes, decode later if needed as string
                    ))
            else:
                # Command might return 0 or False on failure, or raise an exception
                # Depending on soundfile's behavior, this might not be reached if an error is raised.
                # Consider checking sf_obj.error_str() or similar if available and no exception.
                pass # No cues or error, cues_data remains empty or handle error
    except soundfile.LibsndfileError as e:
        # Handle cases like file not found, format not supported, or libsndfile errors
        # For now, re-raise or print, or return empty list.
        # print(f"Error getting cue markers for {file_path}: {e}")
        # Depending on desired behavior, could raise custom exception or return empty
        pass # Return empty list on error
    return cues_data


def set_cue_markers(file_path: str, cues: List[SFCuePoint]) -> bool:
    """Writes cue markers to an audio file."""
    if len(cues) > MAX_CUE_POINTS:
        raise ValueError(f"Number of cues ({len(cues)}) exceeds maximum allowed ({MAX_CUE_POINTS}).")

    try:
        with soundfile.SoundFile(file_path, 'r+') as sf_obj:
            c_cues_ptr = _ffi.new("SF_CUES*")
            c_cues_ptr.cue_count = len(cues)

            for i, py_cue in enumerate(cues):
                # Assuming SFCuePoint.to_ctypes_struct() returns a compatible ctypes object
                # and that soundfile's CFFI layer can handle it or we directly assign fields.
                c_cue_point = py_cue.to_ctypes_struct() # Get the ctypes version of the cue
                c_cues_ptr.cue_points[i].indx = c_cue_point.indx
                c_cues_ptr.cue_points[i].position = c_cue_point.position
                c_cues_ptr.cue_points[i].fcc_chunk = c_cue_point.fcc_chunk
                c_cues_ptr.cue_points[i].chunk_start = c_cue_point.chunk_start
                c_cues_ptr.cue_points[i].block_start = c_cue_point.block_start
                c_cues_ptr.cue_points[i].sample_offset = c_cue_point.sample_offset

                # Name handling: ensure bytes, null-terminated, and fits
                name_bytes = py_cue.name
                if not isinstance(name_bytes, bytes): # Should already be bytes due to dataclass type
                    name_bytes = str(name_bytes).encode('utf-8', 'replace')

                # Truncate and null-terminate
                if len(name_bytes) > 255:
                    name_bytes = name_bytes[:255]
                if not name_bytes.endswith(b'\x00'):
                     name_bytes += b'\x00'

                for j, byte_val in enumerate(name_bytes):
                    c_cues_ptr.cue_points[i].name[j] = byte_val
                if len(name_bytes) < 256: # Ensure null termination if shorter
                     c_cues_ptr.cue_points[i].name[len(name_bytes)] = b'\x00'


            if not sf_obj.command(SFC_SET_CUES, c_cues_ptr, _ffi.sizeof("SF_CUES")):
                # print(f"Failed to set cue markers for {file_path}. Error: {sf_obj.error_str()}")
                return False
            sf_obj.flush() # Ensure changes are written
            return True
    except soundfile.LibsndfileError as e:
        # print(f"Error setting cue markers for {file_path}: {e}")
        return False
    except Exception as e:
        # print(f"An unexpected error occurred in set_cue_markers for {file_path}: {e}")
        return False


def get_instrument_info(file_path: str) -> Optional[SFInstrumentInfo]:
    """Reads instrument information from an audio file."""
    try:
        with soundfile.SoundFile(file_path, 'r') as sf_obj:
            c_instr_ptr = _ffi.new("SF_INSTRUMENT*")
            if sf_obj.command(SFC_GET_INSTRUMENT, c_instr_ptr, _ffi.sizeof("SF_INSTRUMENT")):
                # Convert CFFI struct to Python dataclass
                # Need to manually map fields from c_instr_ptr to SFInstrumentInfo
                loops = []
                if c_instr_ptr.loop_count > 0:
                    num_loops_to_read = min(c_instr_ptr.loop_count, MAX_INSTRUMENT_LOOPS)
                    for i in range(num_loops_to_read):
                        cloop = c_instr_ptr.loops[i]
                        loops.append(SFInstrumentLoop(
                            mode=cloop.mode,
                            start=cloop.start,
                            end=cloop.end,
                            count=cloop.count
                        ))

                return SFInstrumentInfo(
                    gain=c_instr_ptr.gain,
                    basenote=ord(c_instr_ptr.basenote) if isinstance(c_instr_ptr.basenote, bytes) else c_instr_ptr.basenote,
                    detune=ord(c_instr_ptr.detune) if isinstance(c_instr_ptr.detune, bytes) else c_instr_ptr.detune,
                    velocity_lo=ord(c_instr_ptr.velocity_lo) if isinstance(c_instr_ptr.velocity_lo, bytes) else c_instr_ptr.velocity_lo,
                    velocity_hi=ord(c_instr_ptr.velocity_hi) if isinstance(c_instr_ptr.velocity_hi, bytes) else c_instr_ptr.velocity_hi,
                    key_lo=ord(c_instr_ptr.key_lo) if isinstance(c_instr_ptr.key_lo, bytes) else c_instr_ptr.key_lo,
                    key_hi=ord(c_instr_ptr.key_hi) if isinstance(c_instr_ptr.key_hi, bytes) else c_instr_ptr.key_hi,
                    loop_count=c_instr_ptr.loop_count,
                    loops=loops
                )
            return None
    except soundfile.LibsndfileError:
        return None


def set_instrument_info(file_path: str, instr_info: SFInstrumentInfo) -> bool:
    """Writes instrument information to an audio file."""
    try:
        with soundfile.SoundFile(file_path, 'r+') as sf_obj:
            c_instr_ptr = _ffi.new("SF_INSTRUMENT*")

            # Populate c_instr_ptr from instr_info
            c_instr_ptr.gain = instr_info.gain
            c_instr_ptr.basenote = instr_info.basenote # char
            c_instr_ptr.detune = instr_info.detune # char
            c_instr_ptr.velocity_lo = instr_info.velocity_lo # char
            c_instr_ptr.velocity_hi = instr_info.velocity_hi # char
            c_instr_ptr.key_lo = instr_info.key_lo # char
            c_instr_ptr.key_hi = instr_info.key_hi # char

            num_loops_to_write = min(len(instr_info.loops), MAX_INSTRUMENT_LOOPS)
            c_instr_ptr.loop_count = num_loops_to_write

            for i in range(num_loops_to_write):
                py_loop = instr_info.loops[i]
                c_instr_ptr.loops[i].mode = py_loop.mode
                c_instr_ptr.loops[i].start = py_loop.start
                c_instr_ptr.loops[i].end = py_loop.end
                c_instr_ptr.loops[i].count = py_loop.count

            if not sf_obj.command(SFC_SET_INSTRUMENT, c_instr_ptr, _ffi.sizeof("SF_INSTRUMENT")):
                return False
            sf_obj.flush()
            return True
    except soundfile.LibsndfileError:
        return False


def get_loop_info(file_path: str) -> Optional[SFLoopInfo]:
    """Reads loop information from an audio file (sampler loop, not instrument loops)."""
    try:
        with soundfile.SoundFile(file_path, 'r') as sf_obj:
            c_loop_ptr = _ffi.new("SF_LOOP_INFO*")
            if sf_obj.command(SFC_GET_LOOP_INFO, c_loop_ptr, _ffi.sizeof("SF_LOOP_INFO")):
                # Convert CFFI struct to Python dataclass
                return SFLoopInfo(
                    time_sig_num=c_loop_ptr.time_sig_num,
                    time_sig_den=c_loop_ptr.time_sig_den,
                    loop_mode=c_loop_ptr.loop_mode,
                    num_beats=c_loop_ptr.num_beats,
                    bpm=c_loop_ptr.bpm,
                    root_key=c_loop_ptr.root_key,
                    future=tuple(c_loop_ptr.future) # Convert C array to tuple
                )
            return None
    except soundfile.LibsndfileError:
        return None

def set_loop_info(file_path: str, loop_info: SFLoopInfo) -> bool:
    """Writes loop information to an audio file."""
    try:
        with soundfile.SoundFile(file_path, 'r+') as sf_obj:
            c_loop_ptr = _ffi.new("SF_LOOP_INFO*")

            # Populate c_loop_ptr from loop_info
            c_loop_ptr.time_sig_num = loop_info.time_sig_num
            c_loop_ptr.time_sig_den = loop_info.time_sig_den
            c_loop_ptr.loop_mode = loop_info.loop_mode
            c_loop_ptr.num_beats = loop_info.num_beats
            c_loop_ptr.bpm = loop_info.bpm
            c_loop_ptr.root_key = loop_info.root_key
            for i in range(6): # future is int[6]
                c_loop_ptr.future[i] = loop_info.future[i]

            if not sf_obj.command(SFC_SET_LOOP_INFO, c_loop_ptr, _ffi.sizeof("SF_LOOP_INFO")):
                return False
            sf_obj.flush()
            return True
    except soundfile.LibsndfileError:
        return False

# TODO:
# - Refine CFFI struct interaction: The current implementation uses _ffi.new("STRUCT_TYPE*")
#   and manual field assignment. This is generally correct. The SFCuePoint.to_ctypes_struct()
#   and similar methods were designed for ctypes, not direct CFFI _ffi.new() style.
#   The current implementation in the functions bypasses these .to_ctypes_struct() methods
#   and directly populates the _ffi.new() allocated structs. This is fine.
# - Test thoroughly with actual audio files containing these metadata types.
# - Add more robust error handling and logging if required.
# - Confirm encoding for SFCuePoint.name (UTF-8 is a common choice).
#   The current code assumes bytes for `name` in SFCuePoint dataclass and handles
#   conversion during set_cue_markers.
# - The `basenote`, `detune`, etc. fields in SFInstrumentInfo are chars in C.
#   Python will treat them as integers (their ASCII value) when read from C struct.
#   When writing, ensure integers are passed that are valid char values (0-255 or -128 to 127).
#   The `ord()` calls in `get_instrument_info` are an attempt to handle this if CFFI
#   returns them as single-char bytes. This needs testing.
