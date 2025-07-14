"""Session logging functionality for Elodie."""

import os
import json
import datetime
from elodie import constants


class SessionLogger:
    """Handles session logging for Elodie operations."""
    
    def __init__(self):
        self.log_dir = os.path.join(constants.application_directory, 'logs')
        self.session_id = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = os.path.join(self.log_dir, f'session_{self.session_id}.json')
        self.session_data = {
            'session_id': self.session_id,
            'start_time': datetime.datetime.now().isoformat(),
            'command': None,
            'files_processed': [],
            'errors': [],
            'summary': {
                'total_files': 0,
                'successful': 0,
                'failed': 0,
                'skipped': 0
            }
        }
        self._ensure_log_directory()
    
    def _ensure_log_directory(self):
        """Ensure the log directory exists."""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
    
    def set_command(self, command, args):
        """Set the command and arguments for this session."""
        self.session_data['command'] = command
        self.session_data['args'] = args
    
    def log_file_processed(self, source_file, destination_file, status, error_msg=None):
        """Log a processed file."""
        entry = {
            'source': source_file,
            'destination': destination_file,
            'status': status,  # 'success', 'failed', 'skipped'
            'timestamp': datetime.datetime.now().isoformat(),
            'error_msg': error_msg
        }
        self.session_data['files_processed'].append(entry)
        
        # Update summary
        self.session_data['summary']['total_files'] += 1
        if status == 'success':
            self.session_data['summary']['successful'] += 1
        elif status == 'failed':
            self.session_data['summary']['failed'] += 1
        elif status == 'skipped':
            self.session_data['summary']['skipped'] += 1
    
    def log_error(self, error_msg, context=None):
        """Log a general error."""
        error_entry = {
            'message': error_msg,
            'context': context,
            'timestamp': datetime.datetime.now().isoformat()
        }
        self.session_data['errors'].append(error_entry)
    
    def finalize_session(self):
        """Finalize the session and write to log file."""
        self.session_data['end_time'] = datetime.datetime.now().isoformat()
        
        # Calculate duration
        start_time = datetime.datetime.fromisoformat(self.session_data['start_time'])
        end_time = datetime.datetime.fromisoformat(self.session_data['end_time'])
        duration = (end_time - start_time).total_seconds()
        self.session_data['duration_seconds'] = duration
        
        # Write to log file
        with open(self.log_file, 'w') as f:
            json.dump(self.session_data, f, indent=2)
        
        return self.log_file
    
    def get_summary(self):
        """Get a summary of the session."""
        return self.session_data['summary']
    
    def print_summary(self):
        """Print a summary of the session."""
        summary = self.session_data['summary']
        print(f"\n=== Session Summary ===")
        print(f"Total files processed: {summary['total_files']}")
        print(f"Successful: {summary['successful']}")
        print(f"Failed: {summary['failed']}")
        print(f"Skipped: {summary['skipped']}")
        if self.session_data['errors']:
            print(f"Errors encountered: {len(self.session_data['errors'])}")