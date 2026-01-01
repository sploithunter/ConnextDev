#!/usr/bin/env python3
"""Convert JSON Schema to DDS DynamicData types.

Takes a JSON Schema and generates equivalent rti.connextdds DynamicData types.
Handles nested objects by flattening with underscores.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Tuple, List

import rti.connextdds as dds


def json_type_to_dds(json_type: str, field_def: dict) -> dds.DynamicType:
    """Convert JSON Schema type to DDS type."""
    if json_type == "integer":
        return dds.Int64Type()
    elif json_type == "number":
        return dds.Float64Type()
    elif json_type == "boolean":
        return dds.BoolType()
    elif json_type == "string":
        max_len = field_def.get("maxLength", 256)
        return dds.StringType(max_len)
    else:
        raise ValueError(f"Unknown JSON type: {json_type}")


def flatten_schema(schema: dict, prefix: str = "") -> List[Tuple[str, dict]]:
    """Flatten nested JSON Schema into flat list of (field_name, field_def)."""
    fields = []
    
    if schema.get("type") != "object" or "properties" not in schema:
        return fields
    
    for name, prop in schema["properties"].items():
        full_name = f"{prefix}{name}" if prefix else name
        
        if prop.get("type") == "object" and "properties" in prop:
            # Recurse into nested object
            fields.extend(flatten_schema(prop, f"{full_name}_"))
        else:
            # Leaf field
            fields.append((full_name, prop))
    
    return fields


def create_dds_type_from_schema(schema: dict, type_name: str = None) -> dds.StructType:
    """Create a DDS StructType from JSON Schema."""
    if type_name is None:
        type_name = schema.get("title", "GeneratedType")
    
    dds_type = dds.StructType(type_name)
    
    # Flatten the schema
    fields = flatten_schema(schema)
    
    print(f"Creating DDS type '{type_name}' with {len(fields)} fields", file=sys.stderr)
    
    for field_name, field_def in fields:
        json_type = field_def.get("type", "string")
        
        try:
            dds_member_type = json_type_to_dds(json_type, field_def)
            dds_type.add_member(dds.Member(field_name, dds_member_type))
        except Exception as e:
            print(f"Warning: Skipping field {field_name}: {e}", file=sys.stderr)
    
    return dds_type


def load_schema(path: str) -> dict:
    """Load JSON Schema from file."""
    with open(path) as f:
        return json.load(f)


if __name__ == "__main__":
    # Test the converter
    schema_path = Path(__file__).parent.parent / "input" / "uav_telemetry_schema.json"
    
    if not schema_path.exists():
        print(f"Schema not found at {schema_path}", file=sys.stderr)
        sys.exit(1)
    
    schema = load_schema(schema_path)
    dds_type = create_dds_type_from_schema(schema)
    
    print(f"\nSuccessfully created DDS type with {len(flatten_schema(schema))} members")
    
    # Show first 20 member names
    print("\nFirst 20 fields:")
    for i, (name, _) in enumerate(flatten_schema(schema)[:20]):
        print(f"  {i+1}. {name}")

