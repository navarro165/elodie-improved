#!/usr/bin/env python

from __future__ import print_function
import os
import re
import sys
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import click
from send2trash import send2trash

# Verify that external dependencies are present first, so the user gets a
# more user-friendly error instead of an ImportError traceback.
from elodie.dependencies import verify_dependencies
if not verify_dependencies():
    sys.exit(1)

from elodie import constants
from elodie import geolocation_offline as geolocation
from elodie import log
from elodie.compatability import _decode
from elodie.config import load_config
from elodie.filesystem import FileSystem
from elodie.localstorage import Db
from elodie.media.base import Base, get_all_subclasses
from elodie.media.media import Media
from elodie.media.text import Text
from elodie.media.audio import Audio
from elodie.media.photo import Photo
from elodie.media.video import Video
from elodie.plugins.plugins import Plugins
from elodie.result import Result
# ExifTool removed - using pure Python ExifRead library instead
from elodie import constants
from elodie.session_log import SessionLogger

FILESYSTEM = FileSystem()

# Thread-safe locks for parallel processing
filesystem_lock = threading.Lock()
logger_lock = threading.Lock()
session_logger = None


def import_file(_file, destination, album_from_folder, trash, allow_duplicates, subclasses):
    
    _file = _decode(_file)
    destination = _decode(destination)

    """Set file metadata and move it to destination.
    """
    global session_logger
    
    if not os.path.exists(_file):
        log.warn('Could not find %s' % _file)
        log.all('{"source":"%s", "error_msg":"Could not find %s"}' %
                  (_file, _file))
        if session_logger:
            with logger_lock:
                session_logger.log_file_processed(_file, None, 'failed', 'Could not find file')
        return
    # Check if the source, _file, is a child folder within destination
    elif destination.startswith(os.path.abspath(os.path.dirname(_file))+os.sep):
        log.all('{"source": "%s", "destination": "%s", "error_msg": "Source cannot be in destination"}' % (
            _file, destination))
        if session_logger:
            with logger_lock:
                session_logger.log_file_processed(_file, None, 'failed', 'Source cannot be in destination')
        return


    media = Media.get_class_by_file(_file, subclasses)
    if not media:
        log.warn('Not a supported file (%s)' % _file)
        log.all('{"source":"%s", "error_msg":"Not a supported file"}' % _file)
        if session_logger:
            with logger_lock:
                session_logger.log_file_processed(_file, None, 'failed', 'Not a supported file')
        return

    if album_from_folder:
        media.set_album_from_folder()

    # Use thread-safe filesystem operations
    with filesystem_lock:
        dest_path = FILESYSTEM.process_file(_file, destination,
            media, allowDuplicate=allow_duplicates, move=False)
    
    if dest_path:
        log.all('%s -> %s' % (_file, dest_path))
        if session_logger:
            with logger_lock:
                session_logger.log_file_processed(_file, dest_path, 'success')
    else:
        # More descriptive error message for duplicate files
        if allow_duplicates:
            error_msg = 'Processing failed'
            status = 'failed'
        else:
            error_msg = 'File already exists (duplicate not allowed)'
            status = 'skipped'
        
        log.warn('Skipping %s: %s' % (_file, error_msg))
        if session_logger:
            with logger_lock:
                session_logger.log_file_processed(_file, None, status, error_msg)
    
    if trash:
        send2trash(_file)

    return dest_path or None


def import_file_parallel(args):
    """Wrapper for import_file to work with parallel processing."""
    _file, destination, album_from_folder, trash, allow_duplicates, subclasses = args
    return import_file(_file, destination, album_from_folder, trash, allow_duplicates, subclasses)

@click.command('batch')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
def _batch(debug):
    """Run batch() for all plugins.
    """
    constants.debug = debug
    plugins = Plugins()
    plugins.run_batch()
       

@click.command('import')
@click.option('--destination', type=click.Path(file_okay=False),
              required=True, help='Copy imported files into this directory.')
