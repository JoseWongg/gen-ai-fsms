from io import BytesIO
from typing import Dict, List
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import (
    TableOfContents,
)

from gen_ai_fsms.schemas.fsms_policy_document import (
    FSMSListBlock,
    FSMSPolicyContentBlock,
    FSMSPolicyDocument,
    FSMSPolicySection,
    FSMSPolicySubsection,
    FSMSTableBlock,
    FSMSTextBlock,
)


PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 18 * mm
RIGHT_MARGIN = 18 * mm
TOP_MARGIN = 18 * mm
BOTTOM_MARGIN = 18 * mm
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN


class FSMSPolicyPDFTemplate(BaseDocTemplate):
    """
    PDF template that records section headings for the
    generated table of contents.
    """

    def __init__(
        self,
        filename,
        *,
        page_footer,
        **kwargs,
    ):
        super().__init__(
            filename,
            **kwargs,
        )

        content_frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="fsms-policy-content",
        )

        self.addPageTemplates(
            [
                PageTemplate(
                    id="fsms-policy-page",
                    frames=[content_frame],
                    onPage=page_footer,
                    pagesize=self.pagesize,
                )
            ]
        )

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return

        toc_level = getattr(
            flowable,
            "_fsms_toc_level",
            None,
        )
        bookmark_key = getattr(
            flowable,
            "_fsms_bookmark_key",
            None,
        )

        if (
            toc_level is None
            or bookmark_key is None
        ):
            return

        heading_text = flowable.getPlainText()

        self.canv.bookmarkPage(bookmark_key)
        self.canv.addOutlineEntry(
            heading_text,
            bookmark_key,
            level=toc_level,
            closed=False,
        )
        self.notify(
            "TOCEntry",
            (
                toc_level,
                heading_text,
                self.page,
                bookmark_key,
            ),
        )


def render_fsms_policy_document_pdf(
    document: FSMSPolicyDocument,
) -> bytes:
    """
    Render one policy-format FSMS document as PDF bytes.
    """
    output = BytesIO()
    styles = _build_styles()

    def draw_page_footer(canvas, template):
        canvas.saveState()
        canvas.setTitle(document.document_title)
        canvas.setAuthor(document.business_name)
        canvas.setSubject(
            "Food Safety Management System for "
            f"{document.business_name}"
        )
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(
            colors.HexColor("#5F6B76")
        )
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

    pdf = FSMSPolicyPDFTemplate(
        output,
        page_footer=draw_page_footer,
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

    pdf.multiBuild(story)

    return output.getvalue()


def _build_story(
    *,
    document: FSMSPolicyDocument,
    styles: Dict[str, ParagraphStyle],
):
    story = [
        Paragraph(
            _escape_text(document.document_title),
            styles["document_title"],
        ),
        Spacer(1, 5 * mm),
        Paragraph(
            _escape_text(document.business_name),
            styles["business_name"],
        ),
        Paragraph(
            _escape_text(document.site_name),
            styles["site_name"],
        ),
        Spacer(1, 9 * mm),
        _cover_details_table(
            document=document,
            styles=styles,
        ),
    ]

    if document.draft_notice is not None:
        story.extend(
            [
                Spacer(1, 7 * mm),
                _draft_notice_table(
                    document.draft_notice,
                    styles=styles,
                ),
            ]
        )

    story.extend(
        [
            PageBreak(),
            Paragraph(
                "Contents",
                styles["contents_heading"],
            ),
            Spacer(1, 4 * mm),
            _table_of_contents(styles),
            PageBreak(),
        ]
    )

    for index, section in enumerate(
        document.sections
    ):
        if index:
            story.append(Spacer(1, 5 * mm))

        story.extend(
            _section_flowables(
                section=section,
                styles=styles,
            )
        )

    return story


def _cover_details_table(
    *,
    document: FSMSPolicyDocument,
    styles: Dict[str, ParagraphStyle],
) -> Table:
    rows = []

    if document.business_type:
        rows.append(
            [
                _cover_label_paragraph(
                    "Business type",
                    styles,
                ),
                _cover_value_paragraph(
                    document.business_type,
                    styles,
                ),
            ]
        )

    rows.extend(
        [
            [
                _cover_label_paragraph(
                    "Document status",
                    styles,
                ),
                _cover_value_paragraph(
                    document.document_status.title(),
                    styles,
                ),
            ],
            [
                _cover_label_paragraph(
                    "Generated",
                    styles,
                ),
                _cover_value_paragraph(
                    document.generated_at.strftime(
                        "%d %B %Y"
                    ),
                    styles,
                ),
            ],
        ]
    )

    table = Table(
        rows,
        colWidths=[
            46 * mm,
            CONTENT_WIDTH - 46 * mm,
        ],
        hAlign="CENTER",
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
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
            ]
        )
    )

    return table


