"""Subprocess utility functions for the Gmail client.

This module provides utility functions for executing and handling subprocesses,
particularly for Gmail API operations.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, List, Any, Optional, Tuple

from ..core.exceptions import GmailAPIError


async def run_subprocess(command: list, logger: Optional[logging.Logger] = None, env: Dict = None) -> Tuple[bytes, List[bytes], int]:
    """Execute a subprocess command and capture output.
    
    Args:
        command: List of command line arguments
        logger: Logger for output messages
        env: Optional environment variables
            
    Returns:
        tuple: (stdout_data, stderr_lines, return_code)
            
    Raises:
        Exception: If subprocess creation or execution fails
    """
    if env is None:
        env = os.environ.copy()
        # Get the project root directory to add to PYTHONPATH
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Move up to app directory
        project_root = os.path.abspath(os.path.join(current_dir, '../../../../../'))
        
        # Set environment variables for the subprocess
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] = f"{project_root}:{env['PYTHONPATH']}"
        else:
            env['PYTHONPATH'] = project_root
    
    # Execute subprocess asynchronously with asyncio
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env
    )
    
    # Define reader functions for stdout and stderr
    async def read_stdout():
        """Read the stdout data from the subprocess.
        
        Returns:
            bytes: The stdout data read from the subprocess.
        """
        return await process.stdout.read()
    
    async def read_stderr():
        """Read the stderr data from the subprocess and log it.
        
        Returns:
            List[bytes]: A list of lines read from stderr.
        """
        lines = []
        while True:
            line = await process.stderr.readline()
            if not line:  # EOF
                break
            
            lines.append(line)
            if logger:
                decoded_line = line.decode().strip()
                
                # Simple logging based on log level
                if "ERROR" in decoded_line:
                    logger.error(f"Subprocess: {decoded_line}")
                elif "WARNING" in decoded_line:
                    logger.warning(f"Subprocess: {decoded_line}")
                else:
                    logger.debug(f"Subprocess: {decoded_line}")
        
        return lines
    
    # Start reading stdout and stderr concurrently
    stdout_task = asyncio.create_task(read_stdout())
    stderr_task = asyncio.create_task(read_stderr())
    
    # Wait for both tasks and the process to complete
    try:
        # Use asyncio.gather to await both tasks
        stdout_data, stderr_lines = await asyncio.gather(stdout_task, stderr_task)
        
        # Wait for the process to exit
        await process.wait()
        
        # Log completion
        if logger:
            logger.info(f"Subprocess completed with exit code: {process.returncode}")
        
        return stdout_data, stderr_lines, process.returncode
    except asyncio.CancelledError:
        # If we're cancelled, make sure to terminate the subprocess
        process.terminate()
        raise
    except Exception as e:
        if logger:
            logger.error(f"Error during subprocess execution: {e}")
        # Try to terminate the process in case it's still running
        process.terminate()
        raise


def parse_json_response(stdout_data: bytes, logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """Parse JSON response from subprocess output.
    
    Args:
        stdout_data: Raw stdout data from subprocess
        logger: Optional logger for debug messages
            
    Returns:
        dict: Parsed JSON response
            
    Raises:
        GmailAPIError: If JSON parsing fails or no valid JSON is found
    """
    try:
        if stdout_data:
            stdout_str = stdout_data.decode('utf-8', errors='replace')
            
            # Find the JSON object boundaries
            json_start = stdout_str.find('{')
            json_end = stdout_str.rfind('}') + 1
            
            if json_start < 0 or json_end <= json_start:
                raise ValueError("No valid JSON found in output")
                
            json_str = stdout_str[json_start:json_end]
            return json.loads(json_str)
        else:
            raise ValueError("No output from subprocess")
            
    except Exception as e:
        if logger:
            logger.error(f"Error parsing subprocess output: {e}")
        raise GmailAPIError(f"Failed to parse subprocess output: {e}")


def handle_subprocess_result(stdout_data: bytes, stderr_lines: List[bytes], return_code: int, 
                           operation_name: str, logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """Handle subprocess result with standardized error handling.
    
    Args:
        stdout_data: Raw stdout data from subprocess
        stderr_lines: List of stderr lines from subprocess
        return_code: Subprocess return code
        operation_name: Name of the operation (for error messages)
        logger: Optional logger for output
            
    Returns:
        Parsed JSON response from subprocess
            
    Raises:
        GmailAPIError: If subprocess failed or returned invalid response
    """
    # Check if process failed
    if return_code != 0:
        stderr_text = "\n".join([
            line.decode('utf-8', errors='replace') if isinstance(line, bytes) else str(line)
            for line in stderr_lines if line
        ]) or f"Process exited with code {return_code}"
        
        if logger:
            logger.error(f"Subprocess failed: {stderr_text}")
        raise GmailAPIError(f"Failed to {operation_name}: {stderr_text}")
        
    # Parse the JSON output
    result = parse_json_response(stdout_data, logger)
    
    # Check for error in response
    if 'error' in result:
        if logger:
            logger.error(f"API error: {result['error']}")
        raise GmailAPIError(f"Failed to {operation_name}: {result['error']}")
        
    return result


def build_command(worker_script_path: str, credentials_path: str, user_email: str, 
                 action: str = "fetch_emails") -> List[str]:
    """Build the base command for subprocess execution.
    
    Args:
        worker_script_path: Path to the worker script
        credentials_path: Path to the credentials file
        user_email: Email address of the user
        action: Action to perform ('fetch_emails' or 'send_email')
            
    Returns:
        List of command line arguments for subprocess
    """
    # Build base command
    return [
        sys.executable,
        worker_script_path,
        "--credentials", f"@{credentials_path}",
        "--user_email", user_email,
        "--action", action
    ] 