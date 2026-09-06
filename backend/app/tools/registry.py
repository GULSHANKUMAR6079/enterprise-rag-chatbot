"""
Tool Schema Registry.
Defines explicit, validated Pydantic schemas for permitted tools.
"""
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field, EmailStr


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    required_role: str = "public"


# Pydantic Schemas for Tool Arguments
class SearchDocsArgs(BaseModel):
    query: str = Field(min_length=2, max_length=200, description="Search terms for knowledge base")
    category: Optional[str] = Field(default=None, max_length=50)


class ContactRequestArgs(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: str = Field(max_length=100)
    inquiry_type: str = Field(default="sales", max_length=50)
    message: str = Field(min_length=5, max_length=1000)


class JobOpeningsArgs(BaseModel):
    department: Optional[str] = Field(default=None, max_length=50)
    location: Optional[str] = Field(default=None, max_length=50)


# Standard Tool Schemas exposed to orchestrator
AVAILABLE_TOOLS: Dict[str, ToolDefinition] = {
    "search_docs": ToolDefinition(
        name="search_docs",
        description="Searches verified public documentation and FAQs.",
        parameters_schema=SearchDocsArgs.model_json_schema(),
        required_role="public"
    ),
    "get_public_company_info": ToolDefinition(
        name="get_public_company_info",
        description="Retrieves approved public company profile and headquarters details.",
        parameters_schema={"type": "object", "properties": {}},
        required_role="public"
    ),
    "submit_contact_request": ToolDefinition(
        name="submit_contact_request",
        description="Submits a verified visitor contact or sales inquiry.",
        parameters_schema=ContactRequestArgs.model_json_schema(),
        required_role="public"
    ),
    "get_job_openings": ToolDefinition(
        name="get_job_openings",
        description="Lists current open career positions across engineering and operations.",
        parameters_schema=JobOpeningsArgs.model_json_schema(),
        required_role="public"
    ),
}
