# How to Get a Cookies File for YouTube Authentication

Cookies files are used to authenticate with YouTube and other platforms, helping bypass bot detection and access restricted content. Here's how to obtain a cookies file in Netscape format.

## Method 1: Using yt-dlp (Recommended)

This is the easiest and most reliable method. yt-dlp can extract cookies directly from your browser.

### Step 1: Install yt-dlp
If you haven't already, install yt-dlp:
```bash
pip install yt-dlp
```

### Step 2: Export Cookies from Your Browser
Run this command to export cookies from Chrome:

```bash
yt-dlp --cookies-from-browser chrome --cookies cookies.txt https://www.youtube.com
```

**For different browsers:**
- **Firefox:** `yt-dlp --cookies-from-browser firefox --cookies cookies.txt https://www.youtube.com`
- **Edge:** `yt-dlp --cookies-from-browser edge --cookies cookies.txt https://www.youtube.com`
- **Safari:** `yt-dlp --cookies-from-browser safari --cookies cookies.txt https://www.youtube.com`

**Note:** This exports ALL cookies from your browser (not just YouTube). Keep this file secure!

### Step 3: Verify the Cookies File
The cookies file should start with:
```
# HTTP Cookie File
```
or
```
# Netscape HTTP Cookie File
```

Open `cookies.txt` and verify the first line matches one of the above formats.

## Method 2: Using Browser Extensions

### For Chrome/Edge:
1. Install the extension: **"Get cookies.txt LOCALLY"** (make sure it's the "LOCALLY" version, not the original)
2. Navigate to YouTube and log in
3. Click the extension icon
4. Select the cookies you want (or select all)
5. Click "Export" to download `cookies.txt`

### For Firefox:
1. Install the extension: **"cookies.txt"**
2. Navigate to YouTube and log in
3. Click the extension icon
4. Click "Export" to download `cookies.txt`

**Warning:** Only install extensions from official browser stores. Avoid the original "Get cookies.txt" Chrome extension as it has been reported as malware.

## Method 3: Manual Export (Advanced)

You can manually export cookies using browser developer tools, but this is more complex and not recommended unless you're familiar with the process.

## Important Notes

1. **File Format:** The cookies file MUST be in Netscape format with the header `# HTTP Cookie File` or `# Netscape HTTP Cookie File` as the first line.

2. **File Encoding:** 
   - On Windows: Use CRLF (`\r\n`) line endings
   - On Linux/Mac: Use LF (`\n`) line endings
   
   If you get "HTTP Error 400: Bad Request", try converting the line endings.

3. **Security:** 
   - Cookies files contain sensitive authentication data
   - **NEVER commit cookies files to git repositories**
   - **NEVER share cookies files publicly**
   - Treat cookies files like passwords - keep them secure
   - Delete cookies files when no longer needed

4. **File Expiration:** Cookies expire over time. If downloads start failing, you may need to export a fresh cookies file.

5. **Platform-Specific:**
   - For Docker/cloud deployments, you'll need to export cookies locally and include them in your requests
   - Cookies files cannot be extracted from browsers running in Docker containers
   - Export cookies on your local machine and upload them with your API requests

## Using Cookies with the API

Once you have a `cookies.txt` file:

1. **For all endpoints:** Upload the cookies file with the field name `cookies_file`
   - This single cookies file will be used for all downloads in the request
   - For the merge endpoint, the same `cookies_file` is used for both video and audio downloads

## Troubleshooting

**Problem:** "Invalid cookies file format" error
- **Solution:** Ensure the first line is `# HTTP Cookie File` or `# Netscape HTTP Cookie File`
- Verify line endings match your OS format

**Problem:** Downloads still fail with authentication errors
- **Solution:** Cookies may have expired - export a fresh cookies file
- Make sure you're logged into YouTube in the browser you're exporting from

**Problem:** "400: Bad Request" when using cookies
- **Solution:** Check file encoding and line endings (CRLF for Windows, LF for Unix)

## Example Workflow

1. Open Chrome and log into YouTube
2. Run: `yt-dlp --cookies-from-browser chrome --cookies cookies.txt https://www.youtube.com`
3. Verify `cookies.txt` exists and has the correct header
4. Upload `cookies.txt` with your API request using the `cookies_file` field
5. Your downloads should now work with authentication!

