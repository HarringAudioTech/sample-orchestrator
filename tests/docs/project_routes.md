# Project Routes Integration Testing

This document outlines the integration testing requirements for the project-related API routes in the Sample Orchestrator.

## Routes to Test

### 1. Create Project (`POST /projects`)

#### Test Scenarios

- [ ] Successfully create a sample pack project
- [ ] Successfully create a virtual instrument project
- [ ] Validate error handling for missing required fields
- [ ] Validate error handling for invalid project types
- [ ] Validate error handling for invalid virtual instrument parameters
- [ ] Verify database session is properly managed (opened and closed)
- [ ] Verify project directory is created on filesystem
- [ ] Verify response format and status code (201)

#### Test Data Requirements

```json
// Sample pack project
{
  "name": "Test Sample Pack",
  "project_type": "sample_pack",
  "description": "Test description"
}

// Virtual instrument project
{
  "name": "Test Virtual Instrument",
  "project_type": "virtual_instrument",
  "description": "Test description",
  "base_note": 60,
  "velocity_layers": 3,
  "round_robins": 2,
  "metadata_json": {"instrument_type": "piano"}
}
```

#### Validation Criteria

1. Response should include all project fields
2. Project should be retrievable from database
3. Project directory should exist on filesystem
4. ProjectType enum values must match exactly what's in the database

### 2. Get Project (`GET /projects/<project_id>`)

#### Test Scenarios

- [ ] Successfully retrieve an existing sample pack project
- [ ] Successfully retrieve an existing virtual instrument project
- [ ] Validate error handling for non-existent project
- [ ] Verify database session is properly managed
- [ ] Verify response format and status code (200)

#### Validation Criteria

1. Response should include all project fields
2. Response should include computed fields (e.g., `is_virtual_instrument`)
3. Response should include proper project type

### 3. List Projects (`GET /projects`)

#### Test Scenarios

- [ ] Successfully list all projects
- [ ] Successfully filter projects by type (sample_pack)
- [ ] Successfully filter projects by type (virtual_instrument)
- [ ] Validate error handling for invalid filter parameters
- [ ] Verify database session is properly managed
- [ ] Verify response format and status code (200)

#### Validation Criteria

1. Response should be a list of projects
2. Each project should include all fields
3. Filtering should work correctly
4. Projects should be ordered by created_at (descending)

### 4. Add Project Recording (`POST /projects/<project_id>/recordings`)

#### Test Scenarios

- [ ] Successfully upload and add a recording to a project
- [ ] Validate error handling for missing file
- [ ] Validate error handling for missing name
- [ ] Validate error handling for invalid file format
- [ ] Validate error handling for non-existent project
- [ ] Verify database session is properly managed
- [ ] Verify file is saved to correct location on filesystem
- [ ] Verify response format and status code (201)

#### Test Data Requirements

- WAV audio file (1-3 seconds)
- Form data with recording name

#### Validation Criteria

1. Response should include all recording fields
2. Recording should be retrievable from database
3. Recording file should exist on filesystem
4. Recording should be associated with the correct project

### 5. List Project Recordings (`GET /projects/<project_id>/recordings`)

#### Test Scenarios

- [ ] Successfully list all recordings for a project
- [ ] Validate error handling for non-existent project
- [ ] Verify database session is properly managed
- [ ] Verify response format and status code (200)

#### Validation Criteria

1. Response should be a list of recordings
2. Each recording should include all fields
3. Only recordings for the specified project should be included

## Mock Requirements

- Mock `ProjectManager.create_project_directory` to avoid actual filesystem operations
- Mock `ProjectManager.get_project_upload_dir` to return a test directory
- Mock file operations when needed

## Filesystem Fixtures

- Test project directories
- Test upload directories

## Database Fixtures

- Sample pack project
- Virtual instrument project
- Project with recordings

## Special Considerations

1. **ProjectType Enum Values**: Ensure that the ProjectType enum values in code match exactly what's in the database. The tests should verify that 'sample_pack' and 'virtual_instrument' are used consistently.

2. **SamplePack Model**: The `sample_count` property is read-only and should not be set directly. Tests should verify this behavior.

3. **File Cleanup**: All test files should be cleaned up after tests run.

4. **Database Reset**: The database should be reset between tests to ensure test isolation.