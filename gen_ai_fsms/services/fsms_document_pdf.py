from io import BytesIO
from typing import Dict
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from gen_ai_fsms.schemas.fsms_document import (
    FSMSDocument,
    FSMSDocumentAppendix,
    FSMSDocumentArrangement,
    FSMSDocumentSection,
    FSMSDocumentSubsection,
)


PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 18 * mm
RIGHT_MARGIN = 18 * mm
TOP_MARGIN = 18 * mm
BOTTOM_MARGIN = 18 * mm
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN

STATUS_LABELS = {
    "completed": "Completed",
    "not_completed": "Not completed",
    "beyond_prototype_scope": "Beyond prototype scope",
}

STATUS_BACKGROUNDS = {
    "completed": colors.HexColor("#E8F5E9"),
    "not_completed": colors.HexColor("#FFF8E1"),
    "beyond_prototype_scope": colors.HexColor("#E8F1FB"),
}


def render_fsms_document_pdf(
    document: FSMSDocument,
) -> bytes:
    """
    Render one structured FSMS document as PDF bytes.
    """
    output = BytesIO()
    styles = _build_styles()

    pdf = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=RIGHT_MARGIN,
        leftMargin=LEFT_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title=document.document_title,
        author=document.business_name,
        subject=(
            "Food Safety Management System for "
            f"{document.business_name}"
        ),
    )

    story = _build_story(
        document=document,
        styles=styles,
    )

    def draw_page_footer(canvas, template):
        canvas.saveState()
        canvas.setTitle(document.document_title)
        canvas.setAuthor(document.business_name)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#5F6B76"))

        canvas.drawString(
            LEFT_MARGIN,
            9 * mm,
            _normalise_text(document.site_name),
        )
        canvas.drawRightString(
            PAGE_WIDTH - RIGHT_MARGIN,
            9 * mm,
            f"Page {template.page}",
        )

        canvas.restoreState()

    pdf.build(
        story,
        onFirstPage=draw_page_footer,
        onLaterPages=draw_page_footer,
    )

    return output.getvalue()


def _build_story(
    *,
    document: FSMSDocument,
    styles: Dict[str, ParagraphStyle],
):
    story = [
        Paragraph(
            _escape_text(document.document_title),
            styles["document_title"],
        ),
        Spacer(1, 4 * mm),
        Paragraph(
            _escape_text(document.business_name),
            styles["business_name"],
        ),
        Paragraph(
            _escape_text(document.site_name),
            styles["site_name"],
        ),
        Spacer(1, 8 * mm),
        _business_details_table(document, styles),
        Spacer(1, 6 * mm),
        _progress_table(document, styles),
        PageBreak(),
    ]

    for index, section in enumerate(document.sections):
        if index:
            story.append(Spacer(1, 5 * mm))

        story.extend(
            _section_flowables(
                section=section,
                styles=styles,
            )
        )

    if document.appendices:
        story.append(PageBreak())

    for index, appendix in enumerate(document.appendices):
        if index:
            story.append(Spacer(1, 7 * mm))

        story.extend(
            _appendix_flowables(
                appendix=appendix,
                styles=styles,
            )
        )

    return story


def _business_details_table(
    document: FSMSDocument,
    styles: Dict[str, ParagraphStyle],
) -> Table:
    generated_at = document.generated_at.strftime(
        "%d %B %Y at %H:%M UTC"
    )

    data = [
        [
            _label_paragraph("Business", styles),
            _body_paragraph(document.business_name, styles),
            _label_paragraph("Site", styles),
            _body_paragraph(document.site_name, styles),
        ],
        [
            _label_paragraph("Business type", styles),
            _body_paragraph(
                document.business_type or "Not recorded",
                styles,
            ),
            _label_paragraph("Generated", styles),
            _body_paragraph(generated_at, styles),
        ],
    ]

    if document.business_description:
        data.append(
            [
                _label_paragraph(
                    "Business description",
                    styles,
                ),
                _body_paragraph(
                    document.business_description,
                    styles,
                ),
                "",
                "",
            ]
        )

    table = Table(
        data,
        colWidths=[
            31 * mm,
            56 * mm,
            25 * mm,
            56 * mm,
        ],
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#F4F6F8"),
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#C8D0D8"),
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    colors.HexColor("#DCE1E6"),
                ),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                (
                    "SPAN",
                    (1, 2),
                    (3, 2),
                )
                if document.business_description
                else (
                    "LINEBELOW",
                    (0, 0),
                    (-1, -1),
                    0,
                    colors.white,
                ),
            ]
        )
    )

    return table


