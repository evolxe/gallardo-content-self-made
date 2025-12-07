# QA Test Suite Guide

## Overview

The QA test suite (`qa_test_suite.py`) tests each integration individually and the entire end-to-end pipeline to ensure zero failed steps.

## Test Components

### 1. GPT Script Generation
- Tests OpenAI API integration
- Validates script generation from category/subcategory
- Checks response formatting

### 2. Video Generator Output Formatting
- Tests script formatting for video generator
- Validates output structure (texts, text_locations)
- Ensures valid location values

### 3. NextCloud Upload and Download
- Tests WebDAV upload functionality
- Tests share link creation
- Tests file download with cookie handling
- Verifies content integrity

### 4. Buffer Posting (Late API)
- Tests URL conversion (share URL → download URL)
- Validates API configuration
- Note: Actual posting is skipped to avoid spamming social media

### 5. Facebook → CRM Lead Sync
- Tests Groundhogg authentication
- Tests contact creation and retrieval
- Tests Facebook lead processor initialization

### 6. End-to-End Pipeline
- Tests complete flow: Category → GPT → Video → Social posting → Leads → CRM
- Ensures all steps work together

## Usage

### Run All Tests
```bash
python qa_test_suite.py
```

### Test Specific Component
```bash
python qa_test_suite.py --component gpt
python qa_test_suite.py --component video
python qa_test_suite.py --component nextcloud
python qa_test_suite.py --component buffer
python qa_test_suite.py --component facebook
python qa_test_suite.py --component e2e
```

### Skip Specific Components
```bash
python qa_test_suite.py --skip nextcloud,facebook
```

## Required Environment Variables

### For GPT Tests
- `OPENAI_API_KEY` - OpenAI API key
- `OPENAI_API_URL` (optional) - API endpoint
- `OPENAI_MODEL` (optional) - Model name

### For NextCloud Tests
- `NC_BASE` - NextCloud base URL
- `NC_USER` - NextCloud username
- `NC_PASS` - NextCloud password

### For Buffer/Late Tests
- `LATE_API_KEY` - Late API key
- `LATE_PROFILE_ID` - Late profile ID

### For Facebook/CRM Tests
- `GROUNDHOGG_API_KEY` - Groundhogg API key
- `GROUNDHOGG_API_SECRET` - Groundhogg API secret
- `GROUNDHOGG_BASE_URL` - Groundhogg base URL
- `FACEBOOK_ACCESS_TOKEN` (optional) - Facebook access token

## Expected Output

```
================================================================================
QA TEST SUITE SUMMARY
================================================================================

Total Tests: 6
Passed: 6
Failed: 0
Success Rate: 100.0%

--------------------------------------------------------------------------------
Test Results:
--------------------------------------------------------------------------------
  ✓ PASS GPT Script Generation (2.34s)
  ✓ PASS Video Generator Output Formatting (0.12s)
  ✓ PASS NextCloud Upload and Download (5.67s)
  ✓ PASS Buffer Posting (Late API) (0.05s)
  ✓ PASS Facebook → CRM Lead Sync (1.23s)
  ✓ PASS End-to-End Pipeline (9.41s)

================================================================================
✓ ALL TESTS PASSED - Zero failed steps in end-to-end flow!
```

## Success Criteria

✅ **Done When**: You have zero failed steps in end-to-end flow.

All tests must pass for the system to be considered production-ready.

## Troubleshooting

### GPT Test Fails
- Check `OPENAI_API_KEY` is set correctly
- Verify API endpoint is accessible
- Check API quota/rate limits

### NextCloud Test Fails
- Verify credentials are correct
- Check network connectivity to NextCloud server
- Ensure sufficient storage space
- Note: NextCloud shares may take a few seconds to become accessible

### Buffer Test Fails
- Verify `LATE_API_KEY` and `LATE_PROFILE_ID` are set
- Check Late API status

### Facebook/CRM Test Fails
- Verify Groundhogg credentials
- Check API endpoint accessibility
- Ensure test contact can be created (may need permissions)

## Notes

- The test suite creates temporary test contacts in Groundhogg (with email like `qa_test_<timestamp>@example.com`)
- NextCloud tests create and delete temporary files
- Buffer posting test skips actual posting to avoid spamming social media
- All tests include proper cleanup of temporary resources