@click.option('--source', type=click.Path(file_okay=False),
              help='Import files from this directory, if specified.')
@click.option('--file', type=click.Path(dir_okay=False),
              help='Import this file, if specified.')
@click.option('--album-from-folder', default=False, is_flag=True,
              help="Use images' folders as their album names.")
@click.option('--trash', default=False, is_flag=True,
              help='After copying files, move the old files to the trash.')
@click.option('--allow-duplicates', default=False, is_flag=True,
              help='Import the file even if it\'s already been imported.')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
@click.option('--exclude-regex', default=set(), multiple=True,
              help='Regular expression for directories or files to exclude.')
@click.option('--workers', default=None, type=int,
              help='Number of parallel workers (default: CPU count)')
@click.argument('paths', nargs=-1, type=click.Path())
def _import(destination, source, file, album_from_folder, trash, allow_duplicates, debug, exclude_regex, workers, paths):
    """Import files or directories by reading their EXIF and organizing them accordingly.
    """
    constants.debug = debug
    has_errors = False
    result = Result()

    destination = _decode(destination)
    destination = os.path.abspath(os.path.expanduser(destination))

    # Pre-load all media classes to avoid thread safety issues
    subclasses = get_all_subclasses(Base)
    
    files = set()
    paths = set(paths)
    if source:
        source = _decode(source)
        paths.add(source)
    if file:
        paths.add(file)

    # if no exclude list was passed in we check if there's a config
    if len(exclude_regex) == 0:
        config = load_config()
        if 'Exclusions' in config:
            exclude_regex = [value for key, value in config.items('Exclusions')]

    exclude_regex_list = set(exclude_regex)

    # Read all files first before starting any parallel processing
    for path in paths:
        path = os.path.expanduser(path)
        if os.path.isdir(path):
            files.update(FILESYSTEM.get_all_files(path, None, exclude_regex_list))
        else:
            if not FILESYSTEM.should_exclude(path, exclude_regex_list, True):
                files.add(path)
    
    # Convert to sorted list for consistent processing order
    files = sorted(list(files))

    # Initialize session logger
    global session_logger
    session_logger = SessionLogger()
    session_logger.set_command('import', {
        'destination': destination,
        'source': source,
        'file': file,
        'album_from_folder': album_from_folder,
        'trash': trash,
        'allow_duplicates': allow_duplicates,
        'workers': workers
    })
    
    # Determine number of workers (default to CPU count, max 8)
    if workers is None:
        workers = min(os.cpu_count(), len(files), 8)
    
    print("Processing %d files with %d workers..." % (len(files), workers))
    
    if workers == 1 or len(files) <= 1:
        # Single-threaded processing
        completed_count = 0
        for current_file in files:
            dest_path = import_file(current_file, destination, album_from_folder,
                        trash, allow_duplicates, subclasses)
            
            # Only report as error if dest_path is None AND duplicates are allowed
            # If duplicates are not allowed, None means skipped (not an error)
            if dest_path:
                result.append((current_file, dest_path))
            elif allow_duplicates:
                # This is a real error when duplicates are allowed
                result.append((current_file, None))
                has_errors = True
            else:
                # This is just a skipped file (duplicate not allowed)
                result.append((current_file, 'SKIPPED'))
            
            has_errors = has_errors is True or (not dest_path and allow_duplicates)
            
            completed_count += 1
            if completed_count % 10 == 0 or completed_count == len(files):
                print("Processed %d/%d files" % (completed_count, len(files)))
    else:
        # Multi-threaded processing
        file_args = [(current_file, destination, album_from_folder, trash, allow_duplicates, subclasses) 
                     for current_file in files]
        
        completed_count = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all tasks
            future_to_file = {executor.submit(import_file_parallel, args): args[0] 
                             for args in file_args}
            
            # Process completed tasks
            for future in as_completed(future_to_file):
                current_file = future_to_file[future]
                try:
                    dest_path = future.result()
                    
                    # Only report as error if dest_path is None AND duplicates are allowed
                    # If duplicates are not allowed, None means skipped (not an error)
                    if dest_path:
                        result.append((current_file, dest_path))
                    elif allow_duplicates:
                        # This is a real error when duplicates are allowed
                        result.append((current_file, None))
                        has_errors = True
                    else:
                        # This is just a skipped file (duplicate not allowed)
                        result.append((current_file, 'SKIPPED'))
                    
                    has_errors = has_errors is True or (not dest_path and allow_duplicates)
                    
                    completed_count += 1
                    if completed_count % 10 == 0 or completed_count == len(files):
                        print("Processed %d/%d files" % (completed_count, len(files)))
                        
                except Exception as exc:
                    print("Error processing %s: %s" % (current_file, exc))
                    result.append((current_file, None))
                    has_errors = True
                    if session_logger:
                        with logger_lock:
                            session_logger.log_error(str(exc), current_file)
    
    print("Completed processing %d files" % len(files))
    
    # Finalize session log
    log_file = session_logger.finalize_session()
    session_logger.print_summary()
    print("Session log saved to: %s" % log_file)

    result.write()

    if has_errors:
        sys.exit(1)


