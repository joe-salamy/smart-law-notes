"""
Google Docs uploader for LLM-generated markdown notes.
Uploads formatted markdown content to Google Docs using markgdoc.
"""

import re
import pickle
import subprocess
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from drive_downloader import (
    get_drive_service,
    find_folder_by_name,
    SCOPES,
    TOKEN_FILE,
    CREDENTIALS_FILE,
)
from config import (
    CLASSES,
    LLM_BASE,
    LECTURE_OUTPUT,
    READING_OUTPUT,
    DRIVE_CLASSES_FOLDER_ID,
)
from logger_config import get_logger

# Import markgdoc for markdown to Google Docs conversion
import markgdoc

logger = get_logger(__name__)


def get_credentials():
    """
    Get Google API credentials (shared between Drive and Docs).
    Reuses the same token and authentication flow as drive_downloader.
    """
    creds = None

    # Load existing token if available
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    # Refresh or get new credentials if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.debug("Refreshing expired credentials")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_FILE}. "
                    "Please download it from Google Cloud Console."
                )
            logger.info("Starting OAuth flow - browser will open for authentication")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=8080)

        # Save credentials for next run
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
            logger.debug(f"Credentials saved to {TOKEN_FILE}")

    return creds


def get_docs_service():
    """
    Get a Google Docs service object using existing credentials.
    Reuses the authentication from drive_downloader.
    """
    creds = get_credentials()
    docs_service = build("docs", "v1", credentials=creds)
    return docs_service


def prepend_filename_to_h3(markdown_content: str, filename: str) -> str:
    """
    Prepend the filename to the first h3 element in the markdown content.

    Args:
        markdown_content: The markdown content to modify
        filename: The filename (without extension) to prepend

    Returns:
        Modified markdown content with filename prepended to first h3
    """
    # Pattern to match the first h3 header (### followed by text)
    h3_pattern = r"^(### )(.+)$"

    # Find the first h3 and prepend the filename
    lines = markdown_content.split("\n")
    modified_lines = []
    h3_found = False

    for line in lines:
        if not h3_found and re.match(h3_pattern, line):
            # Prepend filename to the h3
            match = re.match(h3_pattern, line)
            modified_line = f"### {filename}: {match.group(2)}"
            modified_lines.append(modified_line)
            h3_found = True
            logger.debug(f"Prepended filename to h3: {modified_line}")
        else:
            modified_lines.append(line)

    if not h3_found:
        logger.warning(f"No h3 element found in markdown content for {filename}")

    return "\n".join(modified_lines)


def find_notes_document(service, class_name: str, notes_type: str) -> dict | None:
    """
    Find a Google Doc in the class folder that ends with 'Lecture Notes' or 'Reading Notes'.

    Args:
        service: Google Drive service object
        class_name: Name of the class folder to search in
        notes_type: Either 'lecture' or 'reading'

    Returns:
        File metadata dict with 'id' and 'name', or None if not found
    """
    # Find the class folder within the Classes folder
    class_folder_id = find_folder_by_name(service, DRIVE_CLASSES_FOLDER_ID, class_name)

    if not class_folder_id:
        logger.warning(f"No folder found in Drive Classes for class: {class_name}")
        return None

    logger.debug(f"Found class folder for {class_name}: {class_folder_id}")

    # Determine the suffix to search for
    suffix = "Lecture Notes" if notes_type == "lecture" else "Reading Notes"

    # Search for a document ending with the suffix
    query = (
        f"'{class_folder_id}' in parents and "
        f"mimeType = 'application/vnd.google-apps.document' and "
        f"name contains '{suffix}' and "
        f"trashed = false"
    )

    results = (
        service.files()
        .list(q=query, spaces="drive", fields="files(id, name)")
        .execute()
    )

    files = results.get("files", [])

    # Filter to find documents that END with the suffix
    for file in files:
        if file["name"].endswith(suffix):
            logger.info(f"Found {notes_type} notes document: {file['name']}")
            return file

    logger.warning(f"No document ending with '{suffix}' found for class: {class_name}")
    return None


def get_document_end_index(docs_service, document_id: str) -> int:
    """
    Get the end index of a Google Doc (where new content should be appended).

    Args:
        docs_service: Google Docs service object
        document_id: ID of the document

    Returns:
        The end index of the document body
    """
    doc = docs_service.documents().get(documentId=document_id).execute()

    # The body content ends at the endIndex of the last element
    body = doc.get("body", {})
    content = body.get("content", [])

    if content:
        # Get the endIndex of the last element
        last_element = content[-1]
        end_index = last_element.get("endIndex", 1)
        # We need to insert before the final newline, so subtract 1
        return end_index - 1

    return 1  # Default to beginning if empty