def _progress_table(
    document: FSMSDocument,
    styles: Dict[str, ParagraphStyle],
) -> Table:
    progress = document.progress

    data = [
        [
            _label_paragraph(
                "Applicable sections completed",
                styles,
            ),
            _label_paragraph(
                "Prototype coverage",
                styles,
            ),
            _label_paragraph(
                "Document status",
                styles,
            ),
        ],
        [
            Paragraph(
                _escape_text(progress.main_value),
                styles["metric_value"],
            ),
            Paragraph(
                _escape_text(
                    f"{progress.supported_section_count}/"
                    f"{progress.planned_section_count}"
                ),
                styles["metric_value"],
            ),
            Paragraph(
                _escape_text(
                    STATUS_LABELS.get(
                        progress.document_status,
                        progress.document_status.replace(
                            "_",
                            " ",
                        ).title(),
                    )
                ),
                styles["metric_value"],
            ),
        ],
        [
            _body_paragraph(
                progress.completion_caption,
                styles,
            ),
            _body_paragraph(
                progress.coverage_caption,
                styles,
            ),
            _body_paragraph(
                f"{progress.completion_percentage}% complete",
                styles,
            ),
        ],
    ]

    table = Table(
        data,
        colWidths=[CONTENT_WIDTH / 3] * 3,
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#EEF3F7"),
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#B8C4CE"),
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    colors.HexColor("#D2D9DF"),
                ),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 1), (-1, 1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    return table


def _section_flowables(
    *,
    section: FSMSDocumentSection,
    styles: Dict[str, ParagraphStyle],
):
    flowables = [
        Paragraph(
            _escape_text(
                f"{section.display_order}. {section.title}"
            ),
            styles["section_heading"],
        ),
        Spacer(1, 2 * mm),
        _body_paragraph(section.introduction, styles),
        Spacer(1, 2 * mm),
        _status_table(
            status=section.status,
            message=section.completion_message,
            styles=styles,
        ),
        Spacer(1, 4 * mm),
    ]

    for subsection in section.subsections:
        flowables.extend(
            _subsection_flowables(
                subsection=subsection,
                styles=styles,
            )
        )

    return flowables


def _subsection_flowables(
    *,
    subsection: FSMSDocumentSubsection,
    styles: Dict[str, ParagraphStyle],
):
    flowables = [
        Paragraph(
            _escape_text(
                f"{subsection.safe_method_id} "
                f"{subsection.title}"
            ),
            styles["subsection_heading"],
        ),
        Spacer(1, 1.5 * mm),
        _body_paragraph(subsection.introduction, styles),
        Paragraph(
            _escape_text(
                "Status: "
                + STATUS_LABELS.get(
                    subsection.status,
                    subsection.status.replace(
                        "_",
                        " ",
                    ).title(),
                )
            ),
            styles["status_caption"],
        ),
        Spacer(1, 2 * mm),
    ]

    if subsection.approved_rules:
        flowables.append(
            Paragraph(
                "Approved controls",
                styles["content_heading"],
            )
        )

        for index, rule in enumerate(
            subsection.approved_rules,
            start=1,
        ):
            flowables.append(
                _body_paragraph(
                    f"{index}. {rule.instruction}",
                    styles,
                )
            )

    if subsection.business_specific_arrangements:
        flowables.append(Spacer(1, 2 * mm))
        flowables.append(
            Paragraph(
                "Business-specific arrangements",
                styles["content_heading"],
            )
        )

        for arrangement in (
            subsection.business_specific_arrangements
        ):
            flowables.extend(
                _arrangement_flowables(
                    arrangement=arrangement,
                    styles=styles,
                )
            )

    if subsection.source_references:
        flowables.extend(
            _reference_flowables(
                references=subsection.source_references,
                styles=styles,
            )
        )

    flowables.append(Spacer(1, 4 * mm))

    return flowables


def _arrangement_flowables(
    *,
    arrangement: FSMSDocumentArrangement,
    styles: Dict[str, ParagraphStyle],
):
    flowables = [
        Paragraph(
            _escape_text(arrangement.title),
            styles["arrangement_heading"],
        )
    ]

    for statement in arrangement.statements:
        flowables.append(
            _body_paragraph(statement, styles)
        )

    if (
        arrangement.table_headers
        and arrangement.table_rows
    ):
        flowables.append(
            _arrangement_table(
                arrangement=arrangement,
                styles=styles,
            )
        )

    flowables.append(Spacer(1, 2 * mm))

    return flowables


def _arrangement_table(
    *,
    arrangement: FSMSDocumentArrangement,
    styles: Dict[str, ParagraphStyle],
) -> Table:
    column_count = len(arrangement.table_headers)
    column_width = CONTENT_WIDTH / column_count

    data = [
        [
            Paragraph(
                _escape_text(header),
                styles["table_header"],
            )
            for header in arrangement.table_headers
        ]
    ]

    for row in arrangement.table_rows:
        data.append(
            [
                _body_paragraph(
                    row[index] if index < len(row) else "",
                    styles,
                )
                for index in range(column_count)
            ]
        )

    table = Table(
        data,
        colWidths=[column_width] * column_count,
        repeatRows=1,
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#DCE6EF"),
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#AEBBC7"),
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    colors.HexColor("#C9D2DA"),
                ),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    return table


def _appendix_flowables(
    *,
    appendix: FSMSDocumentAppendix,
    styles: Dict[str, ParagraphStyle],
):
    flowables = [
        Paragraph(
            _escape_text(
                f"Appendix {appendix.display_order}: "
                f"{appendix.title}"
            ),
            styles["section_heading"],
        ),
        Spacer(1, 3 * mm),
    ]

    if appendix.arrangements:
        for arrangement in appendix.arrangements:
            flowables.extend(
                _arrangement_flowables(
                    arrangement=arrangement,
                    styles=styles,
                )
            )
    else:
        flowables.append(
            _body_paragraph(
                "No appendix content has been generated yet.",
                styles,
            )
        )

    if appendix.source_references:
        flowables.extend(
            _reference_flowables(
                references=appendix.source_references,
                styles=styles,
            )
        )

    return flowables


def _reference_flowables(
    *,
    references,
    styles: Dict[str, ParagraphStyle],
):
    flowables = [
        Spacer(1, 2 * mm),
        Paragraph(
            "Source references",
            styles["content_heading"],
        ),
    ]

    for reference in references:
        flowables.append(
            Paragraph(
                _escape_text(f"- {reference}"),
                styles["reference"],
            )
        )

    return flowables


def _status_table(
    *,
    status: str,
    message,
    styles: Dict[str, ParagraphStyle],
) -> Table:
    label = STATUS_LABELS.get(
        status,
        status.replace("_", " ").title(),
    )
    status_message = message or label

    table = Table(
        [
            [
                Paragraph(
                    (
                        f"<b>{_escape_text(label)}</b><br/>"
                        f"{_escape_text(status_message)}"
                    ),
                    styles["status_box"],
                )
            ]
        ],
        colWidths=[CONTENT_WIDTH],
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    STATUS_BACKGROUNDS.get(
                        status,
                        colors.HexColor("#EEF1F4"),
                    ),
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#B8C1CA"),
                ),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    return table


def _label_paragraph(
    value: str,
    styles: Dict[str, ParagraphStyle],
) -> Paragraph:
    return Paragraph(
        f"<b>{_escape_text(value)}</b>",
        styles["table_body"],
    )


def _body_paragraph(
    value,
    styles: Dict[str, ParagraphStyle],
) -> Paragraph:
    return Paragraph(
        _escape_text(value),
        styles["table_body"],
    )


def _escape_text(value) -> str:
    return escape(
        _normalise_text(value)
    ).replace("\n", "<br/>")


def _normalise_text(value) -> str:
    if value is None:
        return ""

    text = str(value)

    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }

    for original, replacement in replacements.items():
        text = text.replace(original, replacement)

    return text.strip()


