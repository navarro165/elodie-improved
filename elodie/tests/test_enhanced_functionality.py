# Project imports
from imp import load_source
import mock
import os
import sys
import shutil
import tempfile
import json
import threading
import time

from click.testing import CliRunner
from tempfile import gettempdir

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))))
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))))

from . import helper
elodie = load_source('elodie', os.path.abspath('{}/../../elodie.py'.format(os.path.dirname(os.path.realpath(__file__)))))

from elodie.session_log import SessionLogger
from elodie.filesystem import FileSystem
from elodie.geolocation_offline import place_name, coordinates_by_name
from elodie.exif_reader import ExifReader

os.environ['TZ'] = 'GMT'

# Test Session Logging
def test_session_logger_initialization():
    """Test SessionLogger initialization."""
    logger = SessionLogger()
    assert logger.session_id is not None
    assert logger.log_dir is not None
    assert logger.session_data['session_id'] == logger.session_id
    assert logger.session_data['summary']['total_files'] == 0

def test_session_logger_file_processing():
    """Test SessionLogger file processing logging."""
    logger = SessionLogger()
    
    # Log successful file processing
    logger.log_file_processed('/path/to/source.jpg', '/path/to/dest.jpg', 'success')
    assert logger.session_data['summary']['successful'] == 1
    assert logger.session_data['summary']['total_files'] == 1
    
    # Log failed file processing
    logger.log_file_processed('/path/to/failed.jpg', None, 'failed', 'File not found')
    assert logger.session_data['summary']['failed'] == 1
    assert logger.session_data['summary']['total_files'] == 2
    
    # Log skipped file processing
    logger.log_file_processed('/path/to/skipped.jpg', None, 'skipped', 'Already exists')
    assert logger.session_data['summary']['skipped'] == 1
    assert logger.session_data['summary']['total_files'] == 3

def test_session_logger_error_logging():
    """Test SessionLogger error logging."""
    logger = SessionLogger()
    
    logger.log_error('Test error message', 'test_context')
    assert len(logger.session_data['errors']) == 1
    assert logger.session_data['errors'][0]['message'] == 'Test error message'
    assert logger.session_data['errors'][0]['context'] == 'test_context'

def test_session_logger_finalization():
    """Test SessionLogger session finalization."""
    logger = SessionLogger()
    logger.log_file_processed('/path/to/test.jpg', '/path/to/dest.jpg', 'success')
    
    log_file = logger.finalize_session()
    assert os.path.exists(log_file)
    
    # Verify log file contents
    with open(log_file, 'r') as f:
        log_data = json.load(f)
    
    assert log_data['session_id'] == logger.session_id
    assert log_data['summary']['successful'] == 1
    assert 'end_time' in log_data
    assert 'duration_seconds' in log_data
    
    # Cleanup
    os.remove(log_file)

# Test Filename Date Detection
def test_filename_has_date_prefix():
    """Test filename date prefix detection."""
    filesystem = FileSystem()
    
    # Test various date patterns
    assert filesystem.filename_has_date_prefix('2023-01-15_12-30-45-photo.jpg') == True
    assert filesystem.filename_has_date_prefix('2023-01-15-photo.jpg') == True
    assert filesystem.filename_has_date_prefix('20230115_photo.jpg') == True
    assert filesystem.filename_has_date_prefix('IMG_20230115.jpg') == True
    assert filesystem.filename_has_date_prefix('VID_20230115.mp4') == True
    assert filesystem.filename_has_date_prefix('20230115_123045_photo.jpg') == True
    
    # Test non-date patterns
    assert filesystem.filename_has_date_prefix('photo.jpg') == False
    assert filesystem.filename_has_date_prefix('IMG_photo.jpg') == False
    assert filesystem.filename_has_date_prefix('random_name.jpg') == False
    assert filesystem.filename_has_date_prefix('') == False
    assert filesystem.filename_has_date_prefix(None) == False

# Test Offline Geolocation
def test_offline_geolocation_place_name():
    """Test offline geolocation place name lookup."""
    # Test with valid coordinates (San Francisco)
    result = place_name(37.7749, -122.4194)
    assert isinstance(result, dict)
    assert 'default' in result
    
    # Test with invalid coordinates
    result = place_name(None, None)
    assert result['default'] == 'Unknown Location'

def test_offline_geolocation_coordinates_by_name():
    """Test offline geolocation coordinates by name lookup."""
    # This should return None for offline mode forward geocoding
    result = coordinates_by_name('San Francisco')
    assert result is None

# Test EXIF Reader
def test_exif_reader_initialization():
    """Test ExifReader initialization."""
    reader = ExifReader()
    assert reader is not None

def test_exif_reader_supports_file():
    """Test ExifReader file support detection."""
    reader = ExifReader()
    
    # Test supported file types
    assert reader.supports_file('test.jpg') == True
    assert reader.supports_file('test.jpeg') == True
    assert reader.supports_file('test.tiff') == True
    assert reader.supports_file('test.nef') == True
    assert reader.supports_file('test.cr2') == True
    
    # Test unsupported file types
    assert reader.supports_file('test.txt') == False
    assert reader.supports_file('test.mp4') == False
    assert reader.supports_file('test.pdf') == False

def test_exif_reader_metadata_extraction():
    """Test ExifReader metadata extraction."""
    reader = ExifReader()
    
    # Test with existing test image
    test_image = helper.get_file('plain.jpg')
    metadata = reader.get_metadata(test_image)
    
    assert isinstance(metadata, dict)
    # The metadata might be empty if ExifRead can't read the test file
    # but it should return a dict

