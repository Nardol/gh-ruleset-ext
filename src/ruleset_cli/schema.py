"""Schema fragments derived from GitHub's REST OpenAPI description.

The schema below focuses on the Repository Ruleset create/update payload,
covering the fields leveraged by the extension. It is intentionally limited
so that validation remains lightweight while still aligned with the official
specification (see https://github.com/github/rest-api-description).
"""

RULESET_SCHEMA = {
    "type": "object",
    "required": ["name", "enforcement"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "target": {"type": "string", "enum": ["branch", "tag", "push"]},
        "enforcement": {"type": "string", "enum": ["disabled", "evaluate", "active"]},
        "bypass_actors": {
            "type": "array",
            "items": {"$ref": "#/$defs/bypass_actor"},
        },
        "conditions": {"$ref": "#/$defs/conditions"},
        "rules": {
            "type": "array",
            "items": {"$ref": "#/$defs/rule"},
        },
    },
    "$defs": {
        "bypass_actor": {
            "type": "object",
            "required": ["actor_type", "bypass_mode"],
            "properties": {
                "actor_type": {
                    "type": "string",
                    "enum": [
                        "RepositoryRole",
                        "Team",
                        "Integration",
                        "OrganizationAdmin",
                        "EnterpriseAdmin",
                    ],
                },
                "bypass_mode": {"type": "string", "enum": ["always", "pull_request"]},
                "repository_role_name": {"type": "string", "minLength": 1},
                "actor_id": {"type": "integer"},
            },
        },
        "conditions": {
            "type": "object",
            "properties": {
                "ref_name": {
                    "type": "object",
                    "properties": {
                        "include": {"$ref": "#/$defs/string_array"},
                        "exclude": {"$ref": "#/$defs/string_array"},
                    },
                }
            },
        },
        "rule": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"type": "string", "minLength": 1},
                "parameters": {"type": "object"},
            },
            "allOf": [
                {
                    "if": {
                        "properties": {"type": {"const": "required_status_checks"}},
                    },
                    "then": {
                        "required": ["parameters"],
                        "properties": {
                            "parameters": {"$ref": "#/$defs/required_status_checks"},
                        },
                    },
                }
            ],
        },
        "required_status_checks": {
            "type": "object",
            "required": ["required_status_checks", "strict_required_status_checks_policy"],
            "properties": {
                "required_status_checks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["context"],
                        "properties": {
                            "context": {"type": "string", "minLength": 1},
                            "integration_id": {"type": "integer"},
                        },
                    },
                },
                "strict_required_status_checks_policy": {"type": "boolean"},
                "do_not_enforce_on_create": {"type": "boolean"},
            },
        },
        "string_array": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}

__all__ = ["RULESET_SCHEMA"]