def _draft_notice_table(
    notice: str,
    *,
    styles: Dict[str, ParagraphStyle],
) -> Table:
    table = Table(
        [
            [
                Paragraph(
                    _escape_text(notice),
                    styles["draft_notice"],
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
                    colors.HexColor("#FFF4D6"),
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.75,
                    colors.HexColor("#C89524"),
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    9,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    9,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
            ]
        )
    )

    return table


def _table_of_contents(
    styles: Dict[str, ParagraphStyle],
) -> TableOfContents:
    contents = TableOfContents()
    contents.levelStyles = [
        styles["toc_section"],
        styles["toc_subsection"],
    ]
    contents.dotsMinLevel = 0

    return contents


def _toc_heading_paragraph(
    text: str,
    style: ParagraphStyle,
    *,
    level: int,
    bookmark_key: str,
) -> Paragraph:
    paragraph = Paragraph(
        _escape_text(text),
        style,
    )
    paragraph._fsms_toc_level = level
    paragraph._fsms_bookmark_key = bookmark_key

    return paragraph


def _bookmark_key(
    prefix: str,
    value,
) -> str:
    normalised_value = "".join(
        character.lower()
        if character.isalnum()
        else "-"
        for character in str(value)
    )
    normalised_value = "-".join(
        part
        for part in normalised_value.split("-")
        if part
    )

    return (
        f"{prefix}-"
        f"{normalised_value or 'heading'}"
    )


def _section_flowables(
    *,
    section: FSMSPolicySection,
    styles: Dict[str, ParagraphStyle],
):
    flowables = [
        _toc_heading_paragraph(
            (
                f"{section.section_number}. "
                f"{section.title}"
            ),
            styles["section_heading"],
            level=0,
            bookmark_key=_bookmark_key(
                "section",
                section.section_number,
            ),
        ),
    ]

    flowables.extend(
        _content_blocks_flowables(
            section.content_blocks,
            styles=styles,
        )
    )

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
    subsection: FSMSPolicySubsection,
    styles: Dict[str, ParagraphStyle],
):
    heading = _toc_heading_paragraph(
        (
            f"{subsection.subsection_number} "
            f"{subsection.title}"
        ),
        styles["subsection_heading"],
        level=1,
        bookmark_key=_bookmark_key(
            "subsection",
            subsection.subsection_number,
        ),
    )

    checklist_index = next(
        (
            index
            for index, block in enumerate(
                subsection.content_blocks
            )
            if (
                block.block_type == "table"
                and block.role == "checklist"
            )
        ),
        None,
    )

    if checklist_index is None:
        flowables = [heading]
        flowables.extend(
            _content_blocks_flowables(
                subsection.content_blocks,
                styles=styles,
            )
        )
    else:
        grouped_blocks = (
            subsection.content_blocks[
                : checklist_index + 1
            ]
        )
        remaining_blocks = (
            subsection.content_blocks[
                checklist_index + 1 :
            ]
        )

        flowables = [
            KeepTogether(
                [
                    heading,
                    *_content_blocks_flowables(
                        grouped_blocks,
                        styles=styles,
                    ),
                ]
            )
        ]
        flowables.extend(
            _content_blocks_flowables(
                remaining_blocks,
                styles=styles,
            )
        )

    flowables.append(Spacer(1, 3 * mm))

    return flowables


