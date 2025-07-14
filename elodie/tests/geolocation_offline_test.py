#!/usr/bin/env python
"""
Test the offline geolocation functionality
"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))))

from elodie.geolocation_offline import place_name, coordinates_by_name

os.environ['TZ'] = 'GMT'


def test_place_name_with_valid_coordinates():
    """Test offline place name lookup with valid coordinates."""
    # Test San Francisco coordinates
    result = place_name(37.7749, -122.4194)
    assert isinstance(result, dict)
    assert 'default' in result
    assert result['default'] != 'Unknown Location'
    
    # Test specific fields that should be present
    assert 'city' in result
    assert 'state' in result
    assert 'country' in result


def test_place_name_with_invalid_coordinates():
    """Test offline place name lookup with invalid coordinates."""
    # Test with None coordinates
    result = place_name(None, None)
    assert isinstance(result, dict)
    assert result['default'] == 'Unknown Location'
    
    # Test with missing coordinates
    result = place_name(None, -122.4194)
    assert isinstance(result, dict)
    assert result['default'] == 'Unknown Location'
    
    # Test with one None coordinate
    result = place_name(37.7749, None)
    assert isinstance(result, dict)
    assert result['default'] == 'Unknown Location'


def test_place_name_with_edge_case_coordinates():
    """Test offline place name lookup with edge case coordinates."""
    # Test coordinates at the edge of valid ranges
    result = place_name(90.0, 180.0)  # North pole, international date line
    assert isinstance(result, dict)
    assert 'default' in result
    
    result = place_name(-90.0, -180.0)  # South pole, international date line
    assert isinstance(result, dict)
    assert 'default' in result


def test_place_name_format_consistency():
    """Test that place name results have consistent format."""
    # Test with New York coordinates
    result = place_name(40.7128, -74.0060)
    assert isinstance(result, dict)
    
    # Check that all expected keys are present
    required_keys = ['default', 'city', 'state', 'country']
    for key in required_keys:
        assert key in result, f"Key '{key}' missing from result"
        assert isinstance(result[key], str), f"Key '{key}' should be string"


def test_coordinates_by_name_returns_none():
    """Test that coordinates_by_name returns None (offline mode)."""
    # Forward geocoding is not supported in offline mode
    result = coordinates_by_name('San Francisco')
    assert result is None
    
    result = coordinates_by_name('New York')
    assert result is None
    
    result = coordinates_by_name('Invalid Location')
    assert result is None
    
    result = coordinates_by_name('')
    assert result is None


def test_place_name_caching():
    """Test that repeated calls to place_name work correctly."""
    # This tests the underlying reverse_geocoder caching
    coords = (40.7128, -74.0060)  # New York
    
    result1 = place_name(coords[0], coords[1])
    result2 = place_name(coords[0], coords[1])
    
    # Results should be identical for same coordinates
    assert result1 == result2
    assert result1['default'] == result2['default']


def test_place_name_with_various_locations():
    """Test place name lookup with various global locations."""
    test_locations = [
        (51.5074, -0.1278),   # London
        (35.6762, 139.6503),  # Tokyo
        (-33.8688, 151.2093), # Sydney
        (48.8566, 2.3522),    # Paris
    ]
    
    for lat, lon in test_locations:
        result = place_name(lat, lon)
        assert isinstance(result, dict)
        assert 'default' in result
        assert result['default'] != 'Unknown Location'
        assert result['city'] is not None
        assert result['country'] is not None