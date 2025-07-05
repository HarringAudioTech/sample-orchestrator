# Project Development Plan

## Overall Strategy
The primary goal is to extend the application to support two distinct project types: **Virtual Instruments** and **Sample Packs**. This requires foundational changes to the data model and branching UI/API logic based on the selected project type.

---

## Phase 1: Foundational Changes - Project Types

1.  **Update Database Model:**
    *   Modify the `ProjectModel` in `src/database/models.py`.
    *   Add a `project_type` field (e.g., String) to distinguish between "Virtual Instrument" and "Sample Pack".

2.  **Update Project Creation (API):**
    *   Modify the `POST /projects` endpoint in `src/api/routes.py`.
    *   Require a `project_type` field in the JSON payload.

3.  **Update Project Creation (UI):**
    *   Modify the `create_project.html` template to include a dropdown or radio buttons for selecting the project type.
    *   Implement the logic in the `/ui/projects/create` route in `src/ui/routes.py` to handle the form submission and call the updated API.

---

## Phase 2: "Virtual Instrument" Workflow

This phase focuses on integrating the existing `DecentSamplerPresetGenerator`.

1.  **Create API Endpoint:**
    *   Add a new route: `POST /projects/<int:project_id>/dspreset` in `src/api/routes.py`.
    *   This endpoint will be responsible for initiating the `.dspreset` generation.
    *   It should only be available for projects with `project_type` of "Virtual Instrument".
    *   It will accept instrument metadata (name, author) and a list of sample IDs. It should also handle an optional file upload for UI artwork.

2.  **Create UI:**
    *   Create a new `generate_dspreset.html` template for a form to collect instrument metadata, select samples, and upload artwork.
    *   Add a `GET /projects/<int:project_id>/dspreset` route to `src/ui/routes.py` to render this page.
    *   Add a `POST` route to handle the form submission, which will call the new API endpoint.
    *   Update the `dashboard.html` template to show a "Generate Instrument" button/link, but *only* for "Virtual Instrument" projects.

---

## Phase 3: "Sample Pack" Workflow & Sample Librarian

This phase focuses on building out features for managing collections of samples.

1.  **Research Open-Source Sample Librarian:**
    *   Investigate existing open-source sample librarian tools.
    *   **Constraint:** The tool should be written in Python or Rust to facilitate easy integration.
    *   The goal is to find a suitable backend/frontend component to accelerate development.

2.  **Define Core Librarian Features:**
    *   **UI:** A grid or list view for browsing samples with waveform visualization.
    *   **Metadata:** Support for viewing, adding, and editing tags (e.g., "loop", "one-shot", "kick", key, BPM).
    *   **Search/Filter:** Robust filtering based on filename and metadata tags.
    *   **Audio Preview:** In-browser playback of samples.
    *   **Export:** Functionality to select multiple samples and download them as a `.zip` archive.

3.  **Propose Implementation Plan:**
    *   Based on the research, present a final plan. This will either be a plan to integrate an existing tool or a plan to build the librarian functionality from scratch.
