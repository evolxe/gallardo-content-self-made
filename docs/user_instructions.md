# User Instructions for Google Sheet Video Pipeline

## Overview

This guide explains how to fill out the Google Sheet to generate merged videos with intro/outro segments and text overlays.

---

## Required Columns

### Video File Name
**What to enter:**
- The main video file you want to process
- Can be a **local filename** (if file is in `temp_videos/` folder) OR a **Nextcloud URL**

**Examples:**
- Local file: `boat2.mov`
- Nextcloud URL: `https://cloud.targethouse.dk/s/XXXXXXXXX`
- Nextcloud download URL: `https://cloud.targethouse.dk/s/XXXXXXXXX/download`

### Intro Video File Name/URL
**What to enter:**
- The intro/opening video segment
- Same format as Video File Name (local file or Nextcloud URL)

**Examples:**
- Local file: `intro.mp4`
- Nextcloud URL: `https://cloud.targethouse.dk/s/YYYYYYYYY`

### Exit Video File Name/URL
**What to enter:**
- The outro/closing video segment
- Same format as Video File Name (local file or Nextcloud URL)

**Examples:**
- Local file: `exit.mp4`
- Nextcloud URL: `https://cloud.targethouse.dk/s/ZZZZZZZZZ`

### Video Text 1, 2, 3
**What to enter:**
- Text overlays to display on the video
- Leave empty if you don't want text on that position
- Each text can be multiple lines (use line breaks in the cell)

**Examples:**
- `Welcome to our channel`
- `Subscribe for more!`
- `Check out our website`

### Text 1/2/3 Location
**What to enter:**
- Position where the text should appear
- Options: `top`, `top-left`, `top-right`, `center`, `center-left`, `center-right`, `bottom`, `bottom-left`, `bottom-right`
- Default: `bottom` (if left empty)

**Examples:**
- `top`
- `bottom-right`
- `center`

### Overlay Element 1
**What to enter:**
- Image or logo to overlay on the video
- Can be a local file path or Nextcloud URL
- Leave empty if you don't want an overlay

**Examples:**
- Local file: `logo.png`
- Nextcloud URL: `https://cloud.targethouse.dk/s/AAAAAAAAA`

### Overlay 1 Location
**What to enter:**
- Position where the overlay should appear
- Same options as Text Location
- Default: `top-right` (if left empty)

### Generate
**What to enter:**
- Set to `TRUE`, `YES`, `1`, or `ON` to process this row
- Set to `FALSE`, `NO`, `0`, or leave empty to skip
- After processing, the system automatically sets this to `FALSE`

**Examples:**
- `TRUE` (will process)
- `FALSE` (will skip)
- `YES` (will process)

### Download URL
**What to enter:**
- **Leave this column empty** - it's automatically filled by the system
- After processing, this will contain the Nextcloud download link for your merged video

---

## How to Get Nextcloud Share Links

### Step-by-Step Instructions

1. **Open Nextcloud** in your web browser
   - Go to: `https://cloud.targethouse.dk`

2. **Navigate to your video file**
   - Browse to the folder containing your video
   - Or use the search function to find it

3. **Create a share link**
   - Right-click on the video file
   - Select **"Share"** from the menu
   - Click **"Share link"** or **"Copy link"**
   - The link will be copied to your clipboard

4. **Paste into Google Sheet**
   - Paste the link directly into the appropriate column
   - **Both formats work:**
     - `https://cloud.targethouse.dk/s/XXXXXXXXX` ✅
     - `https://cloud.targethouse.dk/s/XXXXXXXXX/download` ✅

### What the Link Looks Like

A Nextcloud share link typically looks like:
```
https://cloud.targethouse.dk/s/AbCdEfGhIjKlMnOpQrStUvWxYz
```

The part after `/s/` is a unique share ID that Nextcloud generates.

---

## URL Format Guidelines

### ✅ Acceptable Formats

All of these formats are accepted and will work:

1. **Share URL (without /download)**
   ```
   https://cloud.targethouse.dk/s/XXXXXXXXX
   ```

