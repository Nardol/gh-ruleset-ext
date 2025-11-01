from __future__ import annotations

from typing import Any, Dict, List

from .schema import RULESET_SCHEMA


def validate_ruleset_payload(payload: Dict[str, Any]) -> List[str]:
    """Return a list of validation errors for the ruleset payload."""

    errors: List[str] = []
    _validate_schema(RULESET_SCHEMA, payload, path="payload", errors=errors)

    # Additional semantic checks that are easier to express outside the schema.
    bypasses = payload.get("bypass_actors")
    if isinstance(bypasses, list):
        for idx, actor in enumerate(bypasses):
            if not isinstance(actor, dict):
                continue
            actor_type = actor.get("actor_type")
            location = f"payload.bypass_actors[{idx}]"
            if actor_type == "RepositoryRole" and not actor.get("repository_role_name"):
                errors.append(f"{location}.repository_role_name est requis pour RepositoryRole.")
            if actor_type in {"Team", "Integration"} and not isinstance(actor.get("actor_id"), int):
                errors.append(f"{location}.actor_id doit être un entier pour {actor_type}.")

    rules = payload.get("rules")
    if isinstance(rules, list):
        for idx, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue
            if rule.get("type") == "required_status_checks":
                params = rule.get("parameters", {})
                checks = params.get("required_status_checks")
                if isinstance(checks, list) and not checks:
                    errors.append(
                        f"payload.rules[{idx}].parameters.required_status_checks doit contenir au moins un check."
                    )

    return errors


def _validate_schema(schema: Dict[str, Any], data: Any, *, path: str, errors: List[str]) -> None:
    schema_type = schema.get("type")
    if schema_type:
        if not _type_matches(schema_type, data):
            errors.append(f"{path}: type attendu '{schema_type}', obtenu '{type(data).__name__}'.")
            return

    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: valeur '{data}' hors de l'énumération {schema['enum']}.")
        return

    if schema_type == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in data:
                    errors.append(f"{path}.{key} est requis.")
        for key, value in data.items():
            if key in properties:
                _validate_schema(properties[key], value, path=f"{path}.{key}", errors=errors)
            # Unknown properties are ignored to keep validation permissive.
        for key, subschema in properties.items():
            if key in data:
                continue
            if subschema.get("default") is not None:
                continue

    if schema_type == "array":
        item_schema = schema.get("items")
        if item_schema:
            for idx, item in enumerate(data):
                _validate_schema(item_schema, item, path=f"{path}[{idx}]", errors=errors)

    min_length = schema.get("minLength")
    if isinstance(min_length, int) and isinstance(data, str) and len(data) < min_length:
        errors.append(f"{path}: longueur minimale {min_length} non atteinte.")

    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for subschema in all_of:
            _validate_schema(subschema, data, path=path, errors=errors)

    # Handle conditional subschemas (if/then).
    if "if" in schema and "then" in schema:
        if _matches(schema["if"], data):
            _validate_schema(schema["then"], data, path=path, errors=errors)

    if "$ref" in schema:
        ref_schema = _resolve_ref(schema["$ref"])
        if ref_schema:
            _validate_schema(ref_schema, data, path=path, errors=errors)


def _matches(schema: Dict[str, Any], data: Any) -> bool:
    """Minimal matcher for the subset of JSON schema features we need."""
    expected_props = schema.get("properties")
    if expected_props and isinstance(data, dict):
        for key, prop_schema in expected_props.items():
            if key not in data:
                return False
            if "const" in prop_schema and data[key] != prop_schema["const"]:
                return False
    return True


def _resolve_ref(ref: str) -> Dict[str, Any] | None:
    if not ref.startswith("#/$defs/"):
        return None
    key = ref.split("/", 2)[-1]
    return RULESET_SCHEMA.get("$defs", {}).get(key)


def _type_matches(schema_type: str, data: Any) -> bool:
    if schema_type == "object":
        return isinstance(data, dict)
    if schema_type == "array":
        return isinstance(data, list)
    if schema_type == "string":
        return isinstance(data, str)
    if schema_type == "integer":
        return isinstance(data, int) and not isinstance(data, bool)
    if schema_type == "boolean":
        return isinstance(data, bool)
    return True


__all__ = ["validate_ruleset_payload"]
