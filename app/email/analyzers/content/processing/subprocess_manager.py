"""NLP analyzer that uses subprocesses to isolate memory usage for SpaCy.

This module provides subprocess management for running NLP analysis in isolated
processes. It handles process creation, I/O management, error handling, and
result parsing.

The module implements several strategies for handling subprocess execution:
- Large input handling using temporary files
- Robust output parsing with JSON validation
- Comprehensive error handling and logging
- Process cleanup and resource management

Typical usage:
    analyzer = SubprocessNLPAnalyzer()
    results = await analyzer.analyze_batch(texts)
"""

import asyncio
import logging
import json
import os
import time
import tempfile
from typing import List, Dict, Any, Tuple

class SubprocessNLPAnalyzer:
    """Analyze text using separate processes for memory isolation.
    
    This class manages the lifecycle of NLP worker processes, handling process
    creation, communication, and cleanup. It provides memory isolation for
    SpaCy operations by running them in separate processes.

    Attributes:
        logger: Logger instance for this class
        script_path: Path to the NLP worker script
    """
    
    def __init__(self):
        """Initialize the analyzer with worker script path."""
        self.logger = logging.getLogger(__name__)
        self.script_path = os.path.join(os.path.dirname(__file__), 'nlp_worker.py')
        self.logger.debug(f"NLP subprocess script: {self.script_path}")

    async def analyze_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Analyze a batch of texts in a separate process.
        
        Args:
            texts: List of strings to analyze.
            
        Returns:
            List of dictionaries containing analysis results for each text.
            If processing fails, returns error dictionaries for each text.
        """
        if not texts:
            return []
            
        start_time = time.time()
        self.logger.debug(f"Starting NLP analysis of {len(texts)} texts in subprocess")
        
        try:
            # Prepare and run subprocess
            input_data = json.dumps(texts)
            results = await self._run_subprocess(input_data, len(texts))
            
            # Log processing time
            processing_time = time.time() - start_time
            self.logger.debug(
                f"Subprocess NLP analysis completed in {processing_time:.2f}s "
                f"(avg {processing_time/len(texts):.3f}s/text)"
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in subprocess NLP analysis: {e}")
            return [{"error": str(e)} for _ in texts]

    async def _run_subprocess(self, input_data: str, num_texts: int) -> List[Dict[str, Any]]:
        """Run the NLP worker subprocess with the given input.
        
        Args:
            input_data: JSON string containing texts to process
            num_texts: Number of texts being processed (for error handling)
            
        Returns:
            List of result dictionaries from the subprocess
            
        Raises:
            RuntimeError: If subprocess execution fails
        """
        if len(input_data) > 10000:
            return await self._run_with_file(input_data, num_texts)
        else:
            return await self._run_with_args(input_data, num_texts)

    async def _run_with_file(self, input_data: str, num_texts: int) -> List[Dict[str, Any]]:
        """Run subprocess using a temporary file for large inputs.
        
        Args:
            input_data: JSON string containing texts to process
            num_texts: Number of texts being processed
            
        Returns:
            List of result dictionaries
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp:
            temp.write(input_data)
            temp_path = temp.name
        
        try:
            cmd = ["python", self.script_path, "--file", temp_path]
            results = await self._execute_subprocess(cmd, num_texts)
            return results
        finally:
            os.unlink(temp_path)

    async def _run_with_args(self, input_data: str, num_texts: int) -> List[Dict[str, Any]]:
        """Run subprocess passing input as command line argument.
        
        Args:
            input_data: JSON string containing texts to process
            num_texts: Number of texts being processed
            
        Returns:
            List of result dictionaries
        """
        cmd = ["python", self.script_path, input_data]
        return await self._execute_subprocess(cmd, num_texts)

    async def _execute_subprocess(self, cmd: List[str], num_texts: int) -> List[Dict[str, Any]]:
        """Execute the subprocess and handle its output.
        
        Args:
            cmd: Command list to execute
            num_texts: Number of texts being processed
            
        Returns:
            List of result dictionaries
            
        Raises:
            RuntimeError: If subprocess execution fails
        """
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        # Handle subprocess errors
        if proc.returncode != 0:
            self.logger.error(f"Subprocess failed with code {proc.returncode}: {stderr.decode()}")
            raise RuntimeError(f"NLP subprocess failed: {stderr.decode()}")
        
        # Log stderr messages
        self._log_stderr_output(stderr)
        
        # Parse and validate results
        results = self._parse_subprocess_output(stdout.decode().strip(), num_texts)
        return self._validate_results(results, num_texts)

    def _log_stderr_output(self, stderr: bytes) -> None:
        """Log non-error stderr output from subprocess.
        
        Args:
            stderr: Bytes containing stderr output
        """
        stderr_text = stderr.decode()
        if stderr_text:
            for line in stderr_text.split('\n'):
                if line.strip():
                    self.logger.debug(f"Subprocess log: {line}")

    def _parse_subprocess_output(self, stdout_text: str, num_texts: int) -> List[Dict[str, Any]]:
        """Parse and validate JSON output from subprocess.
        
        Args:
            stdout_text: String containing subprocess output
            num_texts: Number of texts being processed
            
        Returns:
            List of parsed result dictionaries
            
        Raises:
            json.JSONDecodeError: If output cannot be parsed as JSON
        """
        # Find the last line that contains valid JSON
        json_line = None
        for line in stdout_text.split('\n'):
            line = line.strip()
            if line and line[0] == '[' and line[-1] == ']':
                json_line = line
        
        if not json_line:
            json_line = stdout_text
            
        results = json.loads(json_line)
        
        # Validate results structure
        if not isinstance(results, list):
            self.logger.error(f"Subprocess returned non-list result: {type(results)}")
            return [{"error": "Invalid result format from subprocess"}] * num_texts
            
        return results

    def _validate_results(self, results: List[Dict[str, Any]], num_texts: int) -> List[Dict[str, Any]]:
        """Ensure results list matches the number of input texts.
        
        Args:
            results: List of result dictionaries
            num_texts: Expected number of results
            
        Returns:
            List of results padded or truncated to match num_texts
        """
        if len(results) != num_texts:
            self.logger.warning(
                f"Subprocess returned {len(results)} results for {num_texts} texts. "
                f"Adjusting results list."
            )
            # Extend if we have fewer results than texts
            if len(results) < num_texts:
                results.extend([{"error": "No result received from subprocess"} 
                               for _ in range(num_texts - len(results))])
            # Truncate if we somehow got more results than texts
            else:
                results = results[:num_texts]
                
        return results

    def __del__(self):
        """Clean up any resources when the analyzer is destroyed."""
        pass 