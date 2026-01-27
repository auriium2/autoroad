import base64
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

MAX_SCREENSHOT_SIZE_BYTES = 5 * 1024 * 1024  # 5MB max for screenshots

GITHUB_REPO = "auriium2/autoroad"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/issues"


class BugReportRequest(BaseModel):
    title: str = "Bug Report"
    description: str
    screenshot: str | None = None  # Base64 encoded image
    debug_info: dict[str, Any]


class BugReportResponse(BaseModel):
    success: bool
    issue_url: str | None = None
    error: str | None = None


async def upload_screenshot_to_r2(screenshot_base64: str) -> str | None:
    """Upload a screenshot to Cloudflare R2 and return the public URL."""
    r2_account_id = os.environ.get("R2_ACCOUNT_ID")
    r2_access_key = os.environ.get("R2_ACCESS_KEY_ID")
    r2_secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
    r2_bucket = os.environ.get("R2_BUCKET_NAME", "autoroad-bugs")
    r2_public_url = os.environ.get("R2_PUBLIC_URL")

    if not all([r2_account_id, r2_access_key, r2_secret_key, r2_public_url]):
        print("R2 credentials not configured")
        return None

    try:
        # Extract the base64 data (remove data:image/png;base64, prefix if present)
        if "," in screenshot_base64:
            screenshot_base64 = screenshot_base64.split(",", 1)[1]

        image_bytes = base64.b64decode(screenshot_base64)

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"screenshots/{timestamp}-{unique_id}.png"

        # R2 S3-compatible endpoint
        endpoint = f"https://{r2_account_id}.r2.cloudflarestorage.com"
        url = f"{endpoint}/{r2_bucket}/{filename}"

        # AWS Signature Version 4 signing
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        region = "auto"
        service = "s3"

        # Create canonical request
        method = "PUT"
        canonical_uri = f"/{r2_bucket}/{filename}"
        canonical_querystring = ""
        content_hash = hashlib.sha256(image_bytes).hexdigest()

        headers_to_sign = {
            "host": f"{r2_account_id}.r2.cloudflarestorage.com",
            "x-amz-content-sha256": content_hash,
            "x-amz-date": amz_date,
            "content-type": "image/png",
        }

        signed_headers = ";".join(sorted(headers_to_sign.keys()))
        canonical_headers = "".join(
            f"{k}:{v}\n" for k, v in sorted(headers_to_sign.items())
        )

        canonical_request = "\n".join([
            method,
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            content_hash,
        ])

        # Create string to sign
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
        string_to_sign = "\n".join([
            algorithm,
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ])

        # Calculate signature
        def sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        k_date = sign(f"AWS4{r2_secret_key}".encode(), date_stamp)
        k_region = sign(k_date, region)
        k_service = sign(k_region, service)
        k_signing = sign(k_service, "aws4_request")
        signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

        # Create authorization header
        authorization = (
            f"{algorithm} "
            f"Credential={r2_access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.put(
                url,
                content=image_bytes,
                headers={
                    "Authorization": authorization,
                    "x-amz-content-sha256": content_hash,
                    "x-amz-date": amz_date,
                    "Content-Type": "image/png",
                },
            )

            if response.status_code in (200, 201):
                assert r2_public_url is not None
                public_url = f"{r2_public_url.rstrip('/')}/{filename}"
                return public_url
            else:
                print(f"Failed to upload to R2: {response.status_code} {response.text}")
                return None

    except Exception as e:
        print(f"Error uploading screenshot to R2: {e}")
        return None


