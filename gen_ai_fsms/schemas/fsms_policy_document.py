from datetime import datetime
from typing import Annotated, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


NonEmptyText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
    ),
]

FSMSPolicyDocumentStatus = Literal[
    "draft",
    "approved",
]

FSMSTextRole = Literal[
    "introduction",
    "business_context",
    "food_safety_importance",
    "policy",
    "responsibilities",
    "procedure",
    "monitoring",
    "corrective_action",
    "review",
]

FSMSListRole = Literal[
    "business_context",
    "food_safety_importance",
    "policy",
    "responsibilities",
    "procedure",
    "monitoring",
    "corrective_action",
    "review",
]

FSMSTableRole = Literal[
    "equipment",
    "monitoring",
    "checklist",
    "responsibilities",
]


class FSMSPolicyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FSMSContentSource(FSMSPolicyModel):
    safety_point_ids: list[NonEmptyText] = Field(
        default_factory=list
    )
    condition_ids: list[NonEmptyText] = Field(
        default_factory=list
    )
    additional_question_keys: list[NonEmptyText] = Field(
        default_factory=list
    )
    source_references: list[NonEmptyText] = Field(
        default_factory=list
    )


class FSMSTextBlock(FSMSPolicyModel):
    block_type: Literal["text"] = "text"
    role: FSMSTextRole
    heading: Optional[NonEmptyText] = None
    text: NonEmptyText
    source: FSMSContentSource = Field(
        default_factory=FSMSContentSource
    )


class FSMSListBlock(FSMSPolicyModel):
    block_type: Literal["list"] = "list"
    role: FSMSListRole
    heading: Optional[NonEmptyText] = None
    ordered: bool = False
    items: list[NonEmptyText] = Field(min_length=1)
    source: FSMSContentSource = Field(
        default_factory=FSMSContentSource
    )


class FSMSTableBlock(FSMSPolicyModel):
    block_type: Literal["table"] = "table"
    role: FSMSTableRole
    heading: Optional[NonEmptyText] = None
    headers: list[NonEmptyText] = Field(min_length=1)
    rows: list[list[str]] = Field(default_factory=list)
    source: FSMSContentSource = Field(
        default_factory=FSMSContentSource
    )

    @model_validator(mode="after")
    def validate_row_widths(self):
        expected_width = len(self.headers)

        for row in self.rows:
            if len(row) != expected_width:
                raise ValueError(
                    "Every FSMS table row must contain the "
                    "same number of values as the headers."
                )

        return self


FSMSPolicyContentBlock = Annotated[
    Union[
        FSMSTextBlock,
        FSMSListBlock,
        FSMSTableBlock,
    ],
    Field(discriminator="block_type"),
]


class FSMSPolicySubsection(FSMSPolicyModel):
    subsection_number: NonEmptyText
    title: NonEmptyText
    content_blocks: list[FSMSPolicyContentBlock] = Field(
        default_factory=list
    )


class FSMSPolicySection(FSMSPolicyModel):
    section_number: NonEmptyText
    title: NonEmptyText
    content_blocks: list[FSMSPolicyContentBlock] = Field(
        default_factory=list
    )
    subsections: list[FSMSPolicySubsection] = Field(
        default_factory=list
    )


class FSMSPolicyDocument(FSMSPolicyModel):
    document_title: NonEmptyText
    document_status: FSMSPolicyDocumentStatus
    draft_notice: Optional[NonEmptyText] = None
    business_name: NonEmptyText
    site_name: NonEmptyText
    business_type: Optional[NonEmptyText] = None
    generated_at: datetime
    sections: list[FSMSPolicySection] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_draft_notice(self):
        if (
            self.document_status == "draft"
            and self.draft_notice is None
        ):
            raise ValueError(
                "A draft FSMS policy document must contain "
                "a draft notice."
            )

        if (
            self.document_status == "approved"
            and self.draft_notice is not None
        ):
            raise ValueError(
                "An approved FSMS policy document must not "
                "contain a draft notice."
            )

        return self
