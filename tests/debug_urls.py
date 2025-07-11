"""Debug script to check registered routes."""
from src.app import create_app

def print_urls():
    """Print all registered routes in the application."""
    app = create_app()
    print("\n=== Registered Routes ===")
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint}: {rule.rule} {rule.methods}")
    print("======================\n")

if __name__ == "__main__":
    print_urls()
