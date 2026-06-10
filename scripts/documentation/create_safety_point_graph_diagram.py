'''
This script generates a diagram of the safety point approval workflow and saves it as a PNG file in the docs/diagrams directory.
The diagram is created using the Mermaid syntax and rendered to PNG format using the graph's draw_mermaid_png method.

To run the script type the following command in the terminal from the root of the project:
python scripts/documentation/create_safety_point_graph_diagram.py

'''
from pathlib import Path

from gen_ai_fsms.workflows.safety_point_graph import safety_point_graph


def main() -> None:
    output_dir = Path("docs/diagrams")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "safety_point_approval_workflow.png"

    png_data = safety_point_graph.get_graph().draw_mermaid_png()

    output_path.write_bytes(png_data)

    print(f"Diagram saved to {output_path}")


if __name__ == "__main__":
    main()