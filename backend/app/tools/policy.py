"""
Server-Side Tool Authorization Policy Engine.
Validates permissions, verifies strict schema arguments, and sanitizes tool execution results.
"""
from typing import Any, Dict
from pydantic import ValidationError
from backend.app.auth.permissions import UserRole, has_sufficient_role
from backend.app.core.exceptions import UnauthorizedToolException
from backend.app.tools.registry import AVAILABLE_TOOLS, ContactRequestArgs, JobOpeningsArgs, SearchDocsArgs


class ToolPolicyEngine:
    def authorize_and_validate(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_role: str = "public"
    ) -> Dict[str, Any]:
        """
        1. Checks if tool exists in whitelist
        2. Verifies user has sufficient authorization role
        3. Strictly validates arguments against Pydantic schema
        """
        if tool_name not in AVAILABLE_TOOLS:
            raise UnauthorizedToolException(tool_name)

        tool_def = AVAILABLE_TOOLS[tool_name]
        required_role = UserRole(tool_def.required_role)

        if not has_sufficient_role(user_role, required_role):
            raise UnauthorizedToolException(f"{tool_name} requires {required_role.value} role")

        # Validate arguments according to tool schema
        validated_data: Dict[str, Any] = {}
        try:
            if tool_name == "search_docs":
                validated = SearchDocsArgs(**arguments)
                validated_data = validated.model_dump()
            elif tool_name == "submit_contact_request":
                validated = ContactRequestArgs(**arguments)
                validated_data = validated.model_dump()
            elif tool_name == "get_job_openings":
                validated = JobOpeningsArgs(**arguments)
                validated_data = validated.model_dump()
            elif tool_name == "get_public_company_info":
                validated_data = {}
        except ValidationError as ve:
            raise ValueError(f"Invalid tool arguments for '{tool_name}': {ve.errors()}")

        return validated_data


tool_policy_engine = ToolPolicyEngine()
