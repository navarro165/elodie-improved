"""Offline geolocation functionality for Elodie."""

import reverse_geocoder as rg
from elodie import log
from elodie.localstorage import Db

__DEFAULT_LOCATION__ = 'Unknown Location'


def coordinates_by_name(name):
    """Get coordinates for a location name using cached data."""
    # Try to get cached location first
    db = Db()
    cached_coordinates = db.get_location_coordinates(name)
    if cached_coordinates is not None:
        return {
            'latitude': cached_coordinates[0],
            'longitude': cached_coordinates[1]
        }
    
    # For offline mode, we can't do forward geocoding without an API
    # This would require a more comprehensive offline dataset
    log.warn(f"Cannot resolve coordinates for '{name}' in offline mode")
    return None


def decimal_to_dms(decimal):
    """Convert decimal degrees to degrees, minutes, seconds."""
    decimal = float(decimal)
    decimal_abs = abs(decimal)
    minutes, seconds = divmod(decimal_abs * 3600, 60)
    degrees, minutes = divmod(minutes, 60)
    degrees = degrees
    sign = 1 if decimal >= 0 else -1
    return (degrees, minutes, seconds, sign)


def dms_to_decimal(degrees, minutes, seconds, direction=' '):
    """Convert degrees, minutes, seconds to decimal degrees."""
    sign = 1
    if direction[0] in 'WSws':
        sign = -1
    return (float(degrees) + float(minutes) / 60 + float(seconds) / 3600) * sign


def dms_string(decimal, type='latitude'):
    """Convert decimal degrees to DMS string format."""
    # Example string -> 38 deg 14' 27.82" S
    dms = decimal_to_dms(decimal)
    if type == 'latitude':
        direction = 'N' if decimal >= 0 else 'S'
    elif type == 'longitude':
        direction = 'E' if decimal >= 0 else 'W'
    return '{} deg {}\' {}" {}'.format(dms[0], dms[1], dms[2], direction)


def place_name(lat, lon):
    """Get place name from coordinates using offline reverse geocoding."""
    lookup_place_name_default = {'default': __DEFAULT_LOCATION__}
    
    if lat is None or lon is None:
        return lookup_place_name_default
    
    # Convert lat/lon to floats
    if not isinstance(lat, float):
        lat = float(lat)
    if not isinstance(lon, float):
        lon = float(lon)
    
    # Try to get cached location first
    db = Db()
    # 3km distance radius for a match
    cached_place_name = db.get_location_name(lat, lon, 3000)
    # We check that it's a dict to coerce an upgrade of the location
    # db from a string location to a dictionary. See gh-160.
    if isinstance(cached_place_name, dict):
        return cached_place_name
    
    try:
        # Use reverse-geocoder for offline lookup
        results = rg.search([(lat, lon)])
        if results:
            result = results[0]
            lookup_place_name = {}
            
            # Map reverse-geocoder fields to our expected format
            if 'name' in result:
                lookup_place_name['city'] = result['name']
                lookup_place_name['default'] = result['name']
            
            if 'admin1' in result:
                lookup_place_name['state'] = result['admin1']
                if 'default' not in lookup_place_name:
                    lookup_place_name['default'] = result['admin1']
            
            if 'cc' in result:
                lookup_place_name['country'] = result['cc']
                if 'default' not in lookup_place_name:
                    lookup_place_name['default'] = result['cc']
            
            if lookup_place_name:
                # Cache the result
                db.add_location(lat, lon, lookup_place_name)
                db.update_location_db()
                return lookup_place_name
    
    except Exception as e:
        log.error(f"Error in offline reverse geocoding: {e}")
    
    return lookup_place_name_default


def lookup(**kwargs):
    """Offline lookup function - limited functionality."""
    if 'lat' in kwargs and 'lon' in kwargs:
        result = place_name(kwargs['lat'], kwargs['lon'])
        return {
            'address': {
                'city': result.get('city'),
                'state': result.get('state'),
                'country': result.get('country')
            }
        }
    
    # Forward geocoding not supported in offline mode
    return None


# Compatibility functions for existing code
def get_key():
    """Compatibility function - no key needed for offline mode."""
    return "offline"


def get_prefer_english_names():
    """Compatibility function - always prefer English names."""
    return True