def _content_blocks_flowables(
    content_blocks: List[FSMSPolicyContentBlock],
    *,
    styles: Dict[str, ParagraphStyle],
):
    flowables = []

    for block in content_blocks:
        if block.block_type == "text":
            flowables.extend(
                _text_block_flowables(
                    block,
                    styles=styles,
                )
            )
            continue

        if block.block_type == "list":
            flowables.extend(
                _list_block_flowables(
                    block,
                    styles=styles,
                )
            )
            continue

        if block.block_type == "table":
            flowables.extend(
                _table_block_flowables(
                    block,
                    styles=styles,
                )
            )
            continue

        raise ValueError(
            "Unsupported FSMS policy PDF content block: "
            f"{block.block_type}"
        )

    return flowables


def _text_block_flowables(
    block: FSMSTextBlock,
    *,
    styles: Dict[str, ParagraphStyle],
):
    flowables = []

    if block.heading:
        flowables.append(
            Paragraph(
                _escape_text(block.heading),
                styles["content_heading"],
            )
        )

    flowables.extend(
        [
            Paragraph(
                _escape_text(block.text),
                styles["body"],
            ),
            Spacer(1, 2.5 * mm),
        ]
    )

    return flowables


def _list_block_flowables(
    block: FSMSListBlock,
    *,
    styles: Dict[str, ParagraphStyle],
):
    flowables = []

    if block.heading:
        flowables.append(
            Paragraph(
                _escape_text(block.heading),
                styles["content_heading"],
            )
        )

    for index, item in enumerate(
        block.items,
        start=1,
    ):
        if block.ordered:
            bullet = _escape_text(f"{index}.")
        else:
            bullet = "&bull;"

        flowables.append(
            Paragraph(
                (
                    f"<bullet>{bullet}</bullet>"
                    f"{_escape_text(item)}"
                ),
                styles["list_item"],
            )
        )

    flowables.append(Spacer(1, 2.5 * mm))

    return flowables


def _table_block_flowables(
    block: FSMSTableBlock,
    *,
    styles: Dict[str, ParagraphStyle],
):
    flowables = []

    if block.heading:
        flowables.append(
            Paragraph(
                _escape_text(block.heading),
                styles["content_heading"],
            )
        )

    flowables.extend(
        [
            _policy_table(
                block,
                styles=styles,
            ),
            Spacer(1, 3 * mm),
        ]
    )

    return flowables


