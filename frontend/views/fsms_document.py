import re
from datetime import datetime
from typing import Any

import streamlit as st

from shared import api_request


def load_fsms_document(token):
    response = api_request(
        "GET",
        "/fsms-document",
        token=token,
    )

    if response is None:
        st.error(
            "Unable to load the Food Safety Management "
            "System document because the backend did not "
            "respond."
        )
        return None

    if response.status_code != 200:
        detail = None

        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            pass

        st.error(
            detail
            or (
                "Unable to load the Food Safety Management "
                f"System document (HTTP "
                f"{response.status_code})."
            )
        )
        return None

    return response.json()


def load_fsms_document_pdf(token):
    response = api_request(
        "GET",
        "/fsms-document/pdf",
        token=token,
    )

    if response is None:
        st.warning(
            "The document preview is available, but the PDF "
            "could not be generated because the backend did "
            "not respond."
        )
        return None

    if response.status_code != 200:
        detail = None

        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            pass

        st.warning(
            detail
            or (
                "The document preview is available, but the "
                f"PDF could not be generated "
                f"(HTTP {response.status_code})."
            )
        )
        return None

    return response.content


def build_pdf_filename(document):
    base_name = (
        document.get("site_name")
        or document.get("business_name")
        or "food-safety-management-system"
    )
    cleaned_name = re.sub(
        r"[^A-Za-z0-9]+",
        "-",
        str(base_name),
    ).strip("-").lower()

    if not cleaned_name:
        cleaned_name = "food-safety-management-system"

    return f"{cleaned_name}-fsms.pdf"


def format_generated_at(value):
    if not value:
        return "Not available"

    cleaned_value = str(value).replace(
        "Z",
        "+00:00",
    )

    try:
        parsed_value = datetime.fromisoformat(
            cleaned_value
        )
    except ValueError:
        return str(value)

    formatted_value = parsed_value.strftime(
        "%d %B %Y at %H:%M"
    )
    timezone_label = parsed_value.strftime("%Z")

    if timezone_label:
        return f"{formatted_value} {timezone_label}"

    return formatted_value


def format_document_status(value):
    return str(value or "Unknown").replace(
        "_",
        " ",
    ).title()


def table_records(block):
    headers = block.get("headers") or []
    rows = block.get("rows") or []

    if not headers:
        return []

    records = []

    for row in rows:
        row_values = (
            row
            if isinstance(row, list)
            else []
        )
        records.append(
            {
                header: (
                    row_values[index]
                    if index < len(row_values)
                    else ""
                )
                for index, header in enumerate(
                    headers
                )
            }
        )

    return records


def render_document_details(document):
    st.subheader("Document details")

    business_column, document_column = st.columns(2)

    with business_column:
        st.markdown("**Business**")
        st.write(
            document.get("business_name")
            or "Not recorded"
        )

        st.markdown("**Site**")
        st.write(
            document.get("site_name")
            or "Not recorded"
        )

    with document_column:
        st.markdown("**Business type**")
        st.write(
            document.get("business_type")
            or "Not recorded"
        )

        st.markdown("**Document status**")
        st.write(
            format_document_status(
                document.get("document_status")
            )
        )

        st.markdown("**Generated**")
        st.write(
            format_generated_at(
                document.get("generated_at")
            )
        )


def render_draft_notice(document):
    if document.get("document_status") != "draft":
        return

    notice = document.get("draft_notice")

    if notice:
        st.warning(notice)


def render_block_heading(block):
    heading = block.get("heading")

    if heading:
        st.markdown(f"**{heading}**")


def render_text_block(block):
    render_block_heading(block)

    text = block.get("text")

    if text:
        st.write(text)


def render_list_block(block):
    render_block_heading(block)

    items = block.get("items") or []
    ordered = bool(block.get("ordered"))

    for index, item in enumerate(
        items,
        start=1,
    ):
        marker = (
            f"{index}."
            if ordered
            else "-"
        )
        st.markdown(f"{marker} {item}")


def render_table_block(block):
    render_block_heading(block)

    records = table_records(block)

    if records:
        st.dataframe(
            records,
            hide_index=True,
            use_container_width=True,
        )


def render_content_block(block):
    block_type = block.get("block_type")

    if block_type == "text":
        render_text_block(block)
    elif block_type == "list":
        render_list_block(block)
    elif block_type == "table":
        render_table_block(block)


def render_content_blocks(content_blocks):
    for block in content_blocks or []:
        render_content_block(block)


def render_subsection(subsection):
    subsection_number = subsection.get(
        "subsection_number"
    )
    title = (
        subsection.get("title")
        or "FSMS subsection"
    )

    if subsection_number:
        st.subheader(
            f"{subsection_number} {title}"
        )
    else:
        st.subheader(title)

    render_content_blocks(
        subsection.get("content_blocks") or []
    )


def render_section(section):
    section_number = section.get(
        "section_number"
    )
    title = (
        section.get("title")
        or "FSMS section"
    )

    if section_number:
        st.header(
            f"{section_number}. {title}"
        )
    else:
        st.header(title)

    render_content_blocks(
        section.get("content_blocks") or []
    )

    for subsection in (
        section.get("subsections") or []
    ):
        render_subsection(subsection)


def show():
    token = st.session_state.get("token")

    if not token:
        st.error(
            "You must be logged in to view the Food "
            "Safety Management System document."
        )
        return

    document = load_fsms_document(token)

    if document is None:
        return

    st.title(
        document.get("document_title")
        or "Food Safety Management System"
    )
    st.caption(
        "Live policy preview generated from the "
        "business's current profile and approved food "
        "safety controls."
    )

    render_document_details(document)
    render_draft_notice(document)

    pdf_bytes = load_fsms_document_pdf(token)

    if pdf_bytes:
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=build_pdf_filename(document),
            mime="application/pdf",
        )

    for section in document.get("sections") or []:
        render_section(section)
