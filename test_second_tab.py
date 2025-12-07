#!/usr/bin/env python3
"""
Test ChatGPT integration with the second tab/worksheet in Google Sheet
"""
import sys
import os
from pathlib import Path

# Setup paths
script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(script_dir))
os.chdir(script_dir)

print("=" * 70)
print("Testing ChatGPT Integration with Second Tab/Worksheet")
print("=" * 70)
print()

# Import required modules
try:
    import gspread
    from google.oauth2.service_account import Credentials
    from config import BASE_DIR, get_env
    from chatgpt_integration import send_categories_to_chatgpt
    print("✓ All modules imported successfully")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

print()

# Load configuration
print("1. Loading Configuration...")
try:
    SHEET_URL = get_env("SHEET_URL")
    SERVICE_ACCOUNT_FILE = get_env("SERVICE_ACCOUNT_FILE")
    
    if not os.path.isabs(SERVICE_ACCOUNT_FILE):
        SERVICE_ACCOUNT_FILE = os.path.join(script_dir, SERVICE_ACCOUNT_FILE)
    
    print(f"   ✓ Sheet URL: {SHEET_URL[:50]}...")
    print(f"   ✓ Service Account: {SERVICE_ACCOUNT_FILE}")
    
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"   ✗ Service account file not found: {SERVICE_ACCOUNT_FILE}")
        sys.exit(1)
    print(f"   ✓ Service account file exists")
    
except Exception as e:
    print(f"   ✗ Configuration error: {e}")
    sys.exit(1)

print()

# Connect to Google Sheet
print("2. Connecting to Google Sheet...")
try:
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    print("   ✓ Authentication successful")
    
    sheet = client.open_by_url(SHEET_URL)
    print(f"   ✓ Opened sheet: {sheet.title}")
    
