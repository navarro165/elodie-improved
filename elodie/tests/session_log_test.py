#!/usr/bin/env python
"""
Test the session logging functionality
"""

import json
import os
import sys
import tempfile
import shutil
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))))

from elodie.session_log import SessionLogger

os.environ['TZ'] = 'GMT'


def test_session_logger_initialization():
    """Test SessionLogger initialization."""
    logger = SessionLogger()
    assert logger.session_id is not None
    assert logger.log_dir is not None
    assert logger.session_data['session_id'] == logger.session_id
    assert logger.session_data['summary']['total_files'] == 0
    assert logger.session_data['summary']['successful'] == 0
    assert logger.session_data['summary']['failed'] == 0
    assert logger.session_data['summary']['skipped'] == 0
    assert logger.session_data['files_processed'] == []
    assert logger.session_data['errors'] == []


def test_session_logger_set_command():
    """Test SessionLogger set_command method."""
    logger = SessionLogger()
    
    command = 'import'
    args = {'destination': '/test/path', 'workers': 4}
    
    logger.set_command(command, args)
    
    assert logger.session_data['command'] == command
    assert logger.session_data['args'] == args


def test_session_logger_file_processing_success():
    """Test SessionLogger successful file processing logging."""
    logger = SessionLogger()
    
    source_file = '/path/to/source.jpg'
    dest_file = '/path/to/dest.jpg'
    
    logger.log_file_processed(source_file, dest_file, 'success')
    
    assert logger.session_data['summary']['successful'] == 1
    assert logger.session_data['summary']['total_files'] == 1
    assert len(logger.session_data['files_processed']) == 1
    
    file_record = logger.session_data['files_processed'][0]
    assert file_record['source'] == source_file
    assert file_record['destination'] == dest_file
    assert file_record['status'] == 'success'
    assert file_record['error_msg'] is None
    assert 'timestamp' in file_record


def test_session_logger_file_processing_failure():
    """Test SessionLogger failed file processing logging."""
    logger = SessionLogger()
    
    source_file = '/path/to/failed.jpg'
    error_msg = 'File not found'
    
    logger.log_file_processed(source_file, None, 'failed', error_msg)
    
    assert logger.session_data['summary']['failed'] == 1
    assert logger.session_data['summary']['total_files'] == 1
    assert len(logger.session_data['files_processed']) == 1
    
    file_record = logger.session_data['files_processed'][0]
    assert file_record['source'] == source_file
    assert file_record['destination'] is None
    assert file_record['status'] == 'failed'
    assert file_record['error_msg'] == error_msg


def test_session_logger_file_processing_skipped():
    """Test SessionLogger skipped file processing logging."""
    logger = SessionLogger()
    
    source_file = '/path/to/skipped.jpg'
    skip_reason = 'Already exists'
    
    logger.log_file_processed(source_file, None, 'skipped', skip_reason)
    
    assert logger.session_data['summary']['skipped'] == 1
    assert logger.session_data['summary']['total_files'] == 1
    assert len(logger.session_data['files_processed']) == 1
    
    file_record = logger.session_data['files_processed'][0]
    assert file_record['source'] == source_file
    assert file_record['destination'] is None
    assert file_record['status'] == 'skipped'
    assert file_record['error_msg'] == skip_reason


def test_session_logger_multiple_files():
    """Test SessionLogger with multiple file processing operations."""
    logger = SessionLogger()
    
    # Log multiple files
    logger.log_file_processed('/path/1.jpg', '/dest/1.jpg', 'success')
    logger.log_file_processed('/path/2.jpg', None, 'failed', 'Invalid format')
    logger.log_file_processed('/path/3.jpg', None, 'skipped', 'Duplicate')
    logger.log_file_processed('/path/4.jpg', '/dest/4.jpg', 'success')
    
    # Check summary
    assert logger.session_data['summary']['total_files'] == 4
    assert logger.session_data['summary']['successful'] == 2
    assert logger.session_data['summary']['failed'] == 1
    assert logger.session_data['summary']['skipped'] == 1
    assert len(logger.session_data['files_processed']) == 4


