# Recording Routes Integration Testing

This document outlines the integration testing requirements for the recording-related API routes in the Sample Orchestrator.

## Routes to Test

### 1. Get Recording Details (`GET /recordings/<recording_id>`)

#### Test Scenarios

- [ ] Successfully retrieve an existing recording
- [ ] Validate error handling for non-existent recording
- [ ] Verify database session is properly managed
- [ ] Verify response format and status code (200)

#### Validation Criteria

1. Response should include all recording fields
2. Response should include metadata
3. Response should include file path

### 2. Process Recording (`POST /recordings/<recording_id>/process`)

#### Test Scenarios

- [ ] Successfully process a recording using a predefined workflow
- [ ] Successfully process a recording using an ad-hoc chain of stages
- [ ] Validate error handling for missing workflow or stages
- [ ] Validate error handling for invalid workflow name
- [ ] Validate error handling for invalid stage parameters
- [ ] Validate error handling for non-existent recording
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

### 3. List Recording Samples (`GET /recordings/<recording_id>/samples`)

#### Test Scenarios

- [ ] Successfully list all samples for a recording
- [ ] Validate error handling for non-existent recording
- [ ] Verify database session is properly managed
- [ ] Verify response format and status code (200)

#### Validation Criteria

1. Response should be a list of samples
2. Each sample should include all fields
3. Only samples for the specified recording should be included

### 4. Upload Project Audio (`POST /projects/<project_id>/upload-audio`)

#### Test Scenarios

- [ ] Successfully upload audio file to a project
- [ ] Validate error handling for missing file
- [ ] Validate error handling for missing recording name
- [ ] Validate error handling for invalid file format
- [ ] Validate error handling for non-existent project
- [ ] Verify database session is properly managed
- [ ] Verify file is saved to correct location on filesystem
- [ ] Verify response format and status code (302 for redirect)

#### Test Data Requirements

- WAV audio file (1-3 seconds)
- Form data with recording name

#### Validation Criteria

1. Recording should be retrievable from database
2. Recording file should exist on filesystem
3. Recording should be associated with the correct project
4. Redirect should be to the correct page

## Mock Requirements

- Mock audio processing stages to avoid actual audio processing
- Mock file operations when needed
- Mock workflow execution

## Filesystem Fixtures

- Test recording files
- Test output directories

## Database Fixtures

- Project with recordings
- Recording with samples

## Special Considerations

1. **Audio Processing**: The actual audio processing should be mocked to avoid dependencies on audio processing libraries during testing.

2. **File Formats**: Tests should verify that only allowed file formats can be uploaded (WAV, AIFF).

3. **File Cleanup**: All test files should be cleaned up after tests run.

4. **Processing Stages**: Each processing stage should be tested individually in unit tests, but integration tests should verify that the stages can be chained together correctly.