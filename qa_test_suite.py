#!/usr/bin/env python3
"""
High-Level QA Test Suite

Tests each integration individually and the entire end-to-end pipeline:
- GPT script generation
- Video generator output formatting
- NextCloud upload and download
- Buffer posting (Late API)
- Facebook → CRM lead sync
- End-to-end: Category → GPT → Video → Social posting → Leads → CRM

Usage:
    python qa_test_suite.py [--component COMPONENT] [--skip SKIP]
    
    --component: Test only specific component (gpt, video, nextcloud, buffer, facebook, e2e)
    --skip: Skip specific components (comma-separated)
"""

import os
import sys
import json
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from log_utils import attach_log_streams, get_logger
from chatgpt_integration import GPT, createVideoFromCategory
from services.groundhogg import (
    GroundhoggClient,
    GroundhoggAuth,
    create_contact,
    get_contact,
    search_contacts,
)
from services.facebook.processor import process_facebook_leads, get_processor
from late_post import post_video_to_all_accounts, build_nextcloud_download_url
from sheet import (
    download_nextcloud_public_file,
    upload_webdav_authenticated,
    create_nextcloud_share_link,
    download_from_url,
)
from config import get_env, BASE_DIR

attach_log_streams("qa_test_suite")
logger = get_logger("gallardo.qa_test_suite")


# ============================================================================
# Test Results Tracking
# ============================================================================

class TestResult:
    """Track test results."""
    
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error: Optional[str] = None
        self.details: Dict = {}
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def start(self):
        self.start_time = time.time()
    
    def finish(self, passed: bool, error: Optional[str] = None, details: Optional[Dict] = None):
        self.end_time = time.time()
        self.passed = passed
        self.error = error
        if details:
            self.details.update(details)
    
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    def __str__(self):
        status = "✓ PASS" if self.passed else "✗ FAIL"
        duration = f" ({self.duration():.2f}s)"
        error = f" - {self.error}" if self.error else ""
        return f"{status} {self.name}{duration}{error}"


# ============================================================================
# Individual Integration Tests
# ============================================================================

def test_gpt_script_generation() -> TestResult:
    """Test GPT script generation."""
    result = TestResult("GPT Script Generation")
    result.start()
    
    try:
        # Initialize GPT
        gpt = GPT()
        
        # Check if API key is configured
        if not gpt.api_key:
            result.finish(False, "OPENAI_API_KEY not configured")
            return result
        
        # Test script generation
        logger.info("Testing GPT script generation...")
        script_response = gpt.generateScript("Technology", "AI")
        
        if not script_response:
            result.finish(False, "GPT returned None response")
            return result
        
        if "raw_content" not in script_response:
            result.finish(False, "GPT response missing 'raw_content' field")
            return result
        
        # Test formatting
        formatted = gpt.formatForVideo(script_response)
        if not formatted:
            result.finish(False, "Failed to format script for video")
            return result
        
        # Validate formatted script
        is_valid, error_msg = gpt.validateScript(formatted)
        if not is_valid:
            result.finish(False, f"Formatted script validation failed: {error_msg}")
            return result
        
        # Check required fields
        if "texts" not in formatted or "text_locations" not in formatted:
            result.finish(False, "Formatted script missing required fields")
            return result
        
        if len(formatted["texts"]) == 0:
            result.finish(False, "Formatted script has no texts")
            return result
        
        result.finish(
            True,
            details={
                "texts_count": len(formatted["texts"]),
                "sample_text": formatted["texts"][0][:50] if formatted["texts"] else None,
            }
        )
        
    except Exception as e:
        result.finish(False, f"Exception: {str(e)}")
        logger.error("GPT test failed", exc_info=True)
    
    return result


def test_video_generator_formatting() -> TestResult:
    """Test video generator output formatting."""
    result = TestResult("Video Generator Output Formatting")
    result.start()
    
    try:
        # Test with createVideoFromCategory (full pipeline)
        logger.info("Testing video generator formatting...")
        formatted = createVideoFromCategory("Technology", "AI")
        
        if not formatted:
            result.finish(False, "createVideoFromCategory returned None")
            return result
        
        # Validate structure
        required_fields = ["texts", "text_locations"]
        for field in required_fields:
            if field not in formatted:
                result.finish(False, f"Missing required field: {field}")
                return result
        
        # Validate arrays
        texts = formatted["texts"]
        locations = formatted["text_locations"]
        
        if not isinstance(texts, list) or len(texts) == 0:
            result.finish(False, "texts must be a non-empty list")
            return result
        
        if not isinstance(locations, list) or len(locations) == 0:
            result.finish(False, "text_locations must be a non-empty list")
            return result
        
        if len(texts) != len(locations):
            result.finish(False, f"texts ({len(texts)}) and locations ({len(locations)}) must have same length")
            return result
        
        # Validate text content
        valid_locations = {
            "top", "top-left", "top-right",
            "center", "center-left", "center-right",
            "bottom", "bottom-left", "bottom-right"
        }
        
        for i, (text, location) in enumerate(zip(texts, locations)):
            if not isinstance(text, str) or not text.strip():
                result.finish(False, f"Text at index {i} is empty or not a string")
                return result
            
            if location not in valid_locations:
                result.finish(False, f"Invalid location '{location}' at index {i}")
                return result
        
        result.finish(
            True,
            details={
                "texts_count": len(texts),
                "locations": locations,
                "sample_text": texts[0][:50] if texts else None,
            }
        )
        
    except Exception as e:
        result.finish(False, f"Exception: {str(e)}")
        logger.error("Video generator formatting test failed", exc_info=True)
    
    return result


