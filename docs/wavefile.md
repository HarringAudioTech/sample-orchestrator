# Guide to the Internals of the Wave File

The Wave file format, native to Windows, is a widely supported digital audio file format on PCs. It utilizes the RIFF (Resource Interchange File Format) structure, organizing data into chunks, each with its own header and data. This chunk-based system allows programs to skip unrecognized chunks.

All data values in wave files are stored in Little-Endian order. Strings, used for things like cue point labels, are stored with the first byte indicating the number of following ASCII text bytes.Wave File Structure and Chunks

A basic wave file layout includes a "RIFF" chunk containing a "WAVE" type ID, followed by a "fmt " (format) chunk and a "data" chunk.Wave File Header (RIFF Type Chunk):

## Wave Header

The first 8 bytes of a wave file form a standard RIFF chunk header.

* Chunk ID: "RIFF" (\`0x52494646\`) at offset \`0x00\`, size 4 bytes.  
* Chunk Data Size: (file size) \- 8 at offset \`0x04\`, size 4 bytes.  
* RIFF Type: "WAVE" (\`0x57415645\`) at offset \`0x08\`, size 4 bytes.

## Wave File Chunks:

Wave chunks follow a standard format:

* Chunk ID: at offset \`0x00\`, size 4 bytes.  
* Chunk Data Size: at offset \`0x04\`, size 4 bytes.  
* Chunk Data Bytes: at offset \`0x08\`.

### Format Chunk \- "fmt ":

This chunk contains information about how the waveform data is stored, including compression, number of channels, sample rate, and bits per sample.

* Chunk ID: "fmt " (\`0x666D7420\`) at offset \`0x00\`, size 4 bytes.  
* Chunk Data Size: 16 \+ extra format bytes at offset \`0x04\`, size 4 bytes.  
* Compression code: 1 \- 65,535 at offset \`0x08\`, size 2 bytes. (e.g., 1 for PCM/uncompressed, 6 for ITU G.711 a-law, 80 for MPEG).  
* Number of channels: 1 \- 65,535 at offset \`0x0a\`, size 2 bytes.  
* Sample rate: 1 \- \`0xFFFFFFFF\` at offset \`0x0c\`, size 4 bytes.  
* Average bytes per second: 1 \- \`0xFFFFFFFF\` at offset \`0x10\`, size 4 bytes (calculated as SampleRate \* BlockAlign).  
* Block align: 1 \- 65,535 at offset \`0x14\`, size 2 bytes (calculated as SignificantBitsPerSample / 8 \* NumChannels).  
* Significant bits per sample: 2 \- 65,535 at offset \`0x16\`, size 2 bytes (usually 8, 16, 24, or 32).  
* Extra format bytes: 0 \- 65,535 at offset \`0x18\`, size 2 bytes.

### Data Chunk \- "data":

Contains the digital audio sample data.

* Chunk ID: "data" (\`0x64616461\`) at offset \`0x00\`, size 4 bytes.  
* Chunk size: depends on sample length and compression at offset \`0x04\`, size 4 bytes.  
* Sample data: at offset \`0x08\`. Multi-channel audio samples are interlaced. 8-bit samples are unsigned, while other bit-sizes are signed.

### Fact Chunk \- "fact":

Stores compression-code dependent information. Required for all compressed WAVE formats and if waveform data is in a "wavl" LIST chunk, but not for uncompressed PCM.

* Chunk ID: "fact" (\`0x66616374\`) at offset \`0x00\`, size 4 bytes.  
* Chunk Data Size: depends on format at offset \`0x04\`, size 4 bytes.  
* Format Dependant Data: at offset \`0x08\` (currently, a 4-byte value specifying the number of samples).

### Wave List Chunk \- "wavl":

Used to specify alternating "slnt" and "data" chunks to reduce file size during periods of silence.

* Chunk ID: "slnt" (\`0x736C6E74\`) at offset \`0x00\`, size 4 bytes.  
* Chunk Data Size: depends on size of data and slnt chunks at offset \`0x04\`, size 4 bytes.  
* List of Alternating "slnt" and "data" Chunks: at offset \`0x08\`.

### Silent Chunk \- "slnt":

Specifies a segment of silence within a wave list chunk.

* Chunk ID: "slnt" (\`0x736C6E74\`) at offset \`0x00\`, size 4 bytes.  
* Chunk Data Size: 4 at offset \`0x04\`, size 4 bytes.  
* Number of Silent Samples: 0 \- \`0xFFFFFFFF\` at offset \`0x08\`, size 4 bytes.

### Cue Chunk \- "cue ":

Specifies one or more sample offsets to mark sections of audio.

* Chunk ID: "cue " (\`0x63756520\`) at offset \`0x00\`, size 4 bytes.  
* Chunk Data Size: depends on Num Cue Points at offset \`0x04\`, size 4 bytes (calculated as 4 \+ (NumCuePoints \* 24)).  
* Num Cue Points: number of cue points in list at offset \`0x08\`, size 4 bytes.  
* List of Cue Points: at offset \`0x0c\`. Each cue point has an ID, Position, Data Chunk ID, Chunk Start, Block Start, and Sample Offset.

### Playlist Chunk \- "plst":

Specifies the play order of cue points.

* Chunk ID: "plst" (\`0x736C6E74\`) at offset \`0x00\`, size 4 bytes.  
* Chunk Data Size: num segments \* 12 at offset \`0x04\`, size 4 bytes.  
* Number of Segments: 1 \- \`0xFFFFFFFF\` at offset \`0x08\`, size 4 bytes.  
* List of Segments: at offset \`0x0a\`. Each segment has a Cue Point ID, Length (in samples), and Number of Repeats.

### Associated Data List Chunk \- "list":

Defines text labels and names associated with cue points.

* Chunk ID: "list" (\`0x6C696E74\`) at offset \`0x00\`, size 4 bytes.  
* Chunk Data Size: depends on contained text at offset \`0x04\`, size 4 bytes.  
* Type ID: "adtl" (\`0x6164746C\`) at offset \`0x08\`, size 4 bytes.  
* List of Text Labels and Names: at offset \`0x0c\` (includes Label Chunk, Note Chunk, Labeled Text Chunk).

### Label Chunk \- "labl":

Associates a text label with a Cue Point.

* Chunk ID: "labl" (\`0x6C61626C\`) at offset \`0x00\`, size 4 bytes.  
* Chunk Data Size: depends on contained text at offset \`0x04\`, size 4 bytes.  
* Cue Point ID: 0 \- \`0xFFFFFFFF\` at offset \`0x08\`, size 4 bytes.  
* Text: at offset \`0x0c\` (null-terminated string, padded to even length).

### Note Chunk \- "note":

Associates a text comment with a Cue Point, similar to a label chunk.

* Chunk ID: "note" (\`0x6E6F7465\`) at offset \`0x00\`, size 4 bytes.  
* Chunk Data Size: depends on contained text at offset \`0x04\`, size 4 bytes.  
* Cue Point ID: 0 \- \`0xFFFFFFFF\` at offset \`0x08\`, size 4 bytes.  
* Text: at offset \`0x0c\` (null-terminated string, padded to even length).

### Labeled Text Chunk \- "ltxt":

Associates a text label with a region of waveform data.

* Chunk ID: "ltxt" (\`0x6C747874\`) at offset \`0x00\`, size 4 bytes.  
* Chunk Data Size: depends on contained text at offset \`0x04\`, size 4 bytes.  
* Cue Point ID: 0 \- \`0xFFFFFFFF\` at offset \`0x08\`, size 4 bytes.  
* Sample Length: 0 \- \`0xFFFFFFFF\` at offset \`0

