README

Video Merge Application

Overview
This repository contains a set of files to merge videos
Using a google form for direction, 3 video files, or URL links to them, are specified.
Along with 3 text segments to be overlayed on the middle video.

The program then takes these 3 videos, concatinates them together, overlays the text on the middle video and outputs the result

Created to interface with NextCloud, the file URLs may be videos in a public share on the NextCloud

Code
There are 2 python scripts at the center of this work

sheets_url.py - Handles the data from the Google Sheets, getting the files/URLs, saving them into a local directory temp_videos and calling upon the next script

merge_videos_cli.py - Handles the merge of video and text overlay, via a set of command line arguments. This may be executed in a stand alone manner, or called by a script above.

Working with the SSH server:

```
ssh -p 2223 office.binarika.com
ssh -p 2223 videoeditor@office.binarika.com
pw: R0cstudio
```

The videos on nextCloud go to the `videoeditor/Videos` directory which is shared