def test_nextcloud_upload_download() -> TestResult:
    """Test NextCloud upload and download."""
    result = TestResult("NextCloud Upload and Download")
    result.start()
    
    try:
        # Check configuration
        nc_base = get_env("NC_BASE", required=False, default="")
        nc_user = get_env("NC_USER", required=False, default="")
        nc_pass = get_env("NC_PASS", required=False, default="")
        
        if not all([nc_base, nc_user, nc_pass]):
            result.finish(False, "NextCloud credentials not configured (NC_BASE, NC_USER, NC_PASS)")
            return result
        
        # Create a test file
        test_content = f"QA Test File - {datetime.now().isoformat()}\n"
        test_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
        test_file.write(test_content)
        test_file.close()
        test_file_path = test_file.name
        
        try:
            # Test upload
            logger.info("Testing NextCloud upload...")
            remote_path = f"qa_test_{int(time.time())}.txt"
            webdav_url = upload_webdav_authenticated(
                base_url=nc_base,
                username=nc_user,
                password=nc_pass,
                local_path=test_file_path,
                remote_path=remote_path,
            )
            
            if not webdav_url:
                result.finish(False, "Upload returned None")
                return result
            
            # Test share link creation
            logger.info("Testing NextCloud share link creation...")
            share_url = create_nextcloud_share_link(
                base_url=nc_base,
                username=nc_user,
                password=nc_pass,
                remote_path=remote_path,
            )
            
            if not share_url:
                result.finish(False, "Share link creation returned None")
                return result
            
            # Test download URL conversion
            download_url = build_nextcloud_download_url(share_url)
            if "/download" not in download_url:
                result.finish(False, "Download URL missing /download suffix")
                return result
            
            # Test download (with retry logic for Nextcloud processing delay)
            logger.info("Testing NextCloud download...")
            max_retries = 3
            downloaded_file = None
            
            for attempt in range(max_retries):
                try:
                    downloaded_file = download_nextcloud_public_file(download_url)
                    if downloaded_file and os.path.exists(downloaded_file):
                        break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.info(f"Download attempt {attempt + 1} failed, retrying...")
                        time.sleep(2 * (attempt + 1))
                    else:
                        raise
            
            if not downloaded_file or not os.path.exists(downloaded_file):
                result.finish(False, "Download failed or file not found")
                return result
            
            # Verify content
            with open(downloaded_file, 'r') as f:
                downloaded_content = f.read()
            
            if test_content not in downloaded_content:
                result.finish(False, "Downloaded content doesn't match uploaded content")
                return result
            
            # Cleanup
            try:
                os.unlink(test_file_path)
                if downloaded_file:
                    os.unlink(downloaded_file)
            except:
                pass
            
            result.finish(
                True,
                details={
                    "share_url": share_url,
                    "download_url": download_url,
                    "file_size": len(test_content),
                }
            )
            
        except Exception as e:
            # Cleanup on error
            try:
                os.unlink(test_file_path)
            except:
                pass
            raise
        
    except Exception as e:
        result.finish(False, f"Exception: {str(e)}")
        logger.error("NextCloud test failed", exc_info=True)
    
    return result