def _policy_table(
    block: FSMSTableBlock,
    *,
    styles: Dict[str, ParagraphStyle],
) -> Table:
    data = [
        [
            Paragraph(
                _escape_text(header),
                styles["table_header"],
            )
            for header in block.headers
        ]
    ]

    for row in block.rows:
        data.append(
            [
                _table_cell_paragraph(
                    value,
                    styles=styles,
                )
                for value in row
            ]
        )

    table = Table(
        data,
        colWidths=_table_column_widths(
            len(block.headers)
        ),
        repeatRows=1,
        splitByRow=1,
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
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    return table


def _table_column_widths(
    column_count: int,
) -> List[float]:
    if column_count <= 0:
        raise ValueError(
            "FSMS policy PDF tables require at least "
            "one column."
        )

    configured_fractions = {
        2: [
            0.45,
            0.55,
        ],
        3: [
            0.24,
            0.17,
            0.59,
        ],
        5: [
            0.22,
            0.15,
            0.13,
            0.13,
            0.37,
        ],
        6: [
            0.19,
            0.17,
            0.10,
            0.10,
            0.26,
            0.18,
        ],
    }

    fractions = configured_fractions.get(
        column_count
    )

    if fractions is None:
        fractions = [
            1 / column_count
        ] * column_count

    return [
        CONTENT_WIDTH * fraction
        for fraction in fractions
    ]


def _cover_label_paragraph(
    value: str,
    styles: Dict[str, ParagraphStyle],
) -> Paragraph:
    return Paragraph(
        _escape_text(value),
        styles["cover_label"],
    )


def _cover_value_paragraph(
    value: str,
    styles: Dict[str, ParagraphStyle],
) -> Paragraph:
    return Paragraph(
        _escape_text(value),
        styles["cover_value"],
    )


def _table_cell_paragraph(
    value,
    *,
    styles: Dict[str, ParagraphStyle],
) -> Paragraph:
    escaped_value = _escape_text(value)

    if not escaped_value:
        escaped_value = "&#160;"

    return Paragraph(
        escaped_value,
        styles["table_body"],
    )


def _escape_text(value) -> str:
    return escape(
        _normalise_text(value)
    ).replace(
        "\n",
        "<br/>",
    )


def _normalise_text(value) -> str:
    if value is None:
        return ""

    text = str(value)

    replacements = {
        "\u2212": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }

    for original, replacement in replacements.items():
        text = text.replace(
            original,
            replacement,
        )

    return text.strip()


def _build_styles() -> Dict[str, ParagraphStyle]:
    sample_styles = getSampleStyleSheet()

    return {
        "document_title": ParagraphStyle(
            "FSMSPolicyDocumentTitle",
            parent=sample_styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#17324D"),
            spaceAfter=4,
        ),
        "business_name": ParagraphStyle(
            "FSMSPolicyBusinessName",
            parent=sample_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#263746"),
            spaceAfter=2,
        ),
        "site_name": ParagraphStyle(
            "FSMSPolicySiteName",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#536270"),
        ),
        "cover_label": ParagraphStyle(
            "FSMSPolicyCoverLabel",
            parent=sample_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#263746"),
        ),
        "cover_value": ParagraphStyle(
            "FSMSPolicyCoverValue",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#263746"),
        ),
        "draft_notice": ParagraphStyle(
            "FSMSPolicyDraftNotice",
            parent=sample_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#5D4300"),
        ),
        "contents_heading": ParagraphStyle(
            "FSMSPolicyContentsHeading",
            parent=sample_styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#17324D"),
            spaceAfter=6,
        ),
        "toc_section": ParagraphStyle(
            "FSMSPolicyTOCSection",
            parent=sample_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            leftIndent=0,
            firstLineIndent=0,
            spaceBefore=4,
            textColor=colors.HexColor("#17324D"),
        ),
        "toc_subsection": ParagraphStyle(
            "FSMSPolicyTOCSubsection",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            leftIndent=10 * mm,
            firstLineIndent=0,
            spaceBefore=1,
            textColor=colors.HexColor("#263746"),
        ),
        "section_heading": ParagraphStyle(
            "FSMSPolicySectionHeading",
            parent=sample_styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#17324D"),
            spaceBefore=5,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "subsection_heading": ParagraphStyle(
            "FSMSPolicySubsectionHeading",
            parent=sample_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#264A69"),
            spaceBefore=5,
            spaceAfter=3,
            keepWithNext=True,
        ),
        "content_heading": ParagraphStyle(
            "FSMSPolicyContentHeading",
            parent=sample_styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#263746"),
            spaceBefore=3,
            spaceAfter=2,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "FSMSPolicyBody",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#202A33"),
            spaceAfter=1,
        ),
        "list_item": ParagraphStyle(
            "FSMSPolicyListItem",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#202A33"),
            leftIndent=8 * mm,
            bulletIndent=1.5 * mm,
            spaceAfter=2,
        ),
        "table_body": ParagraphStyle(
            "FSMSPolicyTableBody",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.8,
            leading=10,
            textColor=colors.HexColor("#202A33"),
        ),
        "table_header": ParagraphStyle(
            "FSMSPolicyTableHeader",
            parent=sample_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.6,
            leading=9.5,
            textColor=colors.HexColor("#17324D"),
        ),
    }