@click.command('generate-db')
@click.option('--source', type=click.Path(file_okay=False),
              required=True, help='Source of your photo library.')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
def _generate_db(source, debug):
    """Regenerate the hash.json database which contains all of the sha256 signatures of media files. The hash.json file is located at ~/.elodie/.
    """
    constants.debug = debug
    result = Result()
    source = os.path.abspath(os.path.expanduser(source))

    if not os.path.isdir(source):
        log.error('Source is not a valid directory %s' % source)
        sys.exit(1)
        
    db = Db()
    db.backup_hash_db()
    db.reset_hash_db()

    for current_file in FILESYSTEM.get_all_files(source):
        result.append((current_file, True))
        db.add_hash(db.checksum(current_file), current_file)
        log.progress()
    
    db.update_hash_db()
    log.progress('', True)
    result.write()

@click.command('verify')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
def _verify(debug):
    constants.debug = debug
    result = Result()
    db = Db()
    for checksum, file_path in db.all():
        if not os.path.isfile(file_path):
            result.append((file_path, False))
            log.progress('x')
            continue

        actual_checksum = db.checksum(file_path)
        if checksum == actual_checksum:
            result.append((file_path, True))
            log.progress()
        else:
            result.append((file_path, False))
            log.progress('x')

    log.progress('', True)
    result.write()


def update_location(media, file_path, location_name):
    """Update location exif metadata of media.
    """
    location_coords = geolocation.coordinates_by_name(location_name)

    if location_coords and 'latitude' in location_coords and \
            'longitude' in location_coords:
        location_status = media.set_location(location_coords[
            'latitude'], location_coords['longitude'])
        if not location_status:
            log.error('Failed to update location')
            log.all(('{"source":"%s",' % file_path,
                       '"error_msg":"Failed to update location"}'))
            sys.exit(1)
    return True


def update_time(media, file_path, time_string):
    """Update time exif metadata of media.
    """
    time_format = '%Y-%m-%d %H:%M:%S'
    if re.match(r'^\d{4}-\d{2}-\d{2}$', time_string):
        time_string = '%s 00:00:00' % time_string
    elif re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}\d{2}$', time_string):
        msg = ('Invalid time format. Use YYYY-mm-dd hh:ii:ss or YYYY-mm-dd')
        log.error(msg)
        log.all('{"source":"%s", "error_msg":"%s"}' % (file_path, msg))
        sys.exit(1)

    time = datetime.strptime(time_string, time_format)
    media.set_date_taken(time)
    return True


@click.command('update')
@click.option('--album', help='Update the image album.')
@click.option('--location', help=('Update the image location. Location '
                                  'should be the name of a place, like "Las '
                                  'Vegas, NV".'))
@click.option('--time', help=('Update the image time. Time should be in '
                              'YYYY-mm-dd hh:ii:ss or YYYY-mm-dd format.'))
