#!/usr/bin/env python3
"""
Test script for the Sample Orchestrator API endpoints.
This script tests the project creation and listing functionality with the new project_type field.
"""

import json
import requests
import sys
from typing import Dict, Any, Optional

# Base URL of the API
BASE_URL = "http://localhost:5000"  # Update if your API runs on a different port

def create_project(project_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Helper function to create a new project."""
    url = f"{BASE_URL}/projects"
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=project_data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error creating project: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None

def list_projects(project_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Helper function to list projects, optionally filtered by type."""
    url = f"{BASE_URL}/projects"
    params = {}
    if project_type:
        params["project_type"] = project_type
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error listing projects: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None

def main():
    print("=== Testing Sample Orchestrator API ===\n")
    
    # Test 1: Create a sample pack project
    print("Test 1: Creating a sample pack project...")
    sample_pack = {
        "name": "Test Drum Kit",
        "project_type": "sample_pack",
        "description": "A test drum kit sample pack"
    }
    created_sample_pack = create_project(sample_pack)
    if created_sample_pack:
        print("✅ Successfully created sample pack project:")
        print(json.dumps(created_sample_pack, indent=2))
    else:
        print("❌ Failed to create sample pack project")
        return
    
    print("\n---\n")
    
    # Test 2: Create a virtual instrument project
    print("Test 2: Creating a virtual instrument project...")
    virtual_instrument = {
        "name": "Test Piano",
        "project_type": "virtual_instrument",
        "description": "A test piano virtual instrument",
        "base_note": 60,  # Middle C
        "velocity_layers": 3,
        "round_robins": 2,
        "metadata_json": {
            "instrument_type": "piano",
            "tuning": "A440",
            "notes": "This is a test virtual instrument"
        }
    }
    created_vi = create_project(virtual_instrument)
    if created_vi:
        print("✅ Successfully created virtual instrument project:")
        print(json.dumps(created_vi, indent=2))
    else:
        print("❌ Failed to create virtual instrument project")
        return
    
    print("\n---\n")
    
    # Test 3: List all projects
    print("Test 3: Listing all projects...")
    all_projects = list_projects()
    if all_projects and isinstance(all_projects, list):
        print(f"✅ Found {len(all_projects)} projects:")
        for i, project in enumerate(all_projects, 1):
            print(f"{i}. {project['name']} ({project['project_type']})")
    else:
        print("❌ Failed to list projects")
        return
    
    print("\n---\n")
    
    # Test 4: Filter projects by type
    print("Test 4: Filtering projects by type 'virtual_instrument'...")
    vi_projects = list_projects(project_type="virtual_instrument")
    if vi_projects and isinstance(vi_projects, list):
        print(f"✅ Found {len(vi_projects)} virtual instrument projects:")
        for project in vi_projects:
            print(f"- {project['name']} (Base note: {project.get('base_note', 'N/A')}, "
                  f"Velocity layers: {project.get('velocity_layers', 'N/A')}, "
                  f"Round robins: {project.get('round_robins', 'N/A')})")
    else:
        print("❌ Failed to filter virtual instrument projects")
        return
    
    print("\n=== All tests completed successfully! ===")

if __name__ == "__main__":
    main()