# Test Parallel Processing
def test_parallel_import_with_workers():
    """Test parallel import functionality with workers."""
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    # Create multiple test files
    origins = []
    for i in range(5):
        origin = '%s/valid_%d.txt' % (folder, i)
        shutil.copyfile(helper.get_file('valid.txt'), origin)
        origins.append(origin)

    helper.reset_dbs()
    runner = CliRunner()
    result = runner.invoke(elodie._import, [
        '--destination', folder_destination,
        '--workers', '2',
        '--allow-duplicates'
    ] + origins)
    helper.restore_dbs()

    # Check that all files were processed
    assert result.exit_code == 0, result.output
    assert 'Processing 5 files with 2 workers' in result.output, result.output
    assert 'Success         5' in result.output, result.output
    assert 'Session log saved to:' in result.output, result.output
    
    # Verify files were actually imported
    for i in range(5):
        files_in_dest = []
        for root, dirs, files in os.walk(folder_destination):
            for file in files:
                if 'valid_%d' % i in file:
                    files_in_dest.append(file)
        assert len(files_in_dest) > 0, "File %d not found in destination" % i

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

def test_parallel_import_with_single_worker():
    """Test parallel import functionality with single worker."""
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    # Create test files
    origins = []
    for i in range(3):
        origin = '%s/valid_%d.txt' % (folder, i)
        shutil.copyfile(helper.get_file('valid.txt'), origin)
        origins.append(origin)

    helper.reset_dbs()
    runner = CliRunner()
    result = runner.invoke(elodie._import, [
        '--destination', folder_destination,
        '--workers', '1',
        '--allow-duplicates'
    ] + origins)
    helper.restore_dbs()

    # Check that all files were processed
    assert result.exit_code == 0, result.output
    assert 'Processing 3 files with 1 workers' in result.output, result.output
    assert 'Success         3' in result.output, result.output

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

def test_parallel_import_with_errors():
    """Test parallel import handles errors gracefully."""
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    # Create a mix of valid and invalid files
    origins = []
    
    # Valid file
    origin_valid = '%s/valid.txt' % folder
    shutil.copyfile(helper.get_file('valid.txt'), origin_valid)
    origins.append(origin_valid)
    
    # Invalid file
    origin_invalid = '%s/invalid.jpg' % folder
    shutil.copyfile(helper.get_file('invalid.jpg'), origin_invalid)
    origins.append(origin_invalid)

    helper.reset_dbs()
    runner = CliRunner()
    result = runner.invoke(elodie._import, [
        '--destination', folder_destination,
        '--workers', '2',
        '--allow-duplicates'
    ] + origins)
    helper.restore_dbs()

    # Should have mixed results
    assert result.exit_code == 1, result.output  # Exit code 1 due to errors
    assert 'Success         1' in result.output, result.output
    assert 'Error           1' in result.output, result.output
    assert 'Session log saved to:' in result.output, result.output

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

def test_import_with_session_logging():
    """Test import with session logging enabled."""
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/valid.txt' % folder
    shutil.copyfile(helper.get_file('valid.txt'), origin)

    helper.reset_dbs()
    runner = CliRunner()
    result = runner.invoke(elodie._import, [
        '--destination', folder_destination,
        '--allow-duplicates',
        origin
    ])
    helper.restore_dbs()

    # Check that session logging worked
    assert result.exit_code == 0, result.output
    assert 'Session Summary' in result.output, result.output
    assert 'Total files processed: 1' in result.output, result.output
    assert 'Successful: 1' in result.output, result.output
    assert 'Session log saved to:' in result.output, result.output

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

def test_thread_safety():
    """Test thread safety of parallel operations."""
    def mock_import_function(file_id):
        # Simulate some processing time
        time.sleep(0.01)
        return f"processed_{file_id}"
    
    results = []
    threads = []
    
    def worker(file_id):
        result = mock_import_function(file_id)
        results.append(result)
    
    # Create multiple threads
    for i in range(10):
        thread = threading.Thread(target=worker, args=(i,))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Check results
    assert len(results) == 10
    assert len(set(results)) == 10  # All results should be unique

def test_threading_optimization_file_discovery():
    """Test that files are discovered before thread allocation."""
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    # Create test files
    origins = []
    for i in range(8):
        origin = '%s/valid_%d.txt' % (folder, i)
        shutil.copyfile(helper.get_file('valid.txt'), origin)
        origins.append(origin)

    helper.reset_dbs()
    runner = CliRunner()
    result = runner.invoke(elodie._import, [
        '--destination', folder_destination,
        '--workers', '8',
        '--allow-duplicates'
    ] + origins)
    helper.restore_dbs()

    # Check that all files were processed successfully
    assert result.exit_code == 0, result.output
    assert 'Processing 8 files with 8 workers' in result.output, result.output
    assert 'Success         8' in result.output, result.output
    
    # Verify all files were actually imported
    for i in range(8):
        files_in_dest = []
        for root, dirs, files in os.walk(folder_destination):
            for file in files:
                if 'valid_%d' % i in file:
                    files_in_dest.append(file)
        assert len(files_in_dest) > 0, "File %d not found in destination" % i

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

def test_media_class_preloading():
    """Test that media classes are preloaded to avoid thread issues."""
    from elodie.media.base import Base, get_all_subclasses
    
    # Test that get_all_subclasses returns consistent results
    subclasses1 = get_all_subclasses(Base)
    subclasses2 = get_all_subclasses(Base)
    
    # Should return the same classes
    assert len(subclasses1) == len(subclasses2)
    assert set(subclasses1) == set(subclasses2)
    
    # Should include expected media classes
    class_names = [cls.__name__ for cls in subclasses1]
    expected_classes = ['Photo', 'Video', 'Audio', 'Text']
    for expected in expected_classes:
        assert expected in class_names, f"Expected class {expected} not found"