@click.option('--title', help='Update the image title.')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
@click.argument('paths', nargs=-1,
                required=True)
def _update(album, location, time, title, paths, debug):
    """Update a file's EXIF. Automatically modifies the file's location and file name accordingly.
    """
    constants.debug = debug
    has_errors = False
    result = Result()

    files = set()
    for path in paths:
        path = os.path.expanduser(path)
        if os.path.isdir(path):
            files.update(FILESYSTEM.get_all_files(path, None))
        else:
            files.add(path)

    for current_file in files:
        if not os.path.exists(current_file):
            has_errors = True
            result.append((current_file, False))
            log.warn('Could not find %s' % current_file)
            log.all('{"source":"%s", "error_msg":"Could not find %s"}' %
                      (current_file, current_file))
            continue

        current_file = os.path.expanduser(current_file)

        # The destination folder structure could contain any number of levels
        #  So we calculate that and traverse up the tree.
        # '/path/to/file/photo.jpg' -> '/path/to/file' ->
        #  ['path','to','file'] -> ['path','to'] -> '/path/to'
        current_directory = os.path.dirname(current_file)
        destination_depth = -1 * len(FILESYSTEM.get_folder_path_definition())
        destination = os.sep.join(
                          os.path.normpath(
                              current_directory
                          ).split(os.sep)[:destination_depth]
                      )

        media = Media.get_class_by_file(current_file, get_all_subclasses())
        if not media:
            continue

        updated = False
        if location:
            update_location(media, current_file, location)
            updated = True
        if time:
            update_time(media, current_file, time)
            updated = True
        if album:
            media.set_album(album)
            updated = True

        # Updating a title can be problematic when doing it 2+ times on a file.
        # You would end up with img_001.jpg -> img_001-first-title.jpg ->
        # img_001-first-title-second-title.jpg.
        # To resolve that we have to track the prior title (if there was one.
        # Then we massage the updated_media's metadata['base_name'] to remove
        # the old title.
        # Since FileSystem.get_file_name() relies on base_name it will properly
        #  rename the file by updating the title instead of appending it.
        remove_old_title_from_name = False
        if title:
            # We call get_metadata() to cache it before making any changes
            metadata = media.get_metadata()
            title_update_status = media.set_title(title)
            original_title = metadata['title']
            if title_update_status and original_title:
                # @TODO: We should move this to a shared method since
                # FileSystem.get_file_name() does it too.
                original_title = re.sub(r'\W+', '-', original_title.lower())
                original_base_name = metadata['base_name']
                remove_old_title_from_name = True
            updated = True

        if updated:
            updated_media = Media.get_class_by_file(current_file,
                                                    get_all_subclasses())
            # See comments above on why we have to do this when titles
            # get updated.
            if remove_old_title_from_name and len(original_title) > 0:
                updated_media.get_metadata()
                updated_media.set_metadata_basename(
                    original_base_name.replace('-%s' % original_title, ''))

            dest_path = FILESYSTEM.process_file(current_file, destination,
                updated_media, move=True, allowDuplicate=True)
            log.info(u'%s -> %s' % (current_file, dest_path))
            log.all('{"source":"%s", "destination":"%s"}' % (current_file,
                                                               dest_path))
            # If the folder we moved the file out of or its parent are empty
            # we delete it.
            FILESYSTEM.delete_directory_if_empty(os.path.dirname(current_file))
            FILESYSTEM.delete_directory_if_empty(
                os.path.dirname(os.path.dirname(current_file)))
            result.append((current_file, dest_path))
            # Trip has_errors to False if it's already False or dest_path is.
            has_errors = has_errors is True or not dest_path
        else:
            has_errors = False
            result.append((current_file, False))

    result.write()
    
    if has_errors:
        sys.exit(1)


@click.group()
def main():
    pass


main.add_command(_import)
main.add_command(_update)
main.add_command(_generate_db)
main.add_command(_verify)
main.add_command(_batch)


if __name__ == '__main__':
    # Pure Python implementation - no ExifTool subprocess needed
    main()