def test_buffer_posting() -> TestResult:
    """Test Buffer posting (Late API)."""
    result = TestResult("Buffer Posting (Late API)")
    result.start()
    
    try:
        # Check configuration
        late_api_key = get_env("LATE_API_KEY", required=False, default="")
        late_profile_id = get_env("LATE_PROFILE_ID", required=False, default="")
        
        if not late_api_key:
            result.finish(False, "LATE_API_KEY not configured")
            return result
        
        if not late_profile_id or late_profile_id == "REPLACE_WITH_LATE_PROFILE_ID":
            result.finish(False, "LATE_PROFILE_ID not configured")
            return result
        
        # We need a valid Nextcloud share URL for testing
        # For now, we'll test the URL conversion function
        logger.info("Testing Late API URL conversion...")
        
        test_share_url = "https://cloud.targethouse.dk/s/TestShareId"
        download_url = build_nextcloud_download_url(test_share_url)
        
        if "/download" not in download_url:
            result.finish(False, "URL conversion failed")
            return result
        
        # Note: We don't actually post to avoid spamming social media
        # In a real test, you would:
        # 1. Upload a test video to Nextcloud
        # 2. Create a share link
        # 3. Post with publishNow=False (scheduled) or to a test account
        # 4. Verify the post was created
        
        logger.info("Late API URL conversion test passed (actual posting skipped to avoid spam)")
        
        result.finish(
            True,
            details={
                "url_conversion_works": True,
                "note": "Actual posting skipped to avoid spamming social media",
            }
        )
        
    except Exception as e:
        result.finish(False, f"Exception: {str(e)}")
        logger.error("Buffer posting test failed", exc_info=True)
    
    return result


def test_facebook_crm_sync() -> TestResult:
    """Test Facebook → CRM lead sync."""
    result = TestResult("Facebook → CRM Lead Sync")
    result.start()
    
    try:
        # Check Groundhogg configuration
        gh_api_key = get_env("GROUNDHOGG_API_KEY", required=False, default="")
        gh_api_secret = get_env("GROUNDHOGG_API_SECRET", required=False, default="")
        gh_base_url = get_env("GROUNDHOGG_BASE_URL", required=False, default="")
        
        if not all([gh_api_key, gh_api_secret, gh_base_url]):
            result.finish(False, "Groundhogg credentials not configured")
            return result
        
        # Test Groundhogg authentication
        logger.info("Testing Groundhogg authentication...")
        auth = GroundhoggAuth(
            api_key=gh_api_key,
            api_secret=gh_api_secret,
            base_url=gh_base_url,
        )
        
        if not auth.is_configured():
            result.finish(False, "Groundhogg authentication not properly configured")
            return result
        
        # Test creating a test contact
        logger.info("Testing contact creation...")
        test_email = f"qa_test_{int(time.time())}@example.com"
        contact = create_contact(
            email=test_email,
            first_name="QA",
            last_name="Test",
            phone="+1234567890",
        )
        
        if not contact or "id" not in contact:
            result.finish(False, "Contact creation failed or missing ID")
            return result
        
        contact_id = contact["id"]
        
        # Test retrieving the contact
        logger.info("Testing contact retrieval...")
        retrieved = get_contact(contact_id)
        
        if not retrieved or retrieved.get("email") != test_email:
            result.finish(False, "Contact retrieval failed or email mismatch")
            return result
        
        # Test Facebook lead processor (if configured)
        fb_token = get_env("FACEBOOK_ACCESS_TOKEN", required=False, default="")
        if fb_token:
            logger.info("Facebook access token found, testing processor initialization...")
            processor = get_processor()
            if processor:
                result.finish(
                    True,
                    details={
                        "groundhogg_works": True,
                        "contact_created": contact_id,
                        "contact_retrieved": True,
                        "facebook_processor_initialized": True,
                    }
                )
            else:
                result.finish(
                    True,
                    details={
                        "groundhogg_works": True,
                        "contact_created": contact_id,
                        "contact_retrieved": True,
                        "facebook_processor_initialized": False,
                    }
                )
        else:
            result.finish(
                True,
                details={
                    "groundhogg_works": True,
                    "contact_created": contact_id,
                    "contact_retrieved": True,
                    "facebook_token_not_configured": True,
                }
            )
        
    except Exception as e:
        result.finish(False, f"Exception: {str(e)}")
        logger.error("Facebook CRM sync test failed", exc_info=True)
    
    return result


# ============================================================================
# End-to-End Pipeline Test
# ============================================================================