2. **Download URL (with /download)**
   ```
   https://cloud.targethouse.dk/s/XXXXXXXXX/download
   ```

3. **Share URL with query parameters** (for directory shares)
   ```
   https://cloud.targethouse.dk/s/XXXXXXXXX/download?path=%2F&files=video.mp4
   ```

4. **Local filename** (if file is in temp_videos folder)
   ```
   boat2.mov
   intro.mp4
   ```

### ❌ Common Mistakes to Avoid

1. **Don't use internal Nextcloud paths** like:
   ```
   ❌ https://cloud.targethouse.dk/apps/files/files/12345?dir=/Videos
   ```
   These can change with Nextcloud updates and won't work reliably.

2. **Don't use WebDAV URLs** like:
   ```
   ❌ https://cloud.targethouse.dk/remote.php/dav/files/username/video.mp4
   ```
   These require authentication and won't work for public access.

3. **Don't forget the share link format**:
   ```
   ❌ https://cloud.targethouse.dk/video.mp4
   ```
   Always use the `/s/` share link format.

---

## Workflow Example

### Complete Example Row

Here's what a complete row might look like:

| Generate | Video File Name | Intro Video File Name/URL | Exit Video File Name/URL | Video Text 1 | Text 1 Location | ... |
|----------|----------------|--------------------------|-------------------------|--------------|-----------------|-----|
| TRUE | `https://cloud.targethouse.dk/s/AbCdEf123` | `intro.mp4` | `https://cloud.targethouse.dk/s/XyZ789` | `Welcome!` | `top` | ... |

### What Happens When You Set Generate = TRUE

1. **System reads your row** from the Google Sheet
2. **Downloads videos** from Nextcloud (if URLs provided) or uses local files
3. **Merges videos** in order: Intro → Main → Exit
4. **Adds text overlays** at specified locations
5. **Adds overlay elements** (logos, images) if provided
6. **Uploads merged video** to Nextcloud
7. **Creates share link** and writes it to "Download URL" column
8. **Sets Generate to FALSE** to mark as complete

---

## Troubleshooting

### "Could not find file" Error

**Problem:** System can't find your video file

**Solutions:**
- If using a local filename, make sure the file is in the `temp_videos/` folder
- If using a Nextcloud URL, verify the link works by opening it in a browser
- Check that the URL is a share link (starts with `https://cloud.targethouse.dk/s/`)

### "URL validation failed" Error

**Problem:** The Nextcloud URL format is incorrect

**Solutions:**
- Make sure you copied the full share link from Nextcloud
- Verify the link starts with `https://cloud.targethouse.dk/s/`
- Try copying the link again from Nextcloud (right-click → Share → Copy link)

### Video Not Processing

**Problem:** Row has Generate = TRUE but nothing happens

**Solutions:**
- Check that all required fields are filled (Video File Name, Intro, Exit)
- Verify the Generate column contains `TRUE`, `YES`, `1`, or `ON`
- Check the system logs for error messages
- Ensure the cron job is running (if automated) or run the script manually

### Download URL Not Appearing

**Problem:** Video processed but Download URL column is empty

**Solutions:**
- Check if there's a "Download URL" column in your sheet
- Verify the upload to Nextcloud succeeded (check system logs)
- The URL may take a few seconds to become available - check again in a minute

---

## Tips & Best Practices

1. **Test with one row first** before processing multiple videos
2. **Use share links** instead of local files when possible (more reliable)
3. **Keep video files organized** in Nextcloud folders
4. **Check the Download URL** after processing to verify the video uploaded correctly
5. **Set Generate back to TRUE** if you need to reprocess a video (after fixing any issues)

---

## Need Help?

If you encounter issues not covered here:
1. Check the system logs for detailed error messages
2. Verify your Nextcloud share links are working (open in browser)
3. Ensure all required columns are filled correctly
4. Contact your system administrator

---

**Last Updated:** Based on current system implementation
**Related Documentation:** See `docs/next_cloud_notes.md` for technical details

