# OpenCV Installation Notes

Due to a numpy version conflict (opencv-python requires numpy<2.3.0, but we use numpy 2.3.5), 
opencv-python must be installed separately with the `--no-deps` flag:

```bash
pip install opencv-python --no-deps
```

This works because opencv-python is compatible with numpy 2.3.5 at runtime, even though 
its metadata specifies a stricter version requirement.

