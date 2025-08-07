# Processing Routes Integration Testing

This document outlines the integration testing requirements for the audio processing-related API routes in the Sample Orchestrator.

## Routes to Test

### 1. Process Recording (`POST /recordings/<recording_id>/process`)

#### Test Scenarios

- [ ] Successfully process a recording using a predefined workflow
- [ ] Successfully process a recording using an ad-hoc chain of stages
- [ ] Process a recording with custom parameters for each stage
- [ ] Process a recording with minimal parameters (using defaults)
- [ ] Validate error handling for missing workflow or stages
- [ ] Validate error handling for invalid workflow name
- [ ] Validate error handling for invalid stage parameters
- [ ] Validate error handling for non-existent recording
- [ ] Validate error handling for unsupported audio format
- [ ] Verify database session is properly managed
- [ ] Verify processing results are saved to database
- [ ] Verify processed files are created on filesystem
- [ ] Verify response format and status code (200)

#### Test Data Requirements

```json
// Process with workflow
{
  "workflow_name": "sample_pack_workflow",
  "output_dir_suffix": "test_output"
}

// Process with ad-hoc chain
{
  "stages_chain": [
    {
      "name": "slicer",
      "params": {
        "threshold": -40
      }
    },
    {
      "name": "noise_reduction",
      "params": {
        "reduction_amount": 6
      }
    }
  ],
  "output_dir_suffix": "test_output"
}
```

#### Validation Criteria

1. Response should include processing status
2. Response should include output location
3. Response should include processing results
4. Samples should be created in the database
5. Sample files should exist on filesystem
6. Sample metadata should be correctly populated

### 2. Available Processing Stages (if implemented)

If there's a route to list available processing stages, it should be tested with the following scenarios:

- [ ] Successfully list all available processing stages
- [ ] Verify response includes stage parameters and descriptions
- [ ] Verify database session is properly managed (if needed)
- [ ] Verify response format and status code (200)

### 3. Available Workflows (if implemented)

If there's a route to list available workflows, it should be tested with the following scenarios:

- [ ] Successfully list all available workflows
- [ ] Verify response includes workflow descriptions and stages
- [ ] Verify database session is properly managed (if needed)
- [ ] Verify response format and status code (200)

## Processing Stages to Test

Each processing stage should be tested as part of the integration tests:

1. **Slicing Stage**
   - [ ] Basic slicing with default parameters
   - [ ] Slicing with custom threshold
   - [ ] Slicing with minimum segment length

2. **Noise Reduction Stage**
   - [ ] Basic noise reduction with default parameters
   - [ ] Noise reduction with custom reduction amount
   - [ ] Noise reduction with custom noise profile

3. **Onset Detection Stage**
   - [ ] Basic onset detection with default parameters
   - [ ] Onset detection with custom sensitivity

4. **Segment Classification Stage**
   - [ ] Basic classification with default parameters
   - [ ] Classification with custom thresholds

5. **Vocal Chop Perfection Stage**
   - [ ] Basic vocal processing with default parameters
   - [ ] Vocal processing with custom parameters

6. **Decent Sampler Export Stage**
   - [ ] Basic export with default parameters
   - [ ] Export with custom mapping

## Mock Requirements

- Mock audio processing stages to avoid actual audio processing
- Mock file operations when needed
- Mock workflow execution

## Filesystem Fixtures

- Test recording files with various characteristics:
  - Clean audio
  - Noisy audio
  - Audio with clear onsets
  - Audio with ambiguous onsets
  - Vocal audio
  - Instrumental audio
- Test output directories

## Database Fixtures

- Project with recordings
- Recording with various audio characteristics
- Recording with existing samples

## Special Considerations

1. **Audio Processing**: The actual audio processing should be mocked to avoid dependencies on audio processing libraries during testing.

2. **Processing Chain**: Tests should verify that processing stages can be chained together correctly.

3. **Error Handling**: Tests should verify that errors in one processing stage are properly handled and don't affect other stages.

4. **Performance**: Tests should verify that processing is performed efficiently and doesn't cause memory leaks.

5. **Concurrency**: If multiple processing requests can be handled concurrently, tests should verify that they don't interfere with each other.