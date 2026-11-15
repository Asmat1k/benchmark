import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

root = Path(__file__).resolve().parents[3]
schemas = {}
for path in sorted((root / "configs/schemas").glob("*.schema.json")):
    schema = json.loads(path.read_text())
    Draft202012Validator.check_schema(schema)
    schemas[path.name.split(".")[0]] = Draft202012Validator(schema, format_checker=FormatChecker())

for path in sorted((root / "configs").glob("*.json")):
    schemas[path.stem].validate(json.loads(path.read_text()))

examples = Path(__file__).parent
for path in sorted(examples.glob("*.valid.json")):
    schemas[path.name.split(".")[0]].validate(json.loads(path.read_text()))

for path in sorted(examples.glob("*.invalid.json")):
    errors = list(schemas[path.name.split(".")[0]].iter_errors(json.loads(path.read_text())))
    if not errors:
        raise ValueError(f"Unexpected valid fixture {path.name}")
    for error in errors:
        print(path.name, error.json_path, error.message)

print(f"Validated {len(schemas)} schemas, configs and synthetic examples")
