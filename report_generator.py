# ==============================================================================
# report_generator.py - Markdown Report Creation Module
# ==============================================================================
# This file is now responsible for creating a well-formatted Markdown (.md)
# document from the analysis data. Markdown is a lightweight and easy-to-read
# text format that can be opened by any text editor.
# ==============================================================================

# --- 1. Import necessary libraries ---
import datetime as dt
from utils import pretty_usd

# --- 2. Main Report Generation Function ---

def create_markdown_report(report_data: dict) -> str:
    """
    Creates a Markdown formatted string from the report data.

    Args:
        report_data: The dictionary containing all the analysis results.

    Returns:
        A string containing the full report in Markdown format.
    """
    # We will build the report line by line in this list.
    md_lines = []

    # --- Header ---
    end_date_str = dt.datetime.fromisoformat(report_data['reportMetadata']['reportDate']).strftime('%d-%m-%Y')
    
    # Add the main title using '#' for a top-level heading.
    md_lines.append(f"# DeFiLlama Weekly Report")
    # Add the subtitle.
    md_lines.append(f"#### Week ending {end_date_str}")
    md_lines.append("\n---") # Add a horizontal rule for separation.

    # --- Helper function for adding report sections ---
    def add_report_section(title, protocols):
        """A helper to create a formatted section in the Markdown report."""
        if not protocols:
            return # Don't add the section if there's no data.

        # Add the section heading using '##' for a second-level heading.
        md_lines.append(f"## {title}")
        
        # Loop through each protocol in the list.
        for i, p in enumerate(protocols):
            # Format the change data string based on the protocol data.
            diff_val = p.get('diff', 0)
            pct_val = p.get('pct', 0)
            
            if diff_val > 0:
                change_str = f"Increased by {pretty_usd(diff_val)}, +{pct_val:.1f} %"
            else:
                # This handles potential decreases if this function is used for them.
                change_str = f"Decreased by {pretty_usd(abs(diff_val))}, {pct_val:.1f} %"

            # Create the Markdown line for the protocol.
            # Syntax: 1. **Name** / Category / $TVL / Change Data – [LINK](URL)
            line = (
                f"{i+1}. **{p.get('name', 'N/A')}** / {p.get('category', 'N/A')} / "
                f"{pretty_usd(p.get('tvl', 0))} / {change_str} – "
                f"[LINK](https://defillama.com/protocol/{p.get('slug', '')})"
            )
            md_lines.append(line)
            
            # Add chain information as a sub-bullet point.
            chains = p.get('chains', [])
            if chains:
                md_lines.append(f"    - Chain: {', '.join(chains)}")

        md_lines.append("") # Add a blank line for spacing after the section.

    # --- New/Removed Protocols Section Helper ---
    def add_new_or_removed_protocols_section(title, protocols):
        """A special helper for 'New' or 'Removed' sections using bullet points."""
        if not protocols:
            return

        md_lines.append(f"## {title} ({len(protocols)})")
        for p in protocols:
            # Syntax: - **Name** / Category / $TVL – [LINK](URL)
            line = (
                f"- **{p.get('name', 'N/A')}** / {p.get('category', 'N/A')} / "
                f"{pretty_usd(p.get('tvl', 0))} – "
                f"[LINK](https://defillama.com/protocol/{p.get('slug', '')})"
            )
            md_lines.append(line)
        md_lines.append("")

    # --- Build the Document Sections ---
    # Call the helper functions to build each part of the report.
    add_report_section('Top TVL Increases (%, 7d)', report_data.get('topIncreasesPct', []))
    add_report_section('Top TVL Increases (absolute, 7d)', report_data.get('topIncreasesAbs', []))
    add_new_or_removed_protocols_section('New Protocols', report_data.get('newProtocols', []))
    add_new_or_removed_protocols_section('Removed Protocols', report_data.get('removedProtocols', []))

    # Join all the lines together into a single string with newline characters.
    return "\n".join(md_lines)
