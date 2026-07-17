from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


FSMSSectionStatus = Literal[
    "completed",
    "not_completed",
    "beyond_prototype_scope",
]

FSMSDocumentStatus = Literal[
    "not_started",
    "in_progress",
    "completed",
]


class FSMSDocumentProgress(BaseModel):
    completed_applicable_section_count: int = Field(ge=0)
    applicable_supported_section_count: int = Field(ge=0)
    completion_percentage: int = Field(ge=0, le=100)
    supported_section_count: int = Field(ge=0)
    planned_section_count: int = Field(ge=0)
    document_status: FSMSDocumentStatus
    main_value: str
    completion_caption: str
    coverage_caption: str


class FSMSDocumentRule(BaseModel):
    safety_point_id: str
    instruction: str
    source_references: list[str] = Field(default_factory=list)


class FSMSDocumentArrangement(BaseModel):
    arrangement_type: str
    title: str
    statements: list[str] = Field(default_factory=list)
    table_headers: list[str] = Field(default_factory=list)
    table_rows: list[list[str]] = Field(default_factory=list)
    source_safety_point_id: Optional[str] = None
    source_question_key: Optional[str] = None


class FSMSDocumentSubsection(BaseModel):
    safe_method_id: str
    title: str
    introduction: str
    status: FSMSSectionStatus
    approved_rules: list[FSMSDocumentRule] = Field(default_factory=list)
    business_specific_arrangements: list[
        FSMSDocumentArrangement
    ] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)


class FSMSDocumentSection(BaseModel):
    section_id: str
    title: str
    display_order: int = Field(ge=1)
    status: FSMSSectionStatus
    introduction: str
    completion_message: Optional[str] = None
    applicable_safety_point_count: int = Field(default=0, ge=0)
    approved_safety_point_count: int = Field(default=0, ge=0)
    outstanding_safety_point_count: int = Field(default=0, ge=0)
    subsections: list[FSMSDocumentSubsection] = Field(
        default_factory=list
    )


class FSMSDocumentAppendix(BaseModel):
    appendix_id: str
    title: str
    display_order: int = Field(ge=1)
    arrangements: list[FSMSDocumentArrangement] = Field(
        default_factory=list
    )
    source_references: list[str] = Field(default_factory=list)


class FSMSDocument(BaseModel):
    document_title: str
    business_name: str
    site_name: str
    business_type: Optional[str] = None
    business_description: Optional[str] = None
    generated_at: datetime
    progress: FSMSDocumentProgress
    sections: list[FSMSDocumentSection] = Field(default_factory=list)
    appendices: list[FSMSDocumentAppendix] = Field(
        default_factory=list
    )
