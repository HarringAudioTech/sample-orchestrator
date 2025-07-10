"""Test blueprint for debugging route registration."""
from flask import Blueprint, jsonify

# Create a test blueprint
test_bp = Blueprint(
    "test_bp",
    __name__,
    url_prefix="/test"
)

@test_bp.route("/test-route")
def test_route():
    """A simple test route to check if the blueprint is working."""
    return jsonify({"message": "Test route is working!"})
