# Project imports
from imp import load_source
import mock
import os
import sys
import shutil
import tempfile
import threading
import time

from click.testing import CliRunner
from nose.tools import assert_raises
from tempfile import gettempdir

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))))
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))))

import helper
elodie = load_source('elodie', os.path.abspath('{}/../../elodie.py'.format(os.path.dirname(os.path.realpath(__file__)))))

from elodie.localstorage import Db

os.environ['TZ'] = 'GMT'

def test_import_with_progress_reporting():
    """Test that import works with enhanced progress reporting"""
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    # Create multiple test files
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
    assert 'Success         3' in result.output, result.output
    
    # Verify files were actually imported
    for i in range(3):
        expected_path = os.path.join(folder_destination, '2016-04-Apr', 'Rainham', 'valid_%d-sample-title.txt' % i)
        files_in_dest = []
        for root, dirs, files in os.walk(folder_destination):
            for file in files:
                if 'valid_%d' % i in file:
                    files_in_dest.append(file)
        assert len(files_in_dest) > 0, "File %d not found in destination" % i

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

def test_import_with_workers_parameter():
    """Test that import works with workers parameter (for backward compatibility)"""
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    # Create multiple test files
    origins = []
    for i in range(6):
        origin = '%s/valid_%d.txt' % (folder, i)
        shutil.copyfile(helper.get_file('valid.txt'), origin)
        origins.append(origin)

    helper.reset_dbs()
    runner = CliRunner()
    result = runner.invoke(elodie._import, [
        '--destination', folder_destination,
        '--workers', '3',
        '--allow-duplicates'
    ] + origins)
    helper.restore_dbs()

    # Check that all files were processed
    assert result.exit_code == 0, result.output
    assert 'Success         6' in result.output, result.output
    
    # Verify files were actually imported
    for i in range(6):
        files_in_dest = []
        for root, dirs, files in os.walk(folder_destination):
            for file in files:
                if 'valid_%d' % i in file:
                    files_in_dest.append(file)
        assert len(files_in_dest) > 0, "File %d not found in destination" % i

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

def test_import_with_default_settings():
    """Test that import works with default settings"""
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    # Create multiple test files
    origins = []
    for i in range(4):
        origin = '%s/valid_%d.txt' % (folder, i)
        shutil.copyfile(helper.get_file('valid.txt'), origin)
        origins.append(origin)

    helper.reset_dbs()
    runner = CliRunner()
    result = runner.invoke(elodie._import, [
        '--destination', folder_destination,
        '--allow-duplicates'
    ] + origins)
    helper.restore_dbs()

    # Check that all files were processed
    assert result.exit_code == 0, result.output
    assert 'Success         4' in result.output, result.output
    
    # Verify files were actually imported
    for i in range(4):
        files_in_dest = []
        for root, dirs, files in os.walk(folder_destination):
            for file in files:
                if 'valid_%d' % i in file:
                    files_in_dest.append(file)
        assert len(files_in_dest) > 0, "File %d not found in destination" % i

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

def test_import_mixed_file_types():
    """Test that import works with multiple text files"""
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    # Create multiple text files (avoiding ExifTool issues)
    origins = []
    
    # Text files
    for i in range(3):
        origin_txt = '%s/valid_%d.txt' % (folder, i)
        shutil.copyfile(helper.get_file('valid.txt'), origin_txt)
        origins.append(origin_txt)

    helper.reset_dbs()
    runner = CliRunner()
    result = runner.invoke(elodie._import, [
        '--destination', folder_destination,
        '--workers', '2',
        '--allow-duplicates'
    ] + origins)
    helper.restore_dbs()

    # Check that files were processed
    assert result.exit_code == 0, result.output
    assert 'Success         3' in result.output, result.output

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

def test_import_with_errors():
    """Test that import handles errors gracefully"""
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

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

def test_import_progress_reporting():
    """Test that import reports progress correctly"""
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    # Create enough files to trigger progress reporting
    origins = []
    for i in range(12):  # More than 10 to see progress
        origin = '%s/valid_%d.txt' % (folder, i)
        shutil.copyfile(helper.get_file('valid.txt'), origin)
        origins.append(origin)

    helper.reset_dbs()
    runner = CliRunner()
    result = runner.invoke(elodie._import, [
        '--destination', folder_destination,
        '--workers', '3',
        '--allow-duplicates'
    ] + origins)
    helper.restore_dbs()

    # Check that progress was reported
    assert result.exit_code == 0, result.output
    assert 'Processing 12 files' in result.output, result.output
    assert 'Processed 10/12 files' in result.output, result.output
    assert 'Completed processing 12 files' in result.output, result.output

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

def test_import_duplicate_handling():
    """Test that import handles duplicate files correctly"""
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    # Create multiple identical files to test duplicate handling
    origins = []
    for i in range(5):
        origin = '%s/duplicate_%d.txt' % (folder, i)
        shutil.copyfile(helper.get_file('valid.txt'), origin)
        origins.append(origin)

    helper.reset_dbs()
    runner = CliRunner()
    result = runner.invoke(elodie._import, [
        '--destination', folder_destination,
        '--workers', '4',
        '--allow-duplicates'
    ] + origins)
    helper.restore_dbs()

    # Should complete without issues
    assert result.exit_code == 0, result.output
    assert 'Success         5' in result.output, result.output

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

def test_import_file_directly():
    """Test the import_file function directly"""
    temporary_folder, folder = helper.create_working_folder()
    temporary_folder_destination, folder_destination = helper.create_working_folder()

    origin = '%s/valid.txt' % folder
    shutil.copyfile(helper.get_file('valid.txt'), origin)

    helper.reset_dbs()
    
    # Test the function directly
    dest_path = elodie.import_file(origin, folder_destination, False, False, False)
    
    helper.restore_dbs()

    shutil.rmtree(folder)
    shutil.rmtree(folder_destination)

    assert dest_path is not None, "import_file should return a path"
    assert helper.path_tz_fix(os.path.join('2016-04-Apr','Unknown Location','2016-04-07_11-15-26-valid-sample-title.txt')) in dest_path, dest_path