def _build_styles() -> Dict[str, ParagraphStyle]:
    sample_styles = getSampleStyleSheet()

    return {
        "document_title": ParagraphStyle(
            "FSMSDocumentTitle",
            parent=sample_styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#17324D"),
            spaceAfter=4,
        ),
        "business_name": ParagraphStyle(
            "FSMSBusinessName",
            parent=sample_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#263746"),
        ),
        "site_name": ParagraphStyle(
            "FSMSSiteName",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#536270"),
        ),
        "section_heading": ParagraphStyle(
            "FSMSSectionHeading",
            parent=sample_styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#17324D"),
            spaceBefore=5,
            spaceAfter=3,
        ),
        "subsection_heading": ParagraphStyle(
            "FSMSSubsectionHeading",
            parent=sample_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#264A69"),
            spaceBefore=4,
            spaceAfter=2,
        ),
        "content_heading": ParagraphStyle(
            "FSMSContentHeading",
            parent=sample_styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#263746"),
            spaceBefore=4,
            spaceAfter=2,
        ),
        "arrangement_heading": ParagraphStyle(
            "FSMSArrangementHeading",
            parent=sample_styles["Heading4"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#334E65"),
            spaceBefore=3,
            spaceAfter=2,
        ),
        "table_body": ParagraphStyle(
            "FSMSTableBody",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#202A33"),
        ),
        "table_header": ParagraphStyle(
            "FSMSTableHeader",
            parent=sample_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#17324D"),
        ),
        "metric_value": ParagraphStyle(
            "FSMSMetricValue",
            parent=sample_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#17324D"),
        ),
        "status_box": ParagraphStyle(
            "FSMSStatusBox",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#263238"),
        ),
        "status_caption": ParagraphStyle(
            "FSMSStatusCaption",
            parent=sample_styles["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#5F6B76"),
            spaceAfter=2,
        ),
        "reference": ParagraphStyle(
            "FSMSReference",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#5F6B76"),
            leftIndent=4 * mm,
        ),
    }