except Exception as e:
    print(f"   ✗ Failed to connect: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# List all worksheets
print("3. Listing All Worksheets/Tabs...")
try:
    worksheets = sheet.worksheets()
    print(f"   ✓ Found {len(worksheets)} worksheet(s)/tab(s):")
    for i, ws in enumerate(worksheets, 1):
        print(f"     {i}. '{ws.title}' (ID: {ws.id})")
    
    if len(worksheets) < 2:
        print("\n   ⚠ WARNING: Only one worksheet found!")
        print("   You need at least 2 worksheets to test the second tab.")
        print("   Please add a second tab to your Google Sheet.")
        sys.exit(1)
    
    # Get the second worksheet
    second_worksheet = worksheets[1]  # Index 1 = second worksheet (0-indexed)
    print(f"\n   ✓ Using second worksheet: '{second_worksheet.title}'")
    
except Exception as e:
    print(f"   ✗ Failed to list worksheets: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Read headers from second worksheet
print("4. Reading Second Worksheet Structure...")
try:
    ws = second_worksheet
    headers = ws.row_values(1)
    print(f"   ✓ Found {len(headers)} columns in second worksheet")
    
    # Check for Categories and subcategories
    has_categories = "Categories" in headers
    has_subcategories = "subcategories" in headers
    
    if has_categories:
        cat_idx = headers.index("Categories") + 1
        print(f"   ✓ Found 'Categories' column at index {cat_idx}")
    else:
        print("   ✗ 'Categories' column not found")
        print("   Available columns:")
        for i, h in enumerate(headers[:10], 1):  # Show first 10
            print(f"     {i}. {h}")
        if len(headers) > 10:
            print(f"     ... and {len(headers) - 10} more")
    
    if has_subcategories:
        subcat_idx = headers.index("subcategories") + 1
        print(f"   ✓ Found 'subcategories' column at index {subcat_idx}")
    else:
        print("   ✗ 'subcategories' column not found")
    
    if not has_categories and not has_subcategories:
        print("\n   ⚠ WARNING: Neither 'Categories' nor 'subcategories' columns found!")
        print("   Please add these columns to your second worksheet.")
        print("   Column names must be exactly:")
        print("     - 'Categories' (capital C)")
        print("     - 'subcategories' (all lowercase)")
    
except Exception as e:
    print(f"   ✗ Failed to read headers: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Read rows from second worksheet
print("5. Reading Data from Second Worksheet...")
try:
    rows = ws.get_all_records()
    print(f"   ✓ Found {len(rows)} data rows in second worksheet")
    
    # Look for rows with Categories and subcategories
    test_rows = []
    for idx, row in enumerate(rows, start=2):
        category = str(row.get("Categories", "")).strip()
        subcategory = str(row.get("subcategories", "")).strip()
        
        if category or subcategory:
            test_rows.append({
                "row_num": idx,
                "category": category,
                "subcategory": subcategory,
                "generate": row.get("Generate", ""),
                "full_row": row
            })
    
    if not test_rows:
        print("   ⚠ No rows found with Categories or subcategories in second worksheet")
        print("   Please add test data:")
        print("     - Add values to 'Categories' column")
        print("     - Add values to 'subcategories' column")
        sys.exit(1)
    
    print(f"   ✓ Found {len(test_rows)} row(s) with Categories/subcategories")
    print()
    print("   Test rows found in second worksheet:")
    for tr in test_rows[:5]:  # Show first 5
        print(f"     Row {tr['row_num']}: Category='{tr['category']}', Subcategory='{tr['subcategory']}'")
    
    # Use first row for testing
    test_row = test_rows[0]
    print()
    print(f"   Using Row {test_row['row_num']} for testing:")
    print(f"     Category: '{test_row['category']}'")
    print(f"     Subcategory: '{test_row['subcategory']}'")
    
except Exception as e:
    print(f"   ✗ Failed to read rows: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test ChatGPT integration with data from second worksheet
print("6. Testing ChatGPT Integration with Second Worksheet Data...")
print("   This will make an actual API call to OpenAI")
print()

try:
    # Simulate what sheet.py does
    category_val = test_row['category']
    subcategory_val = test_row['subcategory']
    
    # Add some context like sheet.py does
    post_text = test_row['full_row'].get("Post Text", "")
    additional_context = None
    if post_text:
        additional_context = f"Post Text: {post_text}"
    
    print(f"   Sending to ChatGPT (from second worksheet):")
    print(f"     Worksheet: '{ws.title}'")
    print(f"     Row: {test_row['row_num']}")
    print(f"     Category: '{category_val}'")
    print(f"     Subcategory: '{subcategory_val}'")
    if additional_context:
        print(f"     Additional Context: {additional_context[:50]}...")
    print()
    
    # Call the function (same way sheet.py does)
    chatgpt_response = send_categories_to_chatgpt(
        category=category_val,
        subcategory=subcategory_val,
        additional_context=additional_context,
    )
    
    if chatgpt_response is None:
        print("   ✗ ChatGPT returned None")
        print("   Possible reasons:")
        print("     - API key is invalid or missing")
        print("     - Network connectivity issue")
        print("     - Check error messages above")
        sys.exit(1)
    
    print("   ✓ SUCCESS! ChatGPT API call completed!")
    print()
    
    # Display response
    if isinstance(chatgpt_response, dict):
        if "choices" in chatgpt_response and chatgpt_response["choices"]:
            choice = chatgpt_response["choices"][0]
            message = choice.get("message", {})
            content = message.get("content", "")
            
            if content:
                print("   ChatGPT Response:")
                print("   " + "-" * 66)
                # Show first 500 chars
                display_content = content[:500] + "..." if len(content) > 500 else content
                for line in display_content.split('\n'):
                    print(f"   {line}")
                print("   " + "-" * 66)
            
            # Show usage
            if "usage" in chatgpt_response:
                usage = chatgpt_response["usage"]
                print(f"\n   Token Usage:")
                print(f"     Total: {usage.get('total_tokens', 'N/A')}")
                print(f"     Prompt: {usage.get('prompt_tokens', 'N/A')}")
                print(f"     Completion: {usage.get('completion_tokens', 'N/A')}")
    
except Exception as e:
    print(f"   ✗ Error during ChatGPT call: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 70)
print("✓ SECOND TAB TEST PASSED!")
print("=" * 70)
print()
print("Summary:")
print(f"  ✓ Connected to Google Sheet: {sheet.title}")
print(f"  ✓ Found {len(worksheets)} worksheet(s)")
print(f"  ✓ Tested with second worksheet: '{ws.title}'")
print("  ✓ Found Categories and subcategories columns")
print("  ✓ Read data from second worksheet correctly")
print("  ✓ Sent data to ChatGPT successfully")
print("  ✓ Received response from ChatGPT")
print()
print("The integration works correctly with the second tab!")
print()
print("To use the second tab in sheet.py:")
print("  Set WORKSHEET_NAME environment variable to the second tab's name")
print("  Or modify WORKSHEET_NAME in your .env file")

