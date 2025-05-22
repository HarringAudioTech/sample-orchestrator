#!/usr/bin/env python

from aubio import source, notes, sink
import os
import argparse
import sys

# Global constants
HOP_SIZE = 256
WINDOW_SIZE = 512

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Slice tones from a WAV file.")
    parser.add_argument("input_file", help="Path to the input WAV file.")
    parser.add_argument("-o", "--output_dir", default="output_tones", help="Directory to save sliced tone files. Defaults to 'output_tones'.")
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found.")
        exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Input file: {args.input_file}")
    print(f"Output directory: {args.output_dir}")

    file_samplerate = 0
    file_channels = 0
    notes_to_slice = []
    total_frames_read_from_first_pass = 0

    try:
        # First pass: Note detection
        s = source(args.input_file, samplerate=0, hop_size=HOP_SIZE) # samplerate=0 to use file's original, hop_size for note detection
        file_samplerate = s.samplerate
        file_channels = s.channels # This is the number of channels in the source file
        print(f"Audio properties: Samplerate: {file_samplerate}, Channels: {file_channels}")

        # Note detection operates on mono, which s() provides by mixing down if necessary.
        # The HOP_SIZE for notes_o should match the hop_size of the source s.
        notes_o = notes("default", WINDOW_SIZE, HOP_SIZE, file_samplerate)

        detected_notes_raw = []
        current_frame_index = 0

        print("Starting note detection...")
        while True:
            # For note detection, aubio's notes object expects mono samples.
            # s() provides mono samples of size HOP_SIZE.
            samples, read = s() 
            if read < HOP_SIZE:
                current_frame_index += read # Add remaining frames
                break

            note_event = notes_o(samples)
            if note_event[0] != 0:  # Pitch is non-zero
                midi_pitch = note_event[0]
                velocity = note_event[1]
                start_frame = current_frame_index
                detected_notes_raw.append((midi_pitch, start_frame, velocity))
                # print(f"Detected MIDI: {midi_pitch}, Velocity: {velocity} at frame {start_frame}")
            
            current_frame_index += read
        
        total_frames_read_from_first_pass = current_frame_index
        s.close()

        print(f"Finished note detection. Total frames processed: {total_frames_read_from_first_pass}")
        print(f"Found {len(detected_notes_raw)} note events.")

        if not detected_notes_raw:
            print("No notes detected. Exiting.")
            sys.exit(0)

        detected_notes_raw.sort(key=lambda note: note[1])
        
        # print("Detected notes (MIDI_pitch, start_frame, velocity):")
        # for note in detected_notes_raw:
        #     print(note)

        for i, (midi_pitch, start_frame, velocity) in enumerate(detected_notes_raw):
            end_frame = 0
            if i < len(detected_notes_raw) - 1:
                end_frame = detected_notes_raw[i+1][1]
            else:
                end_frame = total_frames_read_from_first_pass
            
            # Ensure end_frame is greater than start_frame
            if end_frame > start_frame:
                notes_to_slice.append((midi_pitch, start_frame, end_frame, velocity))
            # else:
                # print(f"Skipping note {midi_pitch} at {start_frame} due to end_frame ({end_frame}) not being greater.")


        print("\nNotes prepared for slicing (MIDI, StartFrame, EndFrame, Velocity):")
        for note_slice_info in notes_to_slice:
            print(note_slice_info)
        
        if not notes_to_slice:
            print("No valid note segments to slice after processing. Exiting.")
            sys.exit(0)

    except Exception as e:
        print(f"An error occurred during note detection phase: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

    # Second pass: Slicing and writing audio
    try:
        print("\nStarting audio slicing and writing...")
        midi_counters = {}

        for note_info in notes_to_slice:
            midi_pitch, start_frame, end_frame, velocity = note_info

            # Determine output filename
            count = midi_counters.get(midi_pitch, 0)
            filename = f"midi_{int(midi_pitch)}_{count}.wav"
            output_path = os.path.join(args.output_dir, filename)
            midi_counters[midi_pitch] = count + 1

            # Open the original input WAV file again for slicing.
            # Crucially, set channels to file_channels to read all original channels.
            # Samplerate is also set to file_samplerate. Hop size for reading can be larger now.
            s_slice = source(args.input_file, samplerate=file_samplerate, hop_size=HOP_SIZE, channels=file_channels)
            
            # Create the sink with original file's samplerate and channels
            g = sink(output_path, samplerate=file_samplerate, channels=file_channels)

            s_slice.seek(start_frame)
            
            num_frames_to_write = end_frame - start_frame
            if num_frames_to_write <= 0:
                print(f"Warning: Skipping slice for MIDI {midi_pitch} as num_frames_to_write is {num_frames_to_write} (start: {start_frame}, end: {end_frame}).")
                s_slice.close()
                g.close() # Close sink even if no write occurs to prevent empty/corrupt files
                if os.path.exists(output_path) and os.path.getsize(output_path) == 0: # Clean up empty file
                    os.remove(output_path)
                continue

            frames_written_for_slice = 0
            
            while frames_written_for_slice < num_frames_to_write:
                # Read frames based on the number of channels
                if file_channels > 1:
                    samples_block, read = s_slice.do_multi()
                else:
                    samples_block, read = s_slice() # s_slice() returns a mono buffer

                if read == 0: # End of file reached prematurely
                    print(f"Warning: End of file reached prematurely while slicing for MIDI {midi_pitch} at {output_path}. Wrote {frames_written_for_slice} of {num_frames_to_write} frames.")
                    break
                
                # Determine how many of the read frames should actually be written in this iteration
                # This is important to not write past end_frame
                samples_to_write_this_iteration = min(read, num_frames_to_write - frames_written_for_slice)

                if samples_to_write_this_iteration <= 0: # Should not happen if num_frames_to_write is positive
                    break

                # Write frames based on the number of channels
                if file_channels > 1:
                    g.do_multi(samples_block[:, :samples_to_write_this_iteration], samples_to_write_this_iteration)
                else:
                    # For mono, samples_block is 1D array, so slice directly
                    g.do(samples_block[:samples_to_write_this_iteration], samples_to_write_this_iteration)
                
                frames_written_for_slice += samples_to_write_this_iteration
            
            g.close()
            s_slice.close()
            print(f"Wrote: {output_path} ({frames_written_for_slice} frames)")

        print("\nFinished slicing all tones.")

    except Exception as e:
        print(f"An error occurred during audio slicing phase: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
