"""NLP analyzer that uses subprocesses to isolate memory usage for SpaCy."""

import asyncio
import logging
import subprocess
import json
import os
import time
import tempfile
from typing import List, Dict, Any

class SubprocessNLPAnalyzer:
    """Analyze text using separate processes for memory isolation."""
    
    def __init__(self):
        """Initialize the analyzer."""
        self.logger = logging.getLogger(__name__)
        self.script_path = os.path.join(os.path.dirname(__file__), 'process_nlp.py')
        self.logger.debug(f"NLP subprocess script: {self.script_path}")
    
    async def analyze_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Analyze a batch of texts in a separate process."""
        if not texts:
            return []
            
        start_time = time.time()
        self.logger.debug(f"Starting NLP analysis of {len(texts)} texts in subprocess")
        
        try:
            # Prepare input data
            input_data = json.dumps(texts)
            
            # If input data is large, use a temporary file instead of command line
            if len(input_data) > 10000:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp:
                    temp.write(input_data)
                    temp_path = temp.name
                
                # Create process with file input
                cmd = ["python", self.script_path, "--file", temp_path]
                
                try:
                    # Use asyncio to run the subprocess
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    stdout, stderr = await proc.communicate()
                    
                    # Clean up temporary file
                    os.unlink(temp_path)
                    
                    if proc.returncode != 0:
                        self.logger.error(f"Subprocess failed with code {proc.returncode}: {stderr.decode()}")
                        raise RuntimeError(f"NLP subprocess failed: {stderr.decode()}")
                    
                    # Process stderr for log messages but don't treat as an error
                    stderr_text = stderr.decode()
                    if stderr_text:
                        for line in stderr_text.split('\n'):
                            if line.strip():
                                self.logger.debug(f"Subprocess log: {line}")
                    
                    # Parse the results
                    stdout_text = stdout.decode().strip()
                    # Find the last line that contains valid JSON (in case there are log messages)
                    json_line = None
                    for line in stdout_text.split('\n'):
                        line = line.strip()
                        if line and line[0] == '[' and line[-1] == ']':
                            json_line = line
                    
                    if not json_line:
                        json_line = stdout_text
                        
                    results = json.loads(json_line)
                    
                    # Make sure results is a list
                    if not isinstance(results, list):
                        self.logger.error(f"Subprocess returned non-list result: {type(results)}")
                        results = [{"error": "Invalid result format from subprocess"}] * len(texts)
                except Exception as e:
                    self.logger.error(f"Error running NLP subprocess: {e}")
                    # Create error response for each text
                    results = [{"error": str(e)} for _ in texts]
            else:
                # Create process with command line input
                cmd = ["python", self.script_path, input_data]
                
                # Use asyncio to run the subprocess
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await proc.communicate()
                
                if proc.returncode != 0:
                    self.logger.error(f"Subprocess failed with code {proc.returncode}: {stderr.decode()}")
                    # Create error response for each text
                    return [{"error": f"NLP subprocess failed: {stderr.decode()}"} for _ in texts]
                
                # Process stderr for log messages but don't treat as an error
                stderr_text = stderr.decode()
                if stderr_text:
                    for line in stderr_text.split('\n'):
                        if line.strip():
                            self.logger.debug(f"Subprocess log: {line}")
                
                # Parse the results
                try:
                    stdout_text = stdout.decode().strip()
                    # Find the last line that contains valid JSON (in case there are log messages)
                    json_line = None
                    for line in stdout_text.split('\n'):
                        line = line.strip()
                        if line and line[0] == '[' and line[-1] == ']':
                            json_line = line
                    
                    if not json_line:
                        json_line = stdout_text
                        
                    results = json.loads(json_line)
                    
                    # Make sure results is a list
                    if not isinstance(results, list):
                        self.logger.error(f"Subprocess returned non-list result: {type(results)}")
                        results = [{"error": "Invalid result format from subprocess"}] * len(texts)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse subprocess output: {e}")
                    self.logger.debug(f"Subprocess output: {stdout_text[:200]}...")
                    # Create error response for each text
                    return [{"error": "Failed to parse subprocess output"} for _ in texts]
            
            # Ensure we have exactly the right number of results
            if len(results) != len(texts):
                self.logger.warning(
                    f"Subprocess returned {len(results)} results for {len(texts)} texts. "
                    f"Filling in missing results with errors."
                )
                # Extend if we have fewer results than texts
                if len(results) < len(texts):
                    results.extend([{"error": "No result received from subprocess"} 
                                   for _ in range(len(texts) - len(results))])
                # Truncate if we somehow got more results than texts
                elif len(results) > len(texts):
                    results = results[:len(texts)]
                    
            processing_time = time.time() - start_time
            self.logger.debug(
                f"Subprocess NLP analysis completed in {processing_time:.2f}s "
                f"(avg {processing_time/len(texts):.3f}s/text)"
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in subprocess NLP analysis: {e}")
            # Always return the same number of results as input texts
            return [{"error": str(e)} for _ in texts]
    
    def __del__(self):
        """Clean up resources."""
        pass 