def append_markdown_to_doc(
    docs_service, document_id: str, markdown_content: str, debug: bool = False
) -> bool:
    """
    Append formatted markdown content to the end of a Google Doc using markgdoc.

    Args:
        docs_service: Google Docs service object
        document_id: ID of the target document
        markdown_content: Markdown content to append
        debug: Whether to enable debug mode in markgdoc

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get the current end index of the document
        end_index = get_document_end_index(docs_service, document_id)
        logger.debug(f"Document end index: {end_index}")

        # Add a newline before the new content for separation
        if end_index > 1:
            # Insert a newline separator first
            separator_request = [
                {"insertText": {"location": {"index": end_index}, "text": "\n\n"}}
            ]
            docs_service.documents().batchUpdate(
                documentId=document_id, body={"requests": separator_request}
            ).execute()
            end_index += 2  # Account for the added newlines

        # Use markgdoc to convert markdown and get the requests
        # markgdoc.convert_to_google_docs creates a new doc, so we need to use
        # the lower-level functions to build requests and apply them to existing doc

        # Parse the markdown and generate requests
        requests = _generate_markdown_requests(markdown_content, end_index, debug)

        if requests:
            # Apply the requests to the document
            docs_service.documents().batchUpdate(
                documentId=document_id, body={"requests": requests}
            ).execute()
            logger.info(f"Successfully appended markdown content to document")
            return True
        else:
            logger.warning("No requests generated from markdown content")
            return False

    except Exception as e:
        logger.error(f"Error appending markdown to doc: {e}", exc_info=True)
        return False


def _generate_markdown_requests(
    markdown_content: str, start_index: int, debug: bool = False
) -> list:
    """
    Generate Google Docs API requests from markdown content using markgdoc functions.

    Args:
        markdown_content: The markdown content to convert
        start_index: The index at which to start inserting content
        debug: Whether to enable debug mode

    Returns:
        List of Google Docs API requests
    """

    # Apply Prettier formatting to standardize markdown
    markdown_content = _format_with_prettier(markdown_content)

    requests = []
    current_index = start_index

    lines = markdown_content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip empty lines but track them for spacing
        if not line.strip():
            # Add a newline for empty lines
            requests.append(
                {"insertText": {"location": {"index": current_index}, "text": "\n"}}
            )
            current_index += 1
            i += 1
            continue

        # Check for headers (h1-h6)
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if header_match:
            level = len(header_match.group(1))
            text = header_match.group(2)
            header_requests = markgdoc.get_header_request(
                text, level, current_index, debug
            )
            if isinstance(header_requests, list):
                requests.extend(header_requests)
            else:
                requests.append(header_requests)
            current_index += len(text) + 1  # +1 for newline
            i += 1
            continue

        # Check for unordered list items
        ul_match = re.match(r"^[\*\-\+]\s+(.+)$", line)
        if ul_match:
            text = ul_match.group(1)
            ul_requests = markgdoc.get_unordered_list_request(
                text, current_index, debug
            )
            if isinstance(ul_requests, list):
                requests.extend(ul_requests)
            else:
                requests.append(ul_requests)
            current_index += len(text) + 1
            i += 1
            continue

        # Check for ordered list items
        ol_match = re.match(r"^(\d+)\.\s+(.+)$", line)
        if ol_match:
            text = ol_match.group(2)
            ol_requests = markgdoc.get_ordered_list_request(text, current_index, debug)
            if isinstance(ol_requests, list):
                requests.extend(ol_requests)
            else:
                requests.append(ol_requests)
            current_index += len(text) + 1
            i += 1
            continue

        # Check for horizontal rule
        if re.match(r"^[\-\*_]{3,}$", line.strip()):
            hr_requests = markgdoc.get_horizontal_line_request(current_index, debug)
            if isinstance(hr_requests, list):
                requests.extend(hr_requests)
            else:
                requests.append(hr_requests)
            current_index += 1
            i += 1
            continue

        # Default: treat as paragraph
        text = line
        para_requests = markgdoc.get_paragraph_request(text, current_index, debug)
        if isinstance(para_requests, list):
            requests.extend(para_requests)
        else:
            requests.append(para_requests)
        current_index += len(text) + 1
        i += 1

    return requests


def _format_with_prettier(markdown_content: str) -> str:
    """
    Format markdown content using Prettier CLI.

    Args:
        markdown_content: The markdown content to format

    Returns:
        Formatted markdown content, or original content if Prettier fails
    """
    # On Windows, npm global commands need .cmd extension
    import platform

    prettier_cmd = "prettier.cmd" if platform.system() == "Windows" else "prettier"

    try:
        # Run Prettier with markdown parser via subprocess
        result = subprocess.run(
            [prettier_cmd, "--parser", "markdown"],
            input=markdown_content,
            text=True,
            capture_output=True,
            timeout=10,
        )

        if result.returncode == 0:
            logger.debug("Successfully formatted markdown with Prettier")
            return result.stdout
        else:
            logger.warning(
                f"Prettier formatting failed (exit code {result.returncode}): {result.stderr}"
            )
            return markdown_content

    except FileNotFoundError:
        logger.warning(
            "Prettier not found. Install with: npm install -g prettier. "
            "Continuing with unformatted markdown."
        )
        return markdown_content
    except subprocess.TimeoutExpired:
        logger.warning("Prettier formatting timed out. Using original markdown.")
        return markdown_content
    except Exception as e:
        logger.warning(f"Error running Prettier: {e}. Using original markdown.")
        return markdown_content


def process_markdown_file(
    markdown_path: Path, class_name: str, notes_type: str, drive_service, docs_service
) -> bool:
    """
    Process a single markdown file and upload to the appropriate Google Doc.

    Args:
        markdown_path: Path to the markdown file
        class_name: Name of the class
        notes_type: Either 'lecture' or 'reading'
        drive_service: Google Drive service object
        docs_service: Google Docs service object

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Processing markdown file: {markdown_path.name}")

    # Read the markdown file
    try:
        with open(markdown_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()
    except Exception as e:
        logger.error(f"Error reading markdown file {markdown_path}: {e}")
        return False

    # Get filename without extension
    filename = markdown_path.stem

    # Prepend filename to the first h3
    modified_content = prepend_filename_to_h3(markdown_content, filename)

    # Find the target document
    target_doc = find_notes_document(drive_service, class_name, notes_type)

    if not target_doc:
        logger.error(f"Could not find {notes_type} notes document for {class_name}")
        return False

    # Append the markdown content to the document
    success = append_markdown_to_doc(docs_service, target_doc["id"], modified_content)

    if success:
        logger.info(f"✓ Uploaded {markdown_path.name} to {target_doc['name']}")
    else:
        logger.error(f"✗ Failed to upload {markdown_path.name}")

    return success


def process_class_outputs(class_folder: Path, drive_service, docs_service) -> dict:
    """
    Process all LLM-generated markdown files for a class and upload to Google Docs.

    Args:
        class_folder: Path to the class folder
        drive_service: Google Drive service object
        docs_service: Google Docs service object

    Returns:
        Dictionary with counts of successful uploads for lectures and readings
    """
    class_name = class_folder.name
    logger.info(f"Processing outputs for class: {class_name}")

    results = {"lecture": 0, "reading": 0}

    # Process lecture outputs
    lecture_output_dir = class_folder / LLM_BASE / LECTURE_OUTPUT
    if lecture_output_dir.exists():
        md_files = list(lecture_output_dir.glob("*.md"))
        logger.info(f"Found {len(md_files)} lecture markdown file(s)")

        for md_file in md_files:
            if process_markdown_file(
                md_file, class_name, "lecture", drive_service, docs_service
            ):
                results["lecture"] += 1
    else:
        logger.debug(f"No lecture output directory found: {lecture_output_dir}")

    # Process reading outputs
    reading_output_dir = class_folder / LLM_BASE / READING_OUTPUT
    if reading_output_dir.exists():
        md_files = list(reading_output_dir.glob("*.md"))
        logger.info(f"Found {len(md_files)} reading markdown file(s)")

        for md_file in md_files:
            if process_markdown_file(
                md_file, class_name, "reading", drive_service, docs_service
            ):
                results["reading"] += 1
    else:
        logger.debug(f"No reading output directory found: {reading_output_dir}")

    return results


def upload_to_docs(classes: list[Path]) -> dict[str, dict]:
    """
    Upload all LLM-generated markdown files to Google Docs for all classes.

    Args:
        classes: List of class folder paths

    Returns:
        Dictionary mapping class names to upload results
    """
    logger.info("Initializing Google services for Docs upload...")

    try:
        drive_service = get_drive_service()
        docs_service = get_docs_service()
        logger.info("✓ Connected to Google Drive and Docs")
    except Exception as e:
        logger.error(f"Failed to connect to Google services: {e}")
        raise

    results = {}

    for class_folder in classes:
        class_name = class_folder.name
        try:
            class_results = process_class_outputs(
                class_folder, drive_service, docs_service
            )
            results[class_name] = class_results

            total = class_results["lecture"] + class_results["reading"]
            logger.info(f"✓ {class_name}: Uploaded {total} file(s)")
            logger.info("─" * 70)
        except Exception as e:
            logger.error(f"Error processing {class_name}: {e}", exc_info=True)
            results[class_name] = {"lecture": 0, "reading": 0, "error": str(e)}

    return results