def build_issue_body(description: str, screenshot_url: str | None, debug_info: dict[str, Any]) -> str:
    """Build the GitHub issue body with description, screenshot, and debug info."""
    parts = ["## Description", description, ""]

    if screenshot_url:
        parts.extend([
            "## Screenshot",
            f"![Screenshot]({screenshot_url})",
            ""
        ])

    # Debug info in collapsible section
    parts.extend([
        "<details>",
        "<summary>Debug Information (click to expand)</summary>",
        "",
        f"**App Version:** {debug_info.get('version', 'unknown')}",
        f"**Browser:** {debug_info.get('userAgent', 'unknown')}",
        f"**Timestamp:** {debug_info.get('timestamp', 'unknown')}",
        "",
    ])

    if debug_info.get('markers'):
        parts.extend([
            "**Markers:**",
            "```json",
            str(debug_info['markers']),
            "```",
            ""
        ])

    if debug_info.get('objectives'):
        parts.extend([
            "**Objectives:**",
            "```json",
            str(debug_info['objectives']),
            "```",
            ""
        ])

    if debug_info.get('requirements'):
        requirements = debug_info['requirements']
        requirement_sources = debug_info.get('requirementSources', {})
        requirements_with_sources = [
            f"{req} (beta)" if requirement_sources.get(req) == 'beta' else req
            for req in requirements
        ]
        parts.extend([
            "**Requirements:**",
            "```",
            ", ".join(requirements_with_sources),
            "```",
            ""
        ])

    if debug_info.get('lastOptimizationStatus') or debug_info.get('lastCostBreakdown'):
        parts.extend([
            "**Last Optimization:**",
            f"- Status: {debug_info.get('lastOptimizationStatus', 'N/A')}",
            f"- Cost Breakdown: {debug_info.get('lastCostBreakdown', 'N/A')}",
            ""
        ])

    if debug_info.get('consoleLogs'):
        logs = debug_info['consoleLogs']
        log_lines = []
        for log in logs[-50:]:  # Last 50 logs
            level = log.get('level', 'log').upper()
            ts = log.get('timestamp', '')[-12:-1] if log.get('timestamp') else ''
            msg = log.get('message', '')[:200]
            log_lines.append(f"[{ts}] {level}: {msg}")

        parts.extend([
            "**Console Logs (recent):**",
            "```",
            "\n".join(log_lines),
            "```",
            ""
        ])

    parts.extend(["</details>"])

    if debug_info.get('markersRoadData'):
        parts.extend([
            "",
            "<details>",
            "<summary>markers.road (click to expand)</summary>",
            "",
            "```json",
            json.dumps(debug_info['markersRoadData'], indent=2),
            "```",
            "",
            "</details>",
        ])

    if debug_info.get('optimizerRoadData'):
        parts.extend([
            "",
            "<details>",
            "<summary>generated.road (click to expand)</summary>",
            "",
            "```json",
            json.dumps(debug_info['optimizerRoadData'], indent=2),
            "```",
            "",
            "</details>",
        ])

    return "\n".join(parts)


@router.post("/bug-report", response_model=BugReportResponse)
@limiter.limit("5/minute")
async def create_bug_report(request: Request, body: BugReportRequest) -> BugReportResponse:
    """Create a GitHub issue for a bug report."""
    token = os.environ.get("GITHUB_BUG_REPORT_TOKEN")

    if not token:
        raise HTTPException(
            status_code=503,
            detail="Bug reporting is not configured. Please contact the maintainers directly."
        )

    screenshot_url = None
    if body.screenshot:
        # Validate screenshot size before processing
        screenshot_data = body.screenshot
        if "," in screenshot_data:
            screenshot_data = screenshot_data.split(",", 1)[1]
        # Base64 encoding adds ~33% overhead, so check encoded length
        estimated_size = len(screenshot_data) * 3 // 4
        if estimated_size > MAX_SCREENSHOT_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Screenshot too large. Maximum size is {MAX_SCREENSHOT_SIZE_BYTES // (1024 * 1024)}MB."
            )
        screenshot_url = await upload_screenshot_to_r2(body.screenshot)

    issue_body = build_issue_body(body.description, screenshot_url, body.debug_info)

    issue_data = {
        "title": body.title,
        "body": issue_body[:65000],  # GitHub body limit is ~65535 chars
        "labels": ["generated"],
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GITHUB_API_URL,
                json=issue_data,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )

            if response.status_code == 201:
                issue = response.json()
                return BugReportResponse(
                    success=True,
                    issue_url=issue.get("html_url"),
                )
            else:
                error_msg = response.json().get("message", "Unknown error")
                return BugReportResponse(
                    success=False,
                    error=f"GitHub API error: {error_msg}",
                )

    except httpx.TimeoutException:
        return BugReportResponse(
            success=False,
            error="Request timed out. Please try again.",
        )
    except Exception as e:
        return BugReportResponse(
            success=False,
            error=f"Failed to create issue: {str(e)}",
        )
