from datetime import datetime
from typing import Any

import streamlit as st

from shared import api_request


STATUS_LABELS = {
    "completed": "Completed",
    "not_completed": "Not completed",
    "beyond_prototype_scope": "Beyond prototype scope",
}


def load_fsms_document(token):
    response = api_request(
        "GET",
        "/fsms-document",
        token=token,
    )

    if response is None:
        st.error(
            "Unable to load the Food Safety Management System "
            "document because the backend did not respond."
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
                "Unable to load the Food Safety Management System "
                f"document (HTTP {response.status_code})."
            )
        )
        return None

    return response.json()


def format_generated_at(value):
    if not value:
        return "Not available"

    cleaned_value = str(value).replace("Z", "+00:00")

    try:
        parsed_value = datetime.fromisoformat(cleaned_value)
    except ValueError:
        return str(value)

    formatted_value = parsed_value.strftime(
        "%d %B %Y at %H:%M"
    )
    timezone_label = parsed_value.strftime("%Z")

    if timezone_label:
        return f"{formatted_value} {timezone_label}"

    return formatted_value


def format_status_label(status):
    return STATUS_LABELS.get(
        status,
        str(status or "Unknown").replace("_", " ").title(),
    )


def arrangement_table_records(arrangement):
    headers = arrangement.get("table_headers") or []
    rows = arrangement.get("table_rows") or []

    if not headers or not rows:
        return []

    records = []

    for row in rows:
        row_values = row if isinstance(row, list) else []

        records.append(
            {
                header: (
                    row_values[index]
                    if index < len(row_values)
                    else ""
                )
                for index, header in enumerate(headers)
            }
        )

    return records


def render_progress(document):
    progress = document.get("progress") or {}
    completion_percentage = progress.get(
        "completion_percentage",
        0,
    )

    try:
        completion_percentage = int(completion_percentage)
    except (TypeError, ValueError):
        completion_percentage = 0

    completion_percentage = max(
        0,
        min(completion_percentage, 100),
    )

    st.subheader("Document status")

    completion_column, coverage_column = st.columns(2)

    with completion_column:
        st.metric(
            "Current applicable sections",
            progress.get("main_value") or "0/0",
        )
        st.caption(
            progress.get("completion_caption")
            or "Applicable prototype sections completed"
        )

    with coverage_column:
        supported_count = progress.get(
            "supported_section_count",
            0,
        )
        planned_count = progress.get(
            "planned_section_count",
            0,
        )

        st.metric(
            "Prototype coverage",
            f"{supported_count}/{planned_count}",
        )
        st.caption(
            progress.get("coverage_caption")
            or "Planned FSMS sections supported"
        )

    st.progress(completion_percentage)

    document_status = format_status_label(
        progress.get("document_status")
    )
    st.caption(
        f"Overall document status: {document_status}"
    )


def render_business_details(document):
    st.subheader("Business details")

    business_column, site_column = st.columns(2)

    with business_column:
        st.markdown("**Business**")
        st.write(
            document.get("business_name") or "Not recorded"
        )

        st.markdown("**Business type**")
        st.write(
            document.get("business_type") or "Not recorded"
        )

    with site_column:
        st.markdown("**Site**")
        st.write(document.get("site_name") or "Not recorded")

        st.markdown("**Generated**")
        st.write(
            format_generated_at(document.get("generated_at"))
        )

    business_description = document.get(
        "business_description"
    )

    if business_description:
        st.markdown("**Business description**")
        st.write(business_description)


def render_status(status, completion_message=None):
    label = format_status_label(status)
    message = completion_message or label

    if status == "completed":
        st.success(message)
    elif status == "not_completed":
        st.warning(message)
    else:
        st.info(message)


def render_references(references):
    if not references:
        return

    with st.expander("Source references"):
        for reference in references:
            st.write(f"• {reference}")


def render_arrangement(arrangement):
    st.markdown(
        f"**{arrangement.get('title') or 'Business arrangement'}**"
    )

    for statement in arrangement.get("statements") or []:
        st.write(statement)

    records = arrangement_table_records(arrangement)

    if records:
        st.dataframe(
            records,
            hide_index=True,
            use_container_width=True,
        )


def render_subsection(subsection):
    safe_method_id = subsection.get("safe_method_id")
    title = subsection.get("title") or "Safe method"

    if safe_method_id:
        st.subheader(f"{safe_method_id} {title}")
    else:
        st.subheader(title)

    introduction = subsection.get("introduction")

    if introduction:
        st.write(introduction)

    st.caption(
        f"Status: "
        f"{format_status_label(subsection.get('status'))}"
    )

    approved_rules = subsection.get("approved_rules") or []

    if approved_rules:
        st.markdown("**Approved controls**")

        for rule in approved_rules:
            instruction = rule.get("instruction")

            if instruction:
                st.write(f"• {instruction}")

    arrangements = (
        subsection.get("business_specific_arrangements")
        or []
    )

    if arrangements:
        st.markdown("**Business-specific arrangements**")

        for arrangement in arrangements:
            render_arrangement(arrangement)

    render_references(
        subsection.get("source_references") or []
    )


def render_section(section):
    display_order = section.get("display_order")
    title = section.get("title") or "FSMS section"

    if display_order:
        st.header(f"{display_order}. {title}")
    else:
        st.header(title)

    introduction = section.get("introduction")

    if introduction:
        st.write(introduction)

    render_status(
        section.get("status"),
        section.get("completion_message"),
    )

    for subsection in section.get("subsections") or []:
        render_subsection(subsection)


def render_appendix(appendix):
    display_order = appendix.get("display_order")
    title = appendix.get("title") or "Appendix"

    if display_order:
        st.header(f"Appendix {display_order}: {title}")
    else:
        st.header(title)

    arrangements = appendix.get("arrangements") or []

    if arrangements:
        for arrangement in arrangements:
            render_arrangement(arrangement)
    else:
        st.caption(
            "No appendix content has been generated yet."
        )

    render_references(
        appendix.get("source_references") or []
    )


def show():
    token = st.session_state.get("token")

    if not token:
        st.error(
            "You must be logged in to view the Food Safety "
            "Management System document."
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
        "Live preview generated from the business's current "
        "profile, applicable safety points and approved methods."
    )

    render_business_details(document)
    render_progress(document)

    for section in document.get("sections") or []:
        render_section(section)

    for appendix in document.get("appendices") or []:
        render_appendix(appendix)
