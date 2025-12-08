#!/usr/bin/env python3
"""
QA Test Suite - Working Components Only

Tests only the components that are currently configured and working:
- GPT script generation
- Video generator output formatting
- Buffer posting (URL conversion)

This test skips components that require additional credentials.
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from log_utils import attach_log_streams, get_logger
from chatgpt_integration import GPT, createVideoFromCategory
from late_post import build_nextcloud_download_url

attach_log_streams("qa_test_working")
logger = get_logger("gallardo.qa_test_working")


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


def test_gpt_script_generation() -> TestResult:
    """Test GPT script generation."""
    result = TestResult("GPT Script Generation")
    result.start()
    
    try:
        gpt = GPT()
        
        if not gpt.api_key:
            result.finish(False, "OPENAI_API_KEY not configured")
            return result
        
        logger.info("Testing GPT script generation...")
        script_response = gpt.generateScript("Technology", "AI")
        
        if not script_response:
            result.finish(False, "GPT returned None response")
            return result
        
        if "raw_content" not in script_response:
            result.finish(False, "GPT response missing 'raw_content' field")
            return result
        
        formatted = gpt.formatForVideo(script_response)
        if not formatted:
            result.finish(False, "Failed to format script for video")
            return result
        
        is_valid, error_msg = gpt.validateScript(formatted)
        if not is_valid:
            result.finish(False, f"Formatted script validation failed: {error_msg}")
            return result
        
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
        logger.info("Testing video generator formatting...")
        formatted = createVideoFromCategory("Technology", "AI")
        
        if not formatted:
            result.finish(False, "createVideoFromCategory returned None")
            return result
        
        required_fields = ["texts", "text_locations"]
        for field in required_fields:
            if field not in formatted:
                result.finish(False, f"Missing required field: {field}")
                return result
        
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


def test_buffer_url_conversion() -> TestResult:
    """Test Buffer posting URL conversion."""
    result = TestResult("Buffer URL Conversion")
    result.start()
    
    try:
        logger.info("Testing Late API URL conversion...")
        
        test_share_url = "https://cloud.targethouse.dk/s/TestShareId"
        download_url = build_nextcloud_download_url(test_share_url)
        
        if "/download" not in download_url:
            result.finish(False, "URL conversion failed")
            return result
        
        if not download_url.startswith("https://"):
            result.finish(False, "Download URL is not a valid HTTPS URL")
            return result
        
        result.finish(
            True,
            details={
                "input_url": test_share_url,
                "output_url": download_url,
                "url_conversion_works": True,
            }
        )
        
    except Exception as e:
        result.finish(False, f"Exception: {str(e)}")
        logger.error("Buffer URL conversion test failed", exc_info=True)
    
    return result


def test_working_pipeline() -> TestResult:
    """Test the working parts of the pipeline: Category → GPT → Video → Buffer URL."""
    result = TestResult("Working Pipeline (GPT → Video → Buffer URL)")
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
        
        # Step 3: Buffer URL Conversion
        logger.info("Step 3: Testing Buffer URL Conversion...")
        buffer_result = test_buffer_url_conversion()
        pipeline_steps.append(("Buffer URL Conversion", buffer_result.passed, buffer_result.error))
        
        if not buffer_result.passed:
            result.finish(False, f"Step 3 failed: {buffer_result.error}")
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
        logger.error("Working pipeline test failed", exc_info=True)
    
    return result


def run_all_tests() -> Dict[str, TestResult]:
    """Run all working component tests."""
    tests = {
        "gpt": test_gpt_script_generation,
        "video": test_video_generator_formatting,
        "buffer": test_buffer_url_conversion,
        "pipeline": test_working_pipeline,
    }
    
    results = {}
    
    for name, test_func in tests.items():
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
    print("QA TEST SUITE - WORKING COMPONENTS")
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
                if key not in ["pipeline_steps"]:
                    print(f"    - {key}: {value}")
    
    print("\n" + "=" * 80)
    
    if failed == 0:
        print("✓ ALL WORKING COMPONENTS PASSED!")
        return 0
    else:
        print(f"✗ {failed} TEST(S) FAILED")
        return 1


def main():
    """Main entry point."""
    results = run_all_tests()
    exit_code = print_summary(results)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

