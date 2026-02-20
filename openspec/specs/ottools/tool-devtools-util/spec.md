# tool-devtools-util Specification

## Purpose
TBD - created by archiving change add-devtools-util. Update Purpose after archive.
## Requirements
### Requirement: chrome_devtools_util Pack Declaration

The system SHALL provide a `chrome_devtools_util` extension tool pack at `.onetool/tools/chrome_devtools_util.py`.

#### Scenario: Pack discovery
- **GIVEN** the `chrome_devtools_util.py` file exists in `.onetool/tools/`
- **WHEN** `ot.tools(pattern="chrome_devtools")` is called
- **THEN** it lists `chrome_devtools_util` with its 5 functions

### Requirement: Annotation Injection

The `chrome_devtools_util` pack SHALL provide an `inject_annotations()` function for one-time page setup.

#### Scenario: Successful injection
- **GIVEN** a browser page is open via DevTools MCP
- **WHEN** `chrome_devtools_util.inject_annotations()` is called
- **THEN** the inject.js script is loaded into the page
- **AND** the result includes `success: True`, `ready: True`, and `version`

#### Scenario: Already injected
- **GIVEN** inject.js is already loaded on the page
- **WHEN** `chrome_devtools_util.inject_annotations()` is called again
- **THEN** it returns success without re-injecting (idempotent)

### Requirement: Element Highlighting

The `chrome_devtools_util` pack SHALL provide a `highlight_element()` function for programmatic annotation.

#### Scenario: Highlight single element
- **GIVEN** inject.js is loaded on the page
- **WHEN** `chrome_devtools_util.highlight_element(selector="button.submit", label="Click here")` is called
- **THEN** the element is visually highlighted with an orange border and label
- **AND** the result includes `success`, `count`, and `ids`

#### Scenario: Highlight with colour
- **GIVEN** inject.js is loaded on the page
- **WHEN** `chrome_devtools_util.highlight_element(selector=".error", label="Error", color="red")` is called
- **THEN** the element is highlighted using the red colour scheme

#### Scenario: No matching elements
- **GIVEN** inject.js is loaded on the page
- **WHEN** `chrome_devtools_util.highlight_element(selector=".nonexistent", label="Test")` is called
- **THEN** the result includes `success: False` and `count: 0`

### Requirement: Annotation Scanning

The `chrome_devtools_util` pack SHALL provide a `scan_annotations()` function to read all annotations.

#### Scenario: Scan existing annotations
- **GIVEN** elements have been annotated (programmatically or by user via Ctrl+I with custom labels)
- **WHEN** `chrome_devtools_util.scan_annotations()` is called
- **THEN** it returns a list of dicts with `id`, `label`, `selector`, `content`, `tagName`, and `color`

#### Scenario: No annotations
- **GIVEN** no elements are annotated
- **WHEN** `chrome_devtools_util.scan_annotations()` is called
- **THEN** it returns an empty list

### Requirement: Annotation Clearing

The `chrome_devtools_util` pack SHALL provide a `clear_annotations()` function to remove all annotations.

#### Scenario: Clear all annotations
- **GIVEN** multiple elements are annotated
- **WHEN** `chrome_devtools_util.clear_annotations()` is called
- **THEN** all `x-inspect` and `x-inspect-color` attributes are removed
- **AND** all visual highlights are cleared
- **AND** the result includes `success: True` and the count of cleared annotations

### Requirement: Guided User Workflow

The `chrome_devtools_util` pack SHALL provide a `guide_user()` function for sequential element highlighting.

#### Scenario: Sequential step highlighting
- **GIVEN** inject.js is loaded on the page
- **WHEN** `chrome_devtools_util.guide_user(task="Fill form", steps=[{"selector": "input[name='name']", "label": "Enter name"}, {"selector": "button[type='submit']", "label": "Submit"}])` is called
- **THEN** each step's element is highlighted in sequence
- **AND** each step uses the specified colour (defaulting to orange)

### Requirement: Server Independence

The `chrome_devtools_util` pack SHALL only work with the `chrome-devtools` MCP server.

#### Scenario: chrome-devtools server required
- **GIVEN** the `chrome-devtools` MCP server is not connected
- **WHEN** any chrome_devtools_util function is called
- **THEN** it returns an error indicating the chrome-devtools server is unavailable
- **AND** it lists available servers in the error message

#### Scenario: No fallback to Playwright
- **GIVEN** the `chrome-devtools` MCP server is unavailable but Playwright is connected
- **WHEN** any chrome_devtools_util function is called
- **THEN** it does NOT fall back to Playwright automatically
- **AND** users must use `playwright_util` pack for Playwright servers

