# Nextcloud Integration Notes

## Table of Contents

1. [URL Format Standards](#url-format-standards)
2. [How Social Media APIs Work](#how-social-media-apis-work)
3. [Platform-Specific Behavior](#platform-specific-behavior)
4. [Implementation Details](#implementation-details)
5. [Known Issues & Solutions](#known-issues--solutions)
6. [Developer Notes](#developer-notes)
7. [References](#references)

---

## URL Format Standards

### Standard URL Formats

Our system uses Nextcloud public share URLs in the following formats:

#### 1. Share URL (Preview Page)
```
https://cloud.targethouse.dk/s/{SHARE_ID}
```
- **Purpose**: Shows Nextcloud preview page with video player
- **Use Case**: Human viewing, manual sharing
- **Example**: `https://cloud.targethouse.dk/s/BmftWeAio67izSH`

#### 2. Download URL (Direct File Access)
```
https://cloud.targethouse.dk/s/{SHARE_ID}/download
```
- **Purpose**: Direct download of video file
- **Use Case**: API consumption, automation, social media posting
- **Example**: `https://cloud.targethouse.dk/s/fkme6YCptT73GTq/download`
- **Recommended Format**: Always use this for programmatic access

#### 3. Directory Share URL (With Query Parameters)
```
https://cloud.targethouse.dk/s/{SHARE_ID}/download?path=%2F&files={filename}
```
- **Purpose**: Downloads specific file from a shared directory
- **Use Case**: When sharing a directory instead of individual file
- **Example**: `https://cloud.targethouse.dk/s/8eHQ4ntJK4yS8ZW/download?path=%2F&files=boat2_merged.mp4`

#### 4. WebDAV URL (Internal Access)
```
https://cloud.targethouse.dk/remote.php/dav/files/{username}/{path}
```
- **Purpose**: Authenticated WebDAV access for uploads
- **Use Case**: Internal system file operations
- **Example**: `https://cloud.targethouse.dk/public.php/dav/files/2GLpYH28F58wAxt/Boat%20cleaning/Rawvideos/boat2.mov`

### URL Generation Workflow

1. **Upload via WebDAV**: Upload file using authenticated WebDAV API
2. **Create Public Share**: Use Nextcloud OCS Share API to create public link
3. **Append `/download`**: Convert share URL to download URL for API use
4. **Verify Access**: Check URL accessibility with retry logic (handles Nextcloud processing delays)
5. **Store in Google Sheet**: Write download URL to "Download URL" column

### Recommended URL Format for APIs

**Always use the `/download` format for social media APIs:**

```
https://cloud.targethouse.dk/s/{SHARE_ID}/download
```

**Why?**
- Direct file access without requiring cookies
- Works reliably with HTTP GET requests
- Compatible with all social media API services
- Avoids browser cookie policy issues

---

## How Social Media APIs Work

### Understanding API Video Upload Behavior

**Important**: Social media APIs (Ayrshare, Late, etc.) **DO NOT** simply link to or embed your Nextcloud video URL. Instead, they:

1. **Download** the video file from your Nextcloud URL
2. **Upload** the video file to their own servers
3. **Post** the video from their servers to the social media platform

This means:
- ✅ Your Nextcloud URL must be publicly accessible
- ✅ The URL must serve the actual video file (not just a preview page)
- ✅ Cookie issues in browsers **do not affect** API consumption
- ✅ The `/download` format is ideal for API access

### Why Cookie Issues Don't Matter for APIs

Browser cookie strict policy errors occur because:
- Browsers block third-party cookies by default
- Nextcloud share pages may require session cookies

APIs work differently:
- Use standard HTTP GET requests
- Don't rely on browser cookies
- Can access `/download` URLs directly
- **Your code already handles this correctly** (see `download_nextcloud_public_file()` in `sheet.py`)

---

## Platform-Specific Behavior

### Social Media Platform Comparison

| Platform | Inline Playback of Nextcloud URL | API Behavior | Recommended Method |
|----------|----------------------------------|--------------|-------------------|
| **X (Twitter)** | Yes, via link preview with inline playback | Downloads and re-uploads video | Use Nextcloud `/download` URL |
| **Facebook** | No - treats as link share | Downloads and re-uploads video | Use Nextcloud `/download` URL |
| **TikTok** | No - requires direct upload | Downloads and re-uploads video | Use Nextcloud `/download` URL |
| **Instagram** | No - requires direct upload | Downloads and re-uploads video | Use Nextcloud `/download` URL |
| **LinkedIn** | No - treats as link share | Downloads and re-uploads video | Use Nextcloud `/download` URL |

### Platform Details

#### X (Twitter) / Ayrshare

- **Link Preview**: X can show video previews from Nextcloud URLs
- **API Behavior**: Ayrshare downloads video from URL, uploads to X
- **URL Format**: Use `/download` URL in Ayrshare API

```python
# Example from post.py
media_url = build_nextcloud_download_url(share_url)  # Adds /download if needed
payload = {
    "post": post_text,
    "platforms": ["twitter"],
    "mediaUrls": [media_url],
    "isVideo": True,
}
```

#### Facebook / Late API

- **No Inline Playback**: Facebook doesn't support inline video from external URLs
- **API Behavior**: Late downloads video, uploads to Facebook
- **URL Format**: Use `/download` URL in Late API

```python
# Example from late_post.py
media_url = build_nextcloud_download_url(share_url)
payload = {
    "content": post_text,
    "profileId": LATE_PROFILE_ID,
    "mediaItems": [{"type": "video", "source": "url", "url": media_url}],
    "publishNow": True,
}
```

#### TikTok

- **No Direct Support**: TikTok doesn't support external video URLs
- **API Behavior**: Must download and upload via TikTok Share Video API
- **Requirement**: Developer integration and user authorization needed

---

## Implementation Details

### Python Upload & Share Creation

Our implementation uses:

1. **WebDAV Upload**: Authenticated upload to Nextcloud
2. **OCS Share API**: Programmatic creation of public share links
3. **URL Conversion**: Automatic appending of `/download` suffix

#### Example Code Pattern

```python
# Upload via WebDAV
webdav_url = upload_webdav_authenticated(
    base_url=NC_BASE,
    username=NC_USER,
    password=NC_PASS,
    local_path=output_file,
    remote_path=remote_path,
)

# Create public share link
share_url = create_nextcloud_share_link(
    base_url=NC_BASE,
    username=NC_USER,
    password=NC_PASS,
    remote_path=remote_path,
)

# Convert to download URL
download_url = share_url.rstrip("/") + "/download"
```

### URL Verification with Retry Logic

**Issue**: Nextcloud shares may not be immediately accessible after creation (processing delay)

**Solution**: Implemented retry logic with exponential backoff in `sheet.py`

```python
# Verify URL accessibility with retries
max_retries = 3
for attempt in range(max_retries):
    resp = requests.head(download_url, headers=BROWSER_HEADERS, timeout=10)
    if resp.status_code == 200:
        break
    elif attempt < max_retries - 1:
        time.sleep(2 * (attempt + 1))  # Exponential backoff: 2s, 4s, 6s
```

**Benefits**:
- Handles Nextcloud processing delays gracefully
- Provides clear logging of retry attempts
- Warns if URL remains inaccessible after all retries

### Cookie Handling for Downloads

Our `download_nextcloud_public_file()` function handles Nextcloud's cookie requirements:

```python
def download_nextcloud_public_file(url: str) -> Optional[str]:
    """
    Handles Nextcloud public-share links that require strict cookies.
    1. GET the base share page to obtain cookies
    2. Reuse session cookies to request /download
    """
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    
    # Step 1: Visit share page to get cookies
    base_url = url.replace("/download", "")
    r1 = session.get(base_url, timeout=30)
    
    # Step 2: Download with session cookies
    r2 = session.get(url, stream=True, timeout=120)
    # ... save file
```

---

## Known Issues & Solutions

### Issue 1: Share Links Not Immediately Available

**Symptom**: Created share URLs return 404 or timeout immediately after creation

**Cause**: Nextcloud may need time to process the share (cron jobs, background tasks)

**Solution**: 
- ✅ Implemented retry logic with exponential backoff
- ✅ Log warnings if URL remains inaccessible after retries
- ⚠️ If persistent, check Nextcloud cron jobs are running

**Code Location**: `sheet.py` lines 497-534

### Issue 2: Browser Cookie Strict Policy Errors

**Symptom**: Clicking Nextcloud share links in browser shows cookie policy error

**Cause**: Nextcloud requires session cookies for share page access

**Impact**: 
- ❌ Affects human users clicking links in browsers
- ✅ **Does NOT affect** API consumption (APIs use `/download` URLs directly)
- ✅ Our code handles cookies properly for programmatic downloads

**Solution**: 
- For humans: Use Nextcloud UI to access videos
- For APIs: Use `/download` URLs (already implemented)
- Browser issue is a Nextcloud configuration limitation

### Issue 3: Multiple Share Links for Same File

**Symptom**: Same file can have different share IDs when shared at different times

**Cause**: Nextcloud creates unique share IDs for each share operation (security feature)

**Behavior**: 
- Sharing a file creates a new share ID
- Sharing the same file again creates a different share ID
- Both links work, but they're unique

**Impact**: 
- ✅ No functional impact - all share IDs work correctly
- ⚠️ Don't cache share IDs if you expect to re-share files

### Issue 4: Directory vs File Shares

**Symptom**: URLs with query parameters like `?path=%2F&files=video.mp4`

**Cause**: Sharing a directory instead of an individual file

**Solution**: 
- Prefer sharing individual files for cleaner URLs
- Our code handles both formats via `build_nextcloud_download_url()`

---

## Developer Notes

### Current Implementation

**File**: `sheet.py`

**Workflow**:
1. Read Google Sheet rows where "Generate" = TRUE
2. Resolve video file paths/URLs (supports local files and URLs)
3. Call `merge.py` to create merged video
4. Upload merged video to Nextcloud via WebDAV
5. Create public share link via OCS API
6. **NEW**: Verify URL accessibility with retry logic
7. Write download URL to Google Sheet
8. Set "Generate" to FALSE

**Key Functions**:
- `upload_webdav_authenticated()`: Uploads file to Nextcloud
- `create_nextcloud_share_link()`: Creates public share via OCS API
- `build_nextcloud_download_url()`: Ensures `/download` suffix (in `late_post.py`)

### URL Format Standardization

**Consistent Pattern**:
- Share URLs: `https://cloud.targethouse.dk/s/{ID}` (without `/download`)
- Download URLs: `https://cloud.targethouse.dk/s/{ID}/download` (with `/download`)
- Storage: Always store `/download` URLs in Google Sheet for API use

### Configuration

**Environment Variables** (via `.env`):
```env
NC_BASE=https://cloud.targethouse.dk
NC_USER=videoeditor
NC_PASS=your_password
NC_REMOTE_DIR=Videos
```

**Directory Structure**:
- Local temp videos: `temp_videos/`
- Nextcloud upload path: `Videos/` (relative to user root)
- Share links created immediately after upload

### Future Improvements

Potential enhancements:
- [ ] Add URL validation before writing to sheet
- [ ] Implement share link expiration management
- [ ] Add support for custom share permissions
- [ ] Cache verified URLs to reduce retry overhead

---

## References

### Nextcloud API Documentation

- [OCS Share API](https://doc.nextcloud.com/server/developer_manual/core/apis/ocs-share-api.html) - Share link creation
- [WebDAV API](https://doc.nextcloud.com/server/developer_manual/client_apis/WebDAV/) - File upload/download
- [Sharing in Nextcloud](https://nextcloud.com/sharing/) - Official sharing documentation

### Social Media API Documentation

- [Ayrshare API](https://www.ayrshare.com/) - Multi-platform social media posting
- [Late API](https://getlate.dev/) - Cross-platform social media automation
- [TikTok Share Video API](https://developers.tiktok.com/doc/web-video-kit-with-web)

### Community Resources

- [Nextcloud Community Forum](https://help.nextcloud.com/)
- [Nextcloud Reddit Community](https://www.reddit.com/r/NextCloud/)
- [Direct Share Link for Video](https://help.nextcloud.com/t/direct-share-link-for-video/83383)
- [Embed Link-Shared Video in WordPress](https://help.nextcloud.com/t/embed-link-shared-video-in-wordpress/127413)

### Python Libraries

- [pyNextcloud](https://pypi.org/project/pyNextcloud/) - Nextcloud Python client
- [nextcloud_client](https://github.com/pragmaticindustries/pyncclient) - Alternative Nextcloud client
- [Nextcloud Python API Examples](https://github.com/abecam/NextCloud-Python-API-Examples)

---

## Appendix: Quick Reference

### URL Format Decision Tree

```
Is this for human viewing in browser?
├─ YES → Use share URL: https://cloud.targethouse.dk/s/{ID}
└─ NO (API/automation) → Use download URL: https://cloud.targethouse.dk/s/{ID}/download
```

### Standard Workflow

```
1. Upload file via WebDAV
2. Create share link via OCS API
3. Append /download to share URL
4. Verify URL accessibility (with retries)
5. Store /download URL in database/sheet
6. Use /download URL in social media APIs
```

### Common URLs in Our System

- **Share URL** (preview): `https://cloud.targethouse.dk/s/BmftWeAio67izSH`
- **Download URL** (API): `https://cloud.targethouse.dk/s/fkme6YCptT73GTq/download`
- **Directory URL**: `https://cloud.targethouse.dk/apps/files/files/370858?dir=/Videos`

---

**Last Updated**: Based on current implementation in `sheet.py` and `late_post.py`
**Maintained By**: Development team
**Related Files**: `sheet.py`, `late_post.py`, `post.py`, `.env`
