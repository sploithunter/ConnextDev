"""Parser for RTI DDS Spy (rtiddsspy) printSample output.

RTI DDS Spy outputs human-readable text that needs to be parsed into structured
JSON format. This module handles the parsing of various data types and nested
structures from the rtiddsspy output.

Example rtiddsspy output:
    Sample received, count 1, topic "HelloWorld"
        message: "Hello DDS World"
        count: 42
        timestamp: 1735600000.123

This would parse to:
    {
        "topic": "HelloWorld",
        "count": 1,
        "data": {
            "message": "Hello DDS World",
            "count": 42,
            "timestamp": 1735600000.123
        }
    }
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SpySample:
    """A parsed DDS sample from rtiddsspy output."""

    topic: str
    sample_count: int
    data: dict[str, Any]
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "topic": self.topic,
            "sample_count": self.sample_count,
            "data": self.data,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class ParseState:
    """Internal state for parsing nested structures."""

    indent_stack: list[int] = field(default_factory=list)
    current_dict: dict[str, Any] = field(default_factory=dict)
    dict_stack: list[dict[str, Any]] = field(default_factory=list)
    key_stack: list[str] = field(default_factory=list)


class SpyParser:
    """Parser for rtiddsspy printSample output.

    Converts the human-readable text output from rtiddsspy into structured
    SpySample objects that can be serialized to JSON.
    
    Handles multiple rtiddsspy output formats:
    - Format 1: "Sample received, count N, topic "TopicName""
    - Format 2: "HH:MM:SS New data ... topic="TopicName" type="TypeName""
    """

    # Pattern to match sample header line - original format
    SAMPLE_HEADER_PATTERN = re.compile(
        r"Sample\s+received,\s*count\s+(\d+),\s*topic\s+\"([^\"]+)\""
    )
    
    # Pattern to match rtiddsspy 7.x format: "HH:MM:SS New data ... topic="TopicName""
    NEW_DATA_PATTERN = re.compile(
        r"^\d{2}:\d{2}:\d{2}\s+New data\s+.*topic=\"([^\"]+)\""
    )

    # Pattern to match field lines: "    fieldName: value"
    FIELD_PATTERN = re.compile(r"^(\s*)(\w+):\s*(.*)$")

    # Pattern to match array start: "    fieldName:"
    ARRAY_START_PATTERN = re.compile(r"^(\s*)(\w+):$")

    # Pattern to match array element: "    [0]: value" or "    [0]:"
    ARRAY_ELEMENT_PATTERN = re.compile(r"^(\s*)\[(\d+)\]:\s*(.*)$")

    # Pattern to match struct start (empty value after colon)
    STRUCT_START_PATTERN = re.compile(r"^(\s*)(\w+):\s*$")

    def __init__(self) -> None:
        """Initialize the parser."""
        self._buffer: list[str] = []
        self._samples: list[SpySample] = []

    def parse_output(self, text: str) -> list[SpySample]:
        """Parse rtiddsspy output text into a list of samples.

        Args:
            text: The raw text output from rtiddsspy.

        Returns:
            List of parsed SpySample objects.
        """
        samples: list[SpySample] = []
        lines = text.split("\n")

        current_sample_lines: list[str] = []
        current_topic: str | None = None
        current_count: int = 0
        sample_counter: int = 0

        for line in lines:
            # Try original format first
            header_match = self.SAMPLE_HEADER_PATTERN.search(line)
            if header_match:
                # If we have a previous sample, parse it
                if current_topic is not None and current_sample_lines:
                    sample = self._parse_sample(
                        current_topic, current_count, current_sample_lines
                    )
                    samples.append(sample)

                # Start new sample
                current_count = int(header_match.group(1))
                current_topic = header_match.group(2)
                current_sample_lines = []
                continue
            
            # Try rtiddsspy 7.x "New data" format
            new_data_match = self.NEW_DATA_PATTERN.search(line)
            if new_data_match:
                # If we have a previous sample, parse it
                if current_topic is not None and current_sample_lines:
                    sample = self._parse_sample(
                        current_topic, current_count, current_sample_lines
                    )
                    samples.append(sample)

                # Start new sample
                sample_counter += 1
                current_count = sample_counter
                current_topic = new_data_match.group(1)
                current_sample_lines = []
                continue
            
            # Skip non-data lines (New writer, Deleted writer, etc.)
            if re.match(r"^\d{2}:\d{2}:\d{2}\s+(New writer|Deleted writer|No writers)", line):
                continue
            
            # Skip rtiddsspy header/info lines
            if line.startswith("RTI Connext") or line.startswith("rtiddsspy") or line.startswith("~~"):
                continue
                
            # Accumulate data lines for current sample
            if current_topic is not None:
                current_sample_lines.append(line)

        # Don't forget the last sample
        if current_topic is not None and current_sample_lines:
            sample = self._parse_sample(
                current_topic, current_count, current_sample_lines
            )
            samples.append(sample)

        return samples

    def parse_line(self, line: str) -> SpySample | None:
        """Parse a single line, maintaining internal state for multi-line samples.

        This is useful for streaming parsing where lines come in one at a time.

        Args:
            line: A single line from rtiddsspy output.

        Returns:
            A SpySample if a complete sample was parsed, None otherwise.
        """
        # Check for original format header
        header_match = self.SAMPLE_HEADER_PATTERN.search(line)
        # Check for rtiddsspy 7.x "New data" format
        new_data_match = self.NEW_DATA_PATTERN.search(line)
        
        # Skip non-data lines
        if re.match(r"^\d{2}:\d{2}:\d{2}\s+(New writer|Deleted writer|No writers)", line):
            return None
        if line.startswith("RTI Connext") or line.startswith("rtiddsspy") or line.startswith("~~"):
            return None

        if header_match or new_data_match:
            # If we have buffered lines, parse the previous sample
            result = None
            if self._buffer:
                result = self._parse_buffered_sample()

            # Start new sample
            self._buffer = [line]
            return result

        # Add line to buffer
        if self._buffer:
            self._buffer.append(line)

        return None

    def flush(self) -> SpySample | None:
        """Flush any remaining buffered lines and return the final sample.

        Returns:
            A SpySample if there was buffered data, None otherwise.
        """
        if self._buffer:
            return self._parse_buffered_sample()
        return None

    def _parse_buffered_sample(self) -> SpySample | None:
        """Parse the buffered lines into a sample."""
        if not self._buffer:
            return None

        header_line = self._buffer[0]
        
        # Try original format
        header_match = self.SAMPLE_HEADER_PATTERN.search(header_line)
        if header_match:
            count = int(header_match.group(1))
            topic = header_match.group(2)
            data_lines = self._buffer[1:]
            self._buffer = []
            return self._parse_sample(topic, count, data_lines)
        
        # Try rtiddsspy 7.x format
        new_data_match = self.NEW_DATA_PATTERN.search(header_line)
        if new_data_match:
            # Use incremental count for streaming
            if not hasattr(self, '_stream_count'):
                self._stream_count = 0
            self._stream_count += 1
            
            topic = new_data_match.group(1)
            data_lines = self._buffer[1:]
            self._buffer = []
            return self._parse_sample(topic, self._stream_count, data_lines)

        self._buffer = []
        return None

    def _parse_sample(
        self, topic: str, count: int, lines: list[str]
    ) -> SpySample:
        """Parse sample data lines into a SpySample."""
        raw_text = "\n".join(lines)
        data = self._parse_fields(lines)

        return SpySample(
            topic=topic,
            sample_count=count,
            data=data,
            raw_text=raw_text,
        )

    def _parse_fields(self, lines: list[str]) -> dict[str, Any]:
        """Parse field lines into a dictionary."""
        result: dict[str, Any] = {}
        i = 0

        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue

            # Try to match a field
            field_match = self.FIELD_PATTERN.match(line)
            if field_match:
                indent = len(field_match.group(1))
                field_name = field_match.group(2)
                value_str = field_match.group(3).strip()

                if value_str:
                    # Simple field with value on same line
                    result[field_name] = self._parse_value(value_str)
                    i += 1
                else:
                    # Complex field (struct or array) - collect nested lines
                    nested_lines, i = self._collect_nested_lines(lines, i + 1, indent)
                    result[field_name] = self._parse_nested(nested_lines, indent)
            else:
                i += 1

        return result

    def _collect_nested_lines(
        self, lines: list[str], start_idx: int, parent_indent: int
    ) -> tuple[list[str], int]:
        """Collect all lines that are nested under the parent indent level."""
        nested: list[str] = []
        i = start_idx

        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue

            # Calculate indent of this line
            stripped = line.lstrip()
            current_indent = len(line) - len(stripped)

            # If indent is <= parent, we're done with this nested block
            if current_indent <= parent_indent:
                break

            nested.append(line)
            i += 1

        return nested, i

    def _parse_nested(self, lines: list[str], parent_indent: int) -> Any:
        """Parse nested structure (could be array or struct)."""
        if not lines:
            return {}

        # Check if it's an array (first line starts with [N]:)
        first_line = lines[0].strip()
        if first_line.startswith("["):
            return self._parse_array(lines, parent_indent)
        else:
            return self._parse_fields(lines)

    def _parse_array(self, lines: list[str], parent_indent: int) -> list[Any]:
        """Parse array elements."""
        result: list[Any] = []
        i = 0

        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue

            array_match = self.ARRAY_ELEMENT_PATTERN.match(line)
            if array_match:
                indent = len(array_match.group(1))
                # index = int(array_match.group(2))  # Not used, we just append
                value_str = array_match.group(3).strip()

                if value_str:
                    # Simple array element
                    result.append(self._parse_value(value_str))
                    i += 1
                else:
                    # Complex array element (struct)
                    nested_lines, i = self._collect_nested_lines(lines, i + 1, indent)
                    result.append(self._parse_fields(nested_lines))
            else:
                i += 1

        return result

    def _parse_value(self, value_str: str) -> Any:
        """Parse a value string into the appropriate Python type."""
        value_str = value_str.strip()

        # Handle quoted strings
        if value_str.startswith('"') and value_str.endswith('"'):
            return value_str[1:-1]

        # Handle booleans
        if value_str.lower() == "true":
            return True
        if value_str.lower() == "false":
            return False

        # Handle integers
        try:
            return int(value_str)
        except ValueError:
            pass

        # Handle floats
        try:
            return float(value_str)
        except ValueError:
            pass

        # Handle hex values
        if value_str.startswith("0x"):
            try:
                return int(value_str, 16)
            except ValueError:
                pass

        # Return as string if nothing else matches
        return value_str


def parse_spy_output(text: str) -> list[SpySample]:
    """Convenience function to parse rtiddsspy output.

    Args:
        text: Raw text output from rtiddsspy.

    Returns:
        List of parsed SpySample objects.
    """
    parser = SpyParser()
    return parser.parse_output(text)