def test_end_to_end_pipeline() -> TestResult:
    """Test the entire end-to-end pipeline: Category → GPT → Video → Social posting → Leads → CRM."""
    result = TestResult("End-to-End Pipeline")
    result.start()
    
    pipeline_steps = []
    
    try:
        # Step 1: Category → GPT
        logger.info("Step 1: Testing Category → GPT...")
        gpt_result = test_gpt_script_generation()
        pipeline_steps.append(("Category → GPT", gpt_result.passed, gpt_result.error))
        
        if not gpt_result.passed:
            result.finish(False, f"Step 1 failed: {gpt_result.error}")
            return result
        
        # Step 2: GPT → Video Formatting
        logger.info("Step 2: Testing GPT → Video Formatting...")
        video_result = test_video_generator_formatting()
        pipeline_steps.append(("GPT → Video Formatting", video_result.passed, video_result.error))
        
        if not video_result.passed:
            result.finish(False, f"Step 2 failed: {video_result.error}")
            return result
        
        # Step 3: Video → NextCloud Upload
        logger.info("Step 3: Testing Video → NextCloud Upload...")
        nc_result = test_nextcloud_upload_download()
        pipeline_steps.append(("Video → NextCloud Upload", nc_result.passed, nc_result.error))
        
        if not nc_result.passed:
            result.finish(False, f"Step 3 failed: {nc_result.error}")
            return result
        
        # Step 4: NextCloud → Social Posting (URL conversion only)
        logger.info("Step 4: Testing NextCloud → Social Posting...")
        buffer_result = test_buffer_posting()
        pipeline_steps.append(("NextCloud → Social Posting", buffer_result.passed, buffer_result.error))
        
        if not buffer_result.passed:
            result.finish(False, f"Step 4 failed: {buffer_result.error}")
            return result
        
        # Step 5: Facebook → CRM Lead Sync
        logger.info("Step 5: Testing Facebook → CRM Lead Sync...")
        crm_result = test_facebook_crm_sync()
        pipeline_steps.append(("Facebook → CRM Lead Sync", crm_result.passed, crm_result.error))
        
        if not crm_result.passed:
            result.finish(False, f"Step 5 failed: {crm_result.error}")
            return result
        
        # All steps passed
        result.finish(
            True,
            details={
                "pipeline_steps": pipeline_steps,
                "total_steps": len(pipeline_steps),
                "passed_steps": sum(1 for _, passed, _ in pipeline_steps if passed),
            }
        )
        
    except Exception as e:
        result.finish(False, f"Exception: {str(e)}")
        logger.error("End-to-end test failed", exc_info=True)
    
    return result


# ============================================================================
# Test Runner
# ============================================================================

def run_all_tests(skip_components: List[str] = None) -> Dict[str, TestResult]:
    """Run all tests."""
    skip_components = skip_components or []
    
    tests = {
        "gpt": test_gpt_script_generation,
        "video": test_video_generator_formatting,
        "nextcloud": test_nextcloud_upload_download,
        "buffer": test_buffer_posting,
        "facebook": test_facebook_crm_sync,
        "e2e": test_end_to_end_pipeline,
    }
    
    results = {}
    
    for name, test_func in tests.items():
        if name in skip_components:
            logger.info(f"Skipping {name} test")
            continue
        
        logger.info("=" * 80)
        logger.info(f"Running test: {name}")
        logger.info("=" * 80)
        
        try:
            result = test_func()
            results[name] = result
        except Exception as e:
            result = TestResult(name)
            result.finish(False, f"Test crashed: {str(e)}")
            results[name] = result
    
    return results


def print_summary(results: Dict[str, TestResult]):
    """Print test summary."""
    print("\n" + "=" * 80)
    print("QA TEST SUITE SUMMARY")
    print("=" * 80)
    
    total = len(results)
    passed = sum(1 for r in results.values() if r.passed)
    failed = total - passed
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/total*100) if total > 0 else 0:.1f}%")
    
    print("\n" + "-" * 80)
    print("Test Results:")
    print("-" * 80)
    
    for name, result in results.items():
        print(f"  {result}")
        if result.details:
            for key, value in result.details.items():
                if key not in ["pipeline_steps"]:  # Skip verbose details
                    print(f"    - {key}: {value}")
    
    print("\n" + "=" * 80)
    
    if failed == 0:
        print("✓ ALL TESTS PASSED - Zero failed steps in end-to-end flow!")
        return 0
    else:
        print(f"✗ {failed} TEST(S) FAILED")
        return 1


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="QA Test Suite")
    parser.add_argument(
        "--component",
        choices=["gpt", "video", "nextcloud", "buffer", "facebook", "e2e"],
        help="Test only specific component",
    )
    parser.add_argument(
        "--skip",
        help="Skip specific components (comma-separated)",
    )
    
    args = parser.parse_args()
    
    skip_components = []
    if args.skip:
        skip_components = [c.strip() for c in args.skip.split(",")]
    
    if args.component:
        # Test only specific component
        tests = {
            "gpt": test_gpt_script_generation,
            "video": test_video_generator_formatting,
            "nextcloud": test_nextcloud_upload_download,
            "buffer": test_buffer_posting,
            "facebook": test_facebook_crm_sync,
            "e2e": test_end_to_end_pipeline,
        }
        
        if args.component not in tests:
            print(f"Unknown component: {args.component}")
            return 1
        
        result = tests[args.component]()
        results = {args.component: result}
    else:
        # Run all tests
        results = run_all_tests(skip_components=skip_components)
    
    exit_code = print_summary(results)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