def test_session_logger_error_logging():
    """Test SessionLogger error logging."""
    logger = SessionLogger()
    
    error_msg = 'Test error message'
    context = 'test_context'
    
    logger.log_error(error_msg, context)
    
    assert len(logger.session_data['errors']) == 1
    error_record = logger.session_data['errors'][0]
    assert error_record['message'] == error_msg
    assert error_record['context'] == context
    assert 'timestamp' in error_record


def test_session_logger_multiple_errors():
    """Test SessionLogger with multiple error logging."""
    logger = SessionLogger()
    
    logger.log_error('First error', 'context1')
    logger.log_error('Second error', 'context2')
    
    assert len(logger.session_data['errors']) == 2
    assert logger.session_data['errors'][0]['message'] == 'First error'
    assert logger.session_data['errors'][1]['message'] == 'Second error'


def test_session_logger_finalization():
    """Test SessionLogger session finalization."""
    logger = SessionLogger()
    
    # Add some test data
    logger.set_command('import', {'destination': '/test'})
    logger.log_file_processed('/test.jpg', '/dest/test.jpg', 'success')
    
    # Finalize session
    log_file = logger.finalize_session()
    
    assert os.path.exists(log_file)
    assert log_file.endswith('.json')
    
    # Verify log file contents
    with open(log_file, 'r') as f:
        log_data = json.load(f)
    
    assert log_data['session_id'] == logger.session_id
    assert log_data['command'] == 'import'
    assert log_data['summary']['successful'] == 1
    assert 'end_time' in log_data
    assert 'duration_seconds' in log_data
    assert 'start_time' in log_data
    
    # Clean up
    os.remove(log_file)


def test_session_logger_print_summary():
    """Test SessionLogger print_summary method."""
    logger = SessionLogger()
    
    # Add test data
    logger.log_file_processed('/test1.jpg', '/dest/test1.jpg', 'success')
    logger.log_file_processed('/test2.jpg', None, 'failed', 'Error')
    logger.log_file_processed('/test3.jpg', None, 'skipped', 'Skip')
    
    # This should not raise an exception
    logger.print_summary()


def test_session_logger_thread_safety():
    """Test SessionLogger thread safety."""
    logger = SessionLogger()
    
    def worker(thread_id):
        for i in range(5):
            logger.log_file_processed(f'/thread_{thread_id}/file_{i}.jpg', 
                                    f'/dest/thread_{thread_id}/file_{i}.jpg', 
                                    'success')
    
    threads = []
    for i in range(3):
        thread = threading.Thread(target=worker, args=(i,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    # Should have processed 15 files total (3 threads * 5 files each)
    assert logger.session_data['summary']['total_files'] == 15
    assert logger.session_data['summary']['successful'] == 15
    assert len(logger.session_data['files_processed']) == 15


def test_session_logger_log_directory_creation():
    """Test SessionLogger creates log directory if it doesn't exist."""
    # Create a temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    log_dir = os.path.join(temp_dir, 'test_logs')
    
    try:
        # Create logger - should create the directory
        logger = SessionLogger()
        
        # The logger should create its own log directory
        assert os.path.exists(logger.log_dir)
        assert os.path.isdir(logger.log_dir)
        
    finally:
        # Clean up
        shutil.rmtree(temp_dir)


def test_session_logger_unique_session_ids():
    """Test that SessionLogger generates unique session IDs."""
    logger1 = SessionLogger()
    time.sleep(1.1)  # Ensure different timestamps (session IDs are second-based)
    logger2 = SessionLogger()
    
    assert logger1.session_id != logger2.session_id


def test_session_logger_duration_calculation():
    """Test that SessionLogger calculates duration correctly."""
    logger = SessionLogger()
    
    # Add a small delay
    time.sleep(0.1)
    
    log_file = logger.finalize_session()
    
    # Verify duration was calculated
    with open(log_file, 'r') as f:
        log_data = json.load(f)
    
    assert 'duration_seconds' in log_data
    assert log_data['duration_seconds'] > 0
    assert log_data['duration_seconds'] < 1  # Should be less than 1 second
    
    # Clean up
    os.remove(log_file)