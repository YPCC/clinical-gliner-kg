#!/usr/bin/env python3
"""Print the medical-data catalog slice used by this showcase."""

from rich.console import Console
from rich.table import Table

from clinical_gliner_kg.data import dataset_access_warning, load_medical_data_catalog

console = Console()


def main() -> None:
    catalog = load_medical_data_catalog()
    table = Table(title="Open / DUA datasets for NER, PHI, and KG evaluation")
    table.add_column("Dataset")
    table.add_column("Access")
    table.add_column("Tasks")
    table.add_column("Use in this repo")
    table.add_column("URL")
    for entry in catalog["datasets"]:
        table.add_row(
            entry["name"],
            str(entry.get("access", "")),
            ", ".join(entry.get("task", [])),
            str(entry.get("use_in_this_repo", "")),
            str(entry.get("url") or entry.get("path") or ""),
        )
    console.print(table)
    console.print(catalog["policy"])
    for entry in catalog["datasets"]:
        warning = dataset_access_warning(entry)
        if warning:
            console.print(f"[yellow]{warning}[/yellow]")


if __name__ == "__main__":
    main()
