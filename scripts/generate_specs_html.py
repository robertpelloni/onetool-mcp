#!/usr/bin/env python3
"""Generate an HTML page with complete detailed OpenSpec specifications.

Shows all requirements and scenarios with filtering by category, spec, etc.
Uses onearch color scheme (teal/cyan theme).
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
OPENSPEC_DIR = PROJECT_ROOT / "openspec"
SPECS_DIR = OPENSPEC_DIR / "specs"
OUTPUT_FILE = PROJECT_ROOT / "docs" / "_internal" / "specs.html"


@dataclass
class Scenario:
    """A scenario within a requirement."""

    name: str
    content: str  # Full scenario text (GIVEN/WHEN/THEN)


@dataclass
class Requirement:
    """A requirement within a spec."""

    name: str
    description: str
    scenarios: list[Scenario] = field(default_factory=list)


@dataclass
class Spec:
    """Represents an OpenSpec specification."""

    name: str
    folder: str
    purpose: str
    category: str
    requirements: list[Requirement] = field(default_factory=list)

    @property
    def requirement_count(self) -> int:
        return len(self.requirements)

    @property
    def scenario_count(self) -> int:
        return sum(len(r.scenarios) for r in self.requirements)


def categorize_spec(folder_name: str) -> str:
    """Determine the category based on folder naming convention."""
    if folder_name.startswith("_nf-"):
        return "Non-Functional"
    elif folder_name.startswith("bench-") or folder_name == "bench":
        return "Benchmark"
    elif folder_name.startswith("serve-"):
        return "Server"
    elif folder_name.startswith("tool-"):
        return "Tool"
    elif folder_name.startswith("onetool"):
        return "CLI"
    else:
        return "Other"


def parse_spec(spec_path: Path) -> Spec | None:
    """Parse a spec.md file and extract all requirements and scenarios."""
    try:
        content = spec_path.read_text()
    except (OSError, IOError):
        return None

    folder = spec_path.parent.name

    # Extract name from first heading
    name_match = re.search(r"^#\s+(.+?)\s+Specification", content, re.MULTILINE)
    name = name_match.group(1) if name_match else folder

    # Extract purpose
    purpose_match = re.search(
        r"##\s+Purpose\s*\n\s*\n?(.*?)(?=\n##|\n---|\Z)", content, re.DOTALL
    )
    purpose = ""
    if purpose_match:
        purpose = purpose_match.group(1).strip()
        purpose = purpose.split("\n\n")[0].strip()
        purpose = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", purpose)

    # Parse requirements and scenarios
    requirements = []

    # Split by requirement headers (use ### followed by space to not match ####)
    req_pattern = r"### Requirement:\s*(.+?)(?=\n### |\n---|\Z)"
    req_matches = re.finditer(req_pattern, content, re.DOTALL)

    for req_match in req_matches:
        req_full = req_match.group(0)
        req_name_match = re.search(r"### Requirement:\s*(.+)", req_full)
        req_name = req_name_match.group(1).strip() if req_name_match else "Unknown"

        # Get requirement description (text before first scenario)
        desc_match = re.search(
            r"### Requirement:.+?\n\n(.+?)(?=\n####|\Z)", req_full, re.DOTALL
        )
        req_desc = ""
        if desc_match:
            req_desc = desc_match.group(1).strip()
            # Clean up markdown
            req_desc = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", req_desc)

        # Parse scenarios within this requirement
        scenarios = []
        scenario_pattern = r"#### Scenario:\s*(.+?)(?=\n#### |\n### |\n---|\Z)"
        for sc_match in re.finditer(scenario_pattern, req_full, re.DOTALL):
            sc_full = sc_match.group(0)
            sc_name_match = re.search(r"#### Scenario:\s*(.+)", sc_full)
            sc_name = sc_name_match.group(1).strip() if sc_name_match else "Unknown"

            # Get scenario content (everything after the header)
            sc_content_match = re.search(
                r"#### Scenario:.+?\n(.+)", sc_full, re.DOTALL
            )
            sc_content = ""
            if sc_content_match:
                sc_content = sc_content_match.group(1).strip()

            scenarios.append(Scenario(name=sc_name, content=sc_content))

        requirements.append(
            Requirement(name=req_name, description=req_desc, scenarios=scenarios)
        )

    return Spec(
        name=name,
        folder=folder,
        purpose=purpose,
        category=categorize_spec(folder),
        requirements=requirements,
    )


def scan_specs() -> list[Spec]:
    """Scan all spec files and return parsed specs."""
    specs = []
    for spec_file in sorted(SPECS_DIR.glob("*/spec.md")):
        spec = parse_spec(spec_file)
        if spec:
            specs.append(spec)
    return specs


def generate_html(specs: list[Spec]) -> str:
    """Generate the HTML page with complete spec details."""

    # Calculate summary stats
    total_specs = len(specs)
    total_requirements = sum(s.requirement_count for s in specs)
    total_scenarios = sum(s.scenario_count for s in specs)
    categories = {}
    for spec in specs:
        categories[spec.category] = categories.get(spec.category, 0) + 1

    # Build flat requirements data for the grid
    requirements_data = []
    for spec in specs:
        for req in spec.requirements:
            for scenario in req.scenarios:
                requirements_data.append(
                    {
                        "spec": spec.name,
                        "specFolder": spec.folder,
                        "category": spec.category,
                        "requirement": req.name,
                        "requirementDesc": req.description,
                        "scenario": scenario.name,
                        "scenarioContent": scenario.content,
                    }
                )

    # Also build spec-level data
    specs_data = []
    for spec in specs:
        specs_data.append(
            {
                "name": spec.name,
                "folder": spec.folder,
                "category": spec.category,
                "purpose": spec.purpose,
                "requirements": spec.requirement_count,
                "scenarios": spec.scenario_count,
                "requirementsList": [
                    {
                        "name": r.name,
                        "description": r.description,
                        "scenarios": [
                            {"name": s.name, "content": s.content} for s in r.scenarios
                        ],
                    }
                    for r in spec.requirements
                ],
            }
        )

    requirements_json = json.dumps(requirements_data, indent=2)
    specs_json = json.dumps(specs_data, indent=2)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenSpec Specifications</title>
    <script src="https://cdn.jsdelivr.net/npm/ag-grid-community/dist/ag-grid-community.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root {{
            /* OneTool/OneArch Color Scheme - Light */
            --brand-primary: #087EA4;
            --brand-primary-light: #5BB0C9;
            --brand-primary-dark: #065A75;
            --brand-primary-bg: #E6F7FF;
            --brand-text: #404756;
            --brand-text-secondary: #6b7280;
            --bg-main: #ffffff;
            --bg-card: #f8fafc;
            --bg-highlight: #F0F1F4;
            --border-color: #e2e8f0;
            --success: #22C55E;
            --warning: #F59E0B;
            --error: #EF4444;
        }}

        [data-theme="dark"] {{
            /* OneTool/OneArch Color Scheme - Dark */
            --brand-primary: #58C4DC;
            --brand-primary-light: #7DD3E8;
            --brand-primary-dark: #3998B6;
            --brand-primary-bg: #283542;
            --brand-text: #f6f7f9;
            --brand-text-secondary: #99a1b3;
            --bg-main: #23272F;
            --bg-card: #2a2f3a;
            --bg-highlight: #343a46;
            --border-color: #3a4150;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: var(--bg-main);
            color: var(--brand-text);
            line-height: 1.6;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1600px;
            margin: 0 auto;
            padding: 24px;
        }}

        /* Header */
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
            flex-wrap: wrap;
            gap: 16px;
        }}

        .header-left h1 {{
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--brand-primary);
            margin-bottom: 4px;
        }}

        .header-left .subtitle {{
            font-size: 0.9rem;
            color: var(--brand-text-secondary);
        }}

        .header-right {{
            display: flex;
            gap: 12px;
            align-items: center;
        }}

        /* Theme Toggle */
        .theme-toggle {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 8px 12px;
            cursor: pointer;
            color: var(--brand-text);
            font-size: 0.85rem;
            transition: all 0.2s;
        }}

        .theme-toggle:hover {{
            border-color: var(--brand-primary);
        }}

        /* Summary Cards */
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}

        .summary-card {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid var(--border-color);
            transition: all 0.2s;
        }}

        .summary-card:hover {{
            border-color: var(--brand-primary);
            box-shadow: 0 4px 12px rgba(8, 126, 164, 0.1);
        }}

        .summary-card .value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--brand-primary);
        }}

        .summary-card .label {{
            font-size: 0.8rem;
            color: var(--brand-text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        /* Tabs */
        .tabs {{
            display: flex;
            gap: 4px;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0;
        }}

        .tab {{
            padding: 12px 20px;
            background: transparent;
            border: none;
            border-bottom: 2px solid transparent;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 500;
            color: var(--brand-text-secondary);
            transition: all 0.2s;
            margin-bottom: -1px;
        }}

        .tab:hover {{
            color: var(--brand-primary);
        }}

        .tab.active {{
            color: var(--brand-primary);
            border-bottom-color: var(--brand-primary);
        }}

        /* Filters */
        .filters {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 20px;
            align-items: center;
        }}

        .search-input {{
            flex: 1;
            min-width: 250px;
            max-width: 400px;
            padding: 10px 14px;
            font-size: 0.9rem;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--brand-text);
            transition: border-color 0.2s;
        }}

        .search-input:focus {{
            outline: none;
            border-color: var(--brand-primary);
        }}

        .search-input::placeholder {{
            color: var(--brand-text-secondary);
        }}

        .filter-select {{
            padding: 10px 14px;
            font-size: 0.9rem;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--brand-text);
            cursor: pointer;
            min-width: 150px;
        }}

        .filter-select:focus {{
            outline: none;
            border-color: var(--brand-primary);
        }}

        /* Category Pills */
        .category-pills {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .category-pill {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 6px 14px;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s;
            color: var(--brand-text-secondary);
        }}

        .category-pill:hover, .category-pill.active {{
            background: var(--brand-primary);
            border-color: var(--brand-primary);
            color: white;
        }}

        .category-pill .count {{
            background: rgba(255, 255, 255, 0.2);
            border-radius: 10px;
            padding: 1px 6px;
            margin-left: 6px;
            font-size: 0.7rem;
        }}

        /* Tab Content */
        .tab-content {{
            display: none;
        }}

        .tab-content.active {{
            display: block;
        }}

        /* Grid Container */
        .grid-container {{
            height: 700px;
            width: 100%;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid var(--border-color);
        }}

        /* AG Grid Theme */
        .ag-theme-alpine, .ag-theme-alpine-dark {{
            --ag-font-family: inherit;
            --ag-font-size: 13px;
            --ag-row-height: 44px;
            --ag-header-height: 44px;
        }}

        .ag-theme-alpine {{
            --ag-background-color: var(--bg-card);
            --ag-header-background-color: var(--bg-highlight);
            --ag-odd-row-background-color: var(--bg-main);
            --ag-row-hover-color: var(--brand-primary-bg);
            --ag-selected-row-background-color: var(--brand-primary-bg);
            --ag-header-foreground-color: var(--brand-text);
            --ag-foreground-color: var(--brand-text);
            --ag-secondary-foreground-color: var(--brand-text-secondary);
            --ag-border-color: var(--border-color);
        }}

        .ag-theme-alpine-dark {{
            --ag-background-color: var(--bg-card);
            --ag-header-background-color: var(--bg-highlight);
            --ag-odd-row-background-color: rgba(255, 255, 255, 0.02);
            --ag-row-hover-color: var(--brand-primary-bg);
            --ag-selected-row-background-color: var(--brand-primary-bg);
            --ag-header-foreground-color: var(--brand-text);
            --ag-foreground-color: var(--brand-text);
            --ag-secondary-foreground-color: var(--brand-text-secondary);
            --ag-border-color: var(--border-color);
        }}

        .ag-header-cell-label {{
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.7rem;
            letter-spacing: 0.5px;
        }}

        /* Custom Renderers */
        .spec-link {{
            color: var(--brand-primary);
            text-decoration: none;
            font-weight: 500;
        }}

        .spec-link:hover {{
            text-decoration: underline;
        }}

        .category-badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .category-badge.nonfunctional {{ background: rgba(139, 92, 246, 0.15); color: #8b5cf6; }}
        .category-badge.benchmark {{ background: rgba(34, 197, 94, 0.15); color: #22c55e; }}
        .category-badge.server {{ background: rgba(59, 130, 246, 0.15); color: #3b82f6; }}
        .category-badge.tool {{ background: rgba(8, 126, 164, 0.15); color: var(--brand-primary); }}
        .category-badge.cli {{ background: rgba(236, 72, 153, 0.15); color: #ec4899; }}
        .category-badge.other {{ background: rgba(107, 114, 128, 0.15); color: #6b7280; }}

        [data-theme="dark"] .category-badge.nonfunctional {{ background: rgba(139, 92, 246, 0.25); }}
        [data-theme="dark"] .category-badge.benchmark {{ background: rgba(34, 197, 94, 0.25); }}
        [data-theme="dark"] .category-badge.server {{ background: rgba(59, 130, 246, 0.25); }}
        [data-theme="dark"] .category-badge.tool {{ background: rgba(88, 196, 220, 0.25); color: var(--brand-primary); }}
        [data-theme="dark"] .category-badge.cli {{ background: rgba(236, 72, 153, 0.25); }}
        [data-theme="dark"] .category-badge.other {{ background: rgba(107, 114, 128, 0.25); }}

        .metric {{
            font-weight: 600;
            color: var(--brand-primary);
        }}

        /* Scenario Details - Markdown Rendering */
        .scenario-details {{
            font-size: 0.8rem;
            line-height: 1.5;
        }}

        .scenario-details p {{
            margin: 0 0 4px 0;
        }}

        .scenario-details p:last-child {{
            margin-bottom: 0;
        }}

        .scenario-details ul {{
            margin: 4px 0;
            padding-left: 16px;
        }}

        .scenario-details li {{
            margin: 2px 0;
        }}

        .scenario-details li::marker {{
            color: var(--brand-primary);
        }}

        .scenario-details strong {{
            color: var(--brand-primary);
            font-weight: 600;
        }}

        .scenario-details code {{
            background: var(--bg-highlight);
            padding: 1px 5px;
            border-radius: 3px;
            font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
            font-size: 0.75rem;
            color: var(--brand-primary-dark);
        }}

        .scenario-details pre {{
            background: var(--bg-highlight);
            padding: 8px 10px;
            border-radius: 4px;
            overflow-x: auto;
            margin: 4px 0;
        }}

        .scenario-details pre code {{
            background: none;
            padding: 0;
        }}

        [data-theme="dark"] .scenario-details code {{
            color: var(--brand-primary-light);
        }}

        /* Footer */
        footer {{
            text-align: center;
            margin-top: 32px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
            color: var(--brand-text-secondary);
            font-size: 0.8rem;
        }}

        footer a {{
            color: var(--brand-primary);
            text-decoration: none;
        }}

        footer a:hover {{
            text-decoration: underline;
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            .header-left h1 {{
                font-size: 1.4rem;
            }}

            .summary-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}

            .grid-container {{
                height: 450px;
            }}

            .filters {{
                flex-direction: column;
                align-items: stretch;
            }}

            .search-input {{
                max-width: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-left">
                <h1>OpenSpec Specifications</h1>
                <p class="subtitle">Complete specification index for OneTool</p>
            </div>
            <div class="header-right">
                <button class="theme-toggle" onclick="toggleTheme()">
                    <span id="themeIcon">🌙</span> Dark Mode
                </button>
            </div>
        </header>

        <div class="summary-grid">
            <div class="summary-card">
                <div class="value">{total_specs}</div>
                <div class="label">Specifications</div>
            </div>
            <div class="summary-card">
                <div class="value">{total_requirements}</div>
                <div class="label">Requirements</div>
            </div>
            <div class="summary-card">
                <div class="value">{total_scenarios}</div>
                <div class="label">Scenarios</div>
            </div>
            <div class="summary-card">
                <div class="value">{len(categories)}</div>
                <div class="label">Categories</div>
            </div>
        </div>

        <div class="tabs">
            <button class="tab active" data-tab="scenarios">All Scenarios</button>
            <button class="tab" data-tab="requirements">By Requirement</button>
            <button class="tab" data-tab="specs">By Specification</button>
        </div>

        <!-- Scenarios Tab -->
        <div id="scenarios-tab" class="tab-content active">
            <div class="filters">
                <input type="text" class="search-input" id="scenarioSearch" placeholder="Search scenarios...">
                <select class="filter-select" id="categoryFilter">
                    <option value="">All Categories</option>
                    {"".join(f'<option value="{cat}">{cat} ({count})</option>' for cat, count in sorted(categories.items()))}
                </select>
                <select class="filter-select" id="specFilter">
                    <option value="">All Specs</option>
                    {"".join(f'<option value="{spec.name}">{spec.name}</option>' for spec in sorted(specs, key=lambda s: s.name))}
                </select>
            </div>
            <div id="scenariosGrid" class="grid-container ag-theme-alpine"></div>
        </div>

        <!-- Requirements Tab -->
        <div id="requirements-tab" class="tab-content">
            <div class="filters">
                <input type="text" class="search-input" id="reqSearch" placeholder="Search requirements...">
                <div class="category-pills" id="reqCategoryPills">
                    <div class="category-pill active" data-category="">All</div>
                    {"".join(f'<div class="category-pill" data-category="{cat}">{cat}</div>' for cat in sorted(categories.keys()))}
                </div>
            </div>
            <div id="requirementsGrid" class="grid-container ag-theme-alpine"></div>
        </div>

        <!-- Specs Tab -->
        <div id="specs-tab" class="tab-content">
            <div class="filters">
                <input type="text" class="search-input" id="specSearch" placeholder="Search specifications...">
            </div>
            <div id="specsGrid" class="grid-container ag-theme-alpine"></div>
        </div>

        <footer>
            <p>Generated {datetime.now().strftime("%Y-%m-%d %H:%M")} |
               <a href="https://github.com/beycom/onetool-mcp/blob/main/openspec/specs/INDEX.md" target="_blank">INDEX.md</a> |
               <a href="https://github.com/beycom/onetool-mcp" target="_blank">GitHub</a>
            </p>
        </footer>
    </div>

    <script>
        // Data
        const scenariosData = {requirements_json};
        const specsData = {specs_json};

        // Build requirements summary data
        const requirementsData = [];
        specsData.forEach(spec => {{
            spec.requirementsList.forEach(req => {{
                requirementsData.push({{
                    spec: spec.name,
                    specFolder: spec.folder,
                    category: spec.category,
                    requirement: req.name,
                    description: req.description,
                    scenarioCount: req.scenarios.length
                }});
            }});
        }});

        // Renderers
        function categoryRenderer(params) {{
            const cat = (params.value || '').toLowerCase().replace(/[- ]/g, '');
            return `<span class="category-badge ${{cat}}">${{params.value}}</span>`;
        }}

        function specLinkRenderer(params) {{
            const folder = params.data.specFolder || params.data.folder;
            const url = `https://github.com/onetool-mcp/onetool-mcp/blob/main/openspec/specs/${{folder}}/spec.md`;
            return `<a href="${{url}}" class="spec-link" target="_blank">${{params.value}}</a>`;
        }}

        function metricRenderer(params) {{
            return `<span class="metric">${{params.value}}</span>`;
        }}

        function scenarioDetailsRenderer(params) {{
            if (!params.value) return '';
            // Use marked to render markdown
            const html = marked.parse(params.value);
            return `<div class="scenario-details">${{html}}</div>`;
        }}

        // Grid APIs
        let scenariosGridApi, requirementsGridApi, specsGridApi;

        // Scenarios Grid
        const scenariosColumnDefs = [
            {{ headerName: 'Spec', field: 'spec', width: 140, cellRenderer: specLinkRenderer, filter: true, sortable: true }},
            {{ headerName: 'Category', field: 'category', width: 120, cellRenderer: categoryRenderer, filter: true, sortable: true }},
            {{ headerName: 'Requirement', field: 'requirement', width: 200, filter: true, sortable: true }},
            {{ headerName: 'Scenario', field: 'scenario', width: 180, filter: true, sortable: true }},
            {{ headerName: 'Details', field: 'scenarioContent', flex: 1, minWidth: 400, filter: true, sortable: true, autoHeight: true, cellRenderer: scenarioDetailsRenderer, cellStyle: {{ 'padding': '8px 12px' }} }},
        ];

        const scenariosGridOptions = {{
            columnDefs: scenariosColumnDefs,
            rowData: scenariosData,
            defaultColDef: {{ resizable: true }},
            animateRows: true,
            pagination: true,
            paginationPageSize: 25,
        }};

        // Requirements Grid
        const reqColumnDefs = [
            {{ headerName: 'Spec', field: 'spec', width: 160, cellRenderer: specLinkRenderer, filter: true, sortable: true }},
            {{ headerName: 'Category', field: 'category', width: 130, cellRenderer: categoryRenderer, filter: true, sortable: true }},
            {{ headerName: 'Requirement', field: 'requirement', flex: 2, minWidth: 250, filter: true, sortable: true }},
            {{ headerName: 'Description', field: 'description', flex: 2, minWidth: 300, filter: true, sortable: true, wrapText: true, autoHeight: true }},
            {{ headerName: 'Scenarios', field: 'scenarioCount', width: 100, cellRenderer: metricRenderer, filter: 'agNumberColumnFilter', sortable: true }},
        ];

        const reqGridOptions = {{
            columnDefs: reqColumnDefs,
            rowData: requirementsData,
            defaultColDef: {{ resizable: true }},
            animateRows: true,
            pagination: true,
            paginationPageSize: 20,
        }};

        // Specs Grid
        const specsColumnDefs = [
            {{ headerName: 'Name', field: 'name', flex: 1, minWidth: 180, cellRenderer: specLinkRenderer, filter: true, sortable: true }},
            {{ headerName: 'Category', field: 'category', width: 130, cellRenderer: categoryRenderer, filter: true, sortable: true }},
            {{ headerName: 'Purpose', field: 'purpose', flex: 2, minWidth: 300, filter: true, sortable: true, wrapText: true, autoHeight: true }},
            {{ headerName: 'Req.', field: 'requirements', width: 80, cellRenderer: metricRenderer, filter: 'agNumberColumnFilter', sortable: true }},
            {{ headerName: 'Scenarios', field: 'scenarios', width: 100, cellRenderer: metricRenderer, filter: 'agNumberColumnFilter', sortable: true }},
        ];

        const specsGridOptions = {{
            columnDefs: specsColumnDefs,
            rowData: specsData,
            defaultColDef: {{ resizable: true }},
            animateRows: true,
            pagination: true,
            paginationPageSize: 20,
        }};

        // Initialize grids
        document.addEventListener('DOMContentLoaded', () => {{
            scenariosGridApi = agGrid.createGrid(document.getElementById('scenariosGrid'), scenariosGridOptions);
            requirementsGridApi = agGrid.createGrid(document.getElementById('requirementsGrid'), reqGridOptions);
            specsGridApi = agGrid.createGrid(document.getElementById('specsGrid'), specsGridOptions);
        }});

        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {{
            tab.addEventListener('click', () => {{
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab + '-tab').classList.add('active');
            }});
        }});

        // Scenario filters
        document.getElementById('scenarioSearch').addEventListener('input', (e) => {{
            scenariosGridApi.setGridOption('quickFilterText', e.target.value);
        }});

        document.getElementById('categoryFilter').addEventListener('change', (e) => {{
            const value = e.target.value;
            if (value) {{
                scenariosGridApi.setGridOption('rowData', scenariosData.filter(r => r.category === value));
            }} else {{
                scenariosGridApi.setGridOption('rowData', scenariosData);
            }}
        }});

        document.getElementById('specFilter').addEventListener('change', (e) => {{
            const value = e.target.value;
            if (value) {{
                scenariosGridApi.setGridOption('rowData', scenariosData.filter(r => r.spec === value));
            }} else {{
                scenariosGridApi.setGridOption('rowData', scenariosData);
            }}
        }});

        // Requirements filters
        document.getElementById('reqSearch').addEventListener('input', (e) => {{
            requirementsGridApi.setGridOption('quickFilterText', e.target.value);
        }});

        document.querySelectorAll('#reqCategoryPills .category-pill').forEach(pill => {{
            pill.addEventListener('click', () => {{
                document.querySelectorAll('#reqCategoryPills .category-pill').forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                const cat = pill.dataset.category;
                if (cat) {{
                    requirementsGridApi.setGridOption('rowData', requirementsData.filter(r => r.category === cat));
                }} else {{
                    requirementsGridApi.setGridOption('rowData', requirementsData);
                }}
            }});
        }});

        // Specs search
        document.getElementById('specSearch').addEventListener('input', (e) => {{
            specsGridApi.setGridOption('quickFilterText', e.target.value);
        }});

        // Theme toggle
        function toggleTheme() {{
            const body = document.body;
            const isDark = body.dataset.theme === 'dark';
            body.dataset.theme = isDark ? '' : 'dark';

            const grids = document.querySelectorAll('.grid-container');
            grids.forEach(grid => {{
                grid.classList.toggle('ag-theme-alpine', isDark);
                grid.classList.toggle('ag-theme-alpine-dark', !isDark);
            }});

            document.getElementById('themeIcon').textContent = isDark ? '🌙' : '☀️';
            document.querySelector('.theme-toggle').innerHTML = isDark
                ? '<span id="themeIcon">🌙</span> Dark Mode'
                : '<span id="themeIcon">☀️</span> Light Mode';
        }}
    </script>
</body>
</html>
"""
    return html


def main():
    """Main entry point."""
    print("Scanning OpenSpec specifications...")
    specs = scan_specs()
    print(f"Found {len(specs)} specifications")

    total_reqs = sum(s.requirement_count for s in specs)
    total_scenarios = sum(s.scenario_count for s in specs)
    print(f"Total: {total_reqs} requirements, {total_scenarios} scenarios")

    print("Generating HTML...")
    html = generate_html(specs)

    print(f"Writing to {OUTPUT_FILE}...")
    OUTPUT_FILE.write_text(html)

    print(f"Done! Open {OUTPUT_FILE} in a browser.")


if __name__ == "__main__":
    main()
