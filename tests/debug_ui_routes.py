"""Debug script to check UI route registration."""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import create_app
from src.ui.routes import ui_bp

def print_routes():
    """Print all registered routes in the UI blueprint."""
    # Create a test app
    app = create_app()
    
    # Print all routes in the app
    print("\n=== All Registered Routes ===")
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint}: {rule.rule} {rule.methods}")
    
    # Print routes in the UI blueprint
    print("\n=== UI Blueprint Routes ===")
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith('ui_bp.'):
            print(f"{rule.endpoint}: {rule.rule} {rule.methods}")
    
    # Print all functions in the UI blueprint
    print("\n=== UI Blueprint View Functions ===")
    for name, func in ui_bp.view_functions.items():
        print(f"{name}: {func.__name__} (module: {func.__module__})")

if __name__ == "__main__":
    print_routes()
