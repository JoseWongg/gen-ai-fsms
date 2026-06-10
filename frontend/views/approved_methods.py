import html
from textwrap import dedent

import streamlit as st
import streamlit.components.v1 as components

from shared import api_request


def show():
    st.title("Approved Food Safety Methods")

    user = st.session_state.get("user")
    if not user or user.get("role") != "admin":
        st.error("You must be an admin to access Approved Food Safety Methods.")
        return

    token = st.session_state.get("token")

    def load_approved_methods():
        response = api_request(
            "GET",
            "/onboarding/safety-points/approved",
            token=token,
        )

        if response is None:
            st.error("Could not load approved food safety methods.")
            return None

        if response.status_code != 200:
            st.error(f"Failed to load approved food safety methods (HTTP {response.status_code}).")
            return None

        return response.json()

    def format_references(references):
        if not references:
            return "<p><em>No provenance references recorded.</em></p>"

        items = "".join(
            f"<li>{html.escape(str(reference))}</li>"
            for reference in references
        )

        return f"<ul>{items}</ul>"

    def format_additional_responses(safety_point):
        additional_responses = safety_point.get("additional_responses", [])

        if not additional_responses:
            return ""

        response_html = []
        for response in additional_responses:
            question = (
                response.get("question_text")
                or response.get("question_key")
                or "Additional question"
            )

            answer = response.get("response_text") or "No response recorded."

            response_html.append(
                "<div class='additional-response'>"
                f"<p><strong>{html.escape(str(question))}</strong></p>"
                f"<p>{html.escape(str(answer))}</p>"
                "</div>"
            )

        return "".join(response_html)

    def format_safety_point_details(safety_point):
        safety_point_id = safety_point.get("safety_point_id") or "Unknown safety point"
        safety_point_text = (
            safety_point.get("safety_point_text")
            or "No safety point text recorded."
        )

        approved_by_user = safety_point.get("approved_by_user") or {}
        approved_by_display = (
            approved_by_user.get("display_name")
            or approved_by_user.get("email")
            or "Not available"
        )
        approved_at = safety_point.get("approved_at") or "Not available"

        provenance_html = format_references(
            safety_point.get("provenance_references", [])
        )
        responses_html = format_additional_responses(safety_point)

        additional_responses_section = ""
        if responses_html:
            additional_responses_section = dedent(f"""
                <details class="approved-subsection">
                    <summary>Additional responses</summary>
                    {responses_html}
                </details>
            """).strip()

        return dedent(f"""
            <details class="approved-safety-point">
                <summary>{html.escape(str(safety_point_id))}</summary>

                <div class="approved-label">Approved safety point</div>
                <div class="approved-text">{html.escape(str(safety_point_text))}</div>

                <p><strong>Approved by:</strong> {html.escape(str(approved_by_display))}</p>
                <p><strong>Approved at:</strong> {html.escape(str(approved_at))}</p>

                <details class="approved-subsection">
                    <summary>Provenance</summary>
                    {provenance_html}
                </details>

                {additional_responses_section}
            </details>
        """).strip()

    def format_approved_methods_html(approved_methods):
        sections = approved_methods.get("sections", [])
        section_html = []

        for section in sections:
            section_name = section.get("section_name") or "Unknown section"
            safe_methods = section.get("safe_methods", [])

            safe_method_html = []

            for safe_method in safe_methods:
                safe_method_name = safe_method.get("safe_method_name") or "Unknown safe method"
                safety_points = safe_method.get("safety_points", [])

                safety_point_html = "".join(
                    format_safety_point_details(safety_point)
                    for safety_point in safety_points
                )

                safe_method_html.append(
                    dedent(f"""
                    <details class="approved-safe-method">
                        <summary>{html.escape(str(safe_method_name))}</summary>
                        {safety_point_html}
                    </details>
                    """).strip()
                )

            section_html.append(
                dedent(f"""
                <details class="approved-section" open>
                    <summary>{html.escape(str(section_name))}</summary>
                    {''.join(safe_method_html)}
                </details>
                """).strip()
            )

        return dedent(f"""
        <style>
        :root {{
            color-scheme: light dark;
        }}

        body {{
            color: inherit;
            background-color: transparent;
            font-family: "Source Sans Pro", Arial, sans-serif;
        }}

        details.approved-section,
        details.approved-safe-method,
        details.approved-safety-point,
        details.additional-responses {{
            color: inherit;
            border: 1px solid rgba(128, 128, 128, 0.45);
            border-radius: 0.5rem;
            margin: 0.6rem 0;
            padding: 0.6rem 0.8rem;
            background-color: rgba(128, 128, 128, 0.08);
        }}

        details.approved-safe-method {{
            margin-left: 1rem;
        }}

        details.approved-safety-point {{
            margin-left: 1rem;
            background-color: rgba(128, 128, 128, 0.05);
        }}

        summary {{
            cursor: pointer;
            font-weight: 600;
            color: inherit;
        }}

        p,
        li,
        div,
        strong,
        em {{
            color: inherit;
        }}

        .safety-point-body {{
            margin-top: 0.8rem;
        }}

        .safety-point-text {{
            max-height: 220px;
            overflow-y: auto;
            padding: 0.8rem;
            border: 1px solid rgba(128, 128, 128, 0.4);
            border-radius: 0.4rem;
            background-color: rgba(128, 128, 128, 0.08);
            white-space: pre-wrap;
            line-height: 1.5;
            color: inherit;
        }}

        .metadata-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.5rem;
            margin: 0.8rem 0;
        }}

        .additional-response {{
            border-top: 1px solid rgba(128, 128, 128, 0.35);
            padding-top: 0.5rem;
            margin-top: 0.5rem;
        }}

        @media (prefers-color-scheme: dark) {{
            body {{
                color: #fafafa;
            }}

            details.approved-section,
            details.approved-safe-method,
            details.approved-safety-point,
            details.additional-responses,
            .safety-point-text {{
                color: #fafafa;
                background-color: rgba(255, 255, 255, 0.08);
                border-color: rgba(255, 255, 255, 0.35);
            }}
        }}
        </style>
        {''.join(section_html)}
        """).strip()

    approved_methods = load_approved_methods()

    if approved_methods is None:
        return

    approved_count = approved_methods.get("approved_safety_point_count", 0) or 0

    st.info(
        "This page shows the SFBB safety points that have been approved for this "
        "business profile. Safety points that have not yet been approved are not shown here."
    )

    if approved_count <= 0:
        st.warning(
            "No approved food safety methods are available yet. Approved safety points "
            "will appear here as the FSMS Builder workflow progresses."
        )
        return

    st.caption(f"{approved_count} approved safety point(s)")

    components.html(
        format_approved_methods_html(approved_methods),
        height=900,
        scrolling=True,
    )
