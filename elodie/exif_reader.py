"""Enhanced EXIF reader using ExifRead for better parallel processing."""

import exifread
import os
from datetime import datetime
from elodie import log


class ExifReader:
    """Thread-safe EXIF reader using ExifRead library."""
    
    def __init__(self):
        pass
    
    def get_metadata(self, file_path):
        """Get EXIF metadata from a file."""
        try:
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
            
            # Convert ExifRead tags to our expected format
            metadata = {}
            
            # Date and time
            date_taken = self._get_date_taken(tags)
            if date_taken:
                metadata['DateTime'] = date_taken
                metadata['DateTimeOriginal'] = date_taken
            
            # GPS coordinates
            gps_info = self._get_gps_info(tags)
            if gps_info:
                metadata.update(gps_info)
            
            # Camera info
            camera_info = self._get_camera_info(tags)
            metadata.update(camera_info)
            
            # Image info
            image_info = self._get_image_info(tags)
            metadata.update(image_info)
            
            return metadata
            
        except Exception as e:
            log.error(f"Error reading EXIF data from {file_path}: {e}")
            return {}
    
    def _get_date_taken(self, tags):
        """Extract date taken from EXIF tags."""
        date_tags = [
            'EXIF DateTimeOriginal',
            'EXIF DateTime',
            'Image DateTime'
        ]
        
        for tag in date_tags:
            if tag in tags:
                try:
                    date_str = str(tags[tag])
                    # Parse the date string
                    return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S').strftime('%Y:%m:%d %H:%M:%S')
                except ValueError:
                    continue
        
        return None
    
    def _get_gps_info(self, tags):
        """Extract GPS information from EXIF tags."""
        gps_info = {}
        
        # GPS Latitude
        if 'GPS GPSLatitude' in tags and 'GPS GPSLatitudeRef' in tags:
            lat_ref = str(tags['GPS GPSLatitudeRef'])
            lat_values = tags['GPS GPSLatitude'].values
            if len(lat_values) >= 3:
                lat_decimal = self._dms_to_decimal(lat_values[0], lat_values[1], lat_values[2], lat_ref)
                gps_info['GPS GPSLatitude'] = lat_decimal
                gps_info['GPS GPSLatitudeRef'] = lat_ref
        
        # GPS Longitude
        if 'GPS GPSLongitude' in tags and 'GPS GPSLongitudeRef' in tags:
            lon_ref = str(tags['GPS GPSLongitudeRef'])
            lon_values = tags['GPS GPSLongitude'].values
            if len(lon_values) >= 3:
                lon_decimal = self._dms_to_decimal(lon_values[0], lon_values[1], lon_values[2], lon_ref)
                gps_info['GPS GPSLongitude'] = lon_decimal
                gps_info['GPS GPSLongitudeRef'] = lon_ref
        
        # GPS Altitude
        if 'GPS GPSAltitude' in tags:
            gps_info['GPS GPSAltitude'] = float(tags['GPS GPSAltitude'].values[0])
        
        return gps_info
    
    def _get_camera_info(self, tags):
        """Extract camera information from EXIF tags."""
        camera_info = {}
        
        # Camera make and model
        if 'Image Make' in tags:
            camera_info['Image Make'] = str(tags['Image Make'])
        
        if 'Image Model' in tags:
            camera_info['Image Model'] = str(tags['Image Model'])
        
        # Camera settings
        if 'EXIF FNumber' in tags:
            camera_info['EXIF FNumber'] = float(tags['EXIF FNumber'].values[0])
        
        if 'EXIF ExposureTime' in tags:
            camera_info['EXIF ExposureTime'] = float(tags['EXIF ExposureTime'].values[0])
        
        if 'EXIF ISOSpeedRatings' in tags:
            camera_info['EXIF ISOSpeedRatings'] = int(tags['EXIF ISOSpeedRatings'].values[0])
        
        if 'EXIF FocalLength' in tags:
            camera_info['EXIF FocalLength'] = float(tags['EXIF FocalLength'].values[0])
        
        return camera_info
    
    def _get_image_info(self, tags):
        """Extract image information from EXIF tags."""
        image_info = {}
        
        if 'Image ImageWidth' in tags:
            image_info['Image ImageWidth'] = int(tags['Image ImageWidth'].values[0])
        
        if 'Image ImageLength' in tags:
            image_info['Image ImageLength'] = int(tags['Image ImageLength'].values[0])
        
        if 'Image Orientation' in tags:
            image_info['Image Orientation'] = int(tags['Image Orientation'].values[0])
        
        return image_info
    
    def _dms_to_decimal(self, degrees, minutes, seconds, direction):
        """Convert degrees, minutes, seconds to decimal degrees."""
        decimal = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
        if direction in ['S', 'W']:
            decimal = -decimal
        return decimal
    
    def supports_file(self, file_path):
        """Check if file is supported for EXIF reading."""
        supported_extensions = ['.jpg', '.jpeg', '.tiff', '.tif', '.nef', '.cr2', '.arw', '.dng']
        _, ext = os.path.splitext(file_path.lower())
        return ext in supported_extensions


# Global instance for reuse
exif_reader = ExifReader()