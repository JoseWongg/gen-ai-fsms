import re

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from gen_ai_fsms.api.deps import (
    get_current_user,
    get_db,
)
from gen_ai_fsms.api.routes.onboarding_screening import (
    get_current_user_profile,
)
from gen_ai_fsms.db.models import User
from gen_ai_fsms.schemas.fsms_policy_document import (
    FSMSPolicyDocument,
    FSMSPolicyDocumentProgress,
)
from gen_ai_fsms.services.fsms_policy_document_pdf import (
    render_fsms_policy_document_pdf,
)
from gen_ai_fsms.services.fsms_policy_document_progress import (
    generate_fsms_policy_document_progress_for_profile,
)
from gen_ai_fsms.services.fsms_policy_document_service import (
    generate_fsms_policy_document_for_profile,
)


router = APIRouter(
    prefix="/fsms-document",
    tags=["FSMS Document"],
)


@router.get(
    "",
    response_model=FSMSPolicyDocument,
)
def get_current_fsms_document(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the current policy-format FSMS document.

    The document is rebuilt from current stored
    information and is not persisted as a snapshot.
    """
    profile = get_current_user_profile(
        db,
        current_user,
    )

    return generate_fsms_policy_document_for_profile(
        db=db,
        business_profile_id=profile.id,
    )


@router.get(
    "/progress",
    response_model=FSMSPolicyDocumentProgress,
)
def get_current_fsms_document_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return live document completion and product
    coverage for the authenticated business.
    """
    profile = get_current_user_profile(
        db,
        current_user,
    )

    return (
        generate_fsms_policy_document_progress_for_profile(
            db=db,
            business_profile_id=profile.id,
        )
    )


@router.get("/pdf")
def download_current_fsms_document_pdf(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the current policy-format document as PDF.
    """
    profile = get_current_user_profile(
        db,
        current_user,
    )
    document = generate_fsms_policy_document_for_profile(
        db=db,
        business_profile_id=profile.id,
    )
    pdf_bytes = render_fsms_policy_document_pdf(
        document
    )
    filename = _build_pdf_filename(document)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            )
        },
    )


def _build_pdf_filename(
    document: FSMSPolicyDocument,
) -> str:
    base_name = (
        document.site_name
        or document.business_name
    )
    cleaned_name = re.sub(
        r"[^A-Za-z0-9]+",
        "-",
        base_name,
    ).strip("-").lower()

    if not cleaned_name:
        cleaned_name = (
            "food-safety-management-system"
        )

    return f"{cleaned_name}-fsms.pdf"
