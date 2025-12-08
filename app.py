#!/usr/bin/env python3
"""
Web Server for Gallardo Content Pipeline

This Flask application provides a web interface to run and monitor
the Gallardo content processing pipeline.
"""

import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from flask import Flask, jsonify, render_template_string, request

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from config import get_env

app = Flask(__name__)

# Global state for tracking running processes
process_status: Dict[str, Any] = {
    "facebook_leads": {"running": False, "last_run": None, "status": "idle", "status_text": "Ready"},
    "video_processing": {"running": False, "last_run": None, "status": "idle", "status_text": "Ready"},
}

# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gallardo Content Pipeline - Web Interface</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 20px;
            text-align: center;
        }
        .header h1 {
            color: #333;
            margin-bottom: 10px;
        }
        .header p {
            color: #666;
        }
        .card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 20px;
        }
        .card h2 {
            color: #333;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .status-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }
        .status-idle { background: #e0e0e0; color: #666; }
        .status-running { background: #4caf50; color: white; }
        .status-success { background: #2196f3; color: white; }
        .status-error { background: #f44336; color: white; }
        .btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: all 0.3s;
            margin-right: 10px;
        }
        .btn:hover {
            background: #5568d3;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        .btn:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        .info {
            margin-top: 15px;
            padding: 15px;
            background: #f5f5f5;
            border-radius: 5px;
            font-family: monospace;
            font-size: 14px;
        }
        .info-item {
            margin: 5px 0;
        }
        .info-label {
            font-weight: bold;
            color: #666;
        }
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .footer {
            text-align: center;
            color: white;
            margin-top: 30px;
            opacity: 0.8;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎬 Gallardo Content Pipeline</h1>
            <p>Web Interface for Video Processing & Facebook Leads Management</p>
        </div>

        <div class="card">
            <h2>
                📘 Facebook Leads Processing
                <span class="status-badge status-{{ facebook_status_class }}" id="fb-status">
                    {{ facebook_status }}
                </span>
            </h2>
            <button class="btn" id="fb-btn" onclick="runFacebookLeads()" {{ fb_disabled }}>
                Process Facebook Leads
            </button>
            <div class="info" id="fb-info">
                <div class="info-item">
                    <span class="info-label">Last Run:</span> 
                    <span id="fb-last-run">{{ facebook_last_run }}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Status:</span> 
                    <span id="fb-status-text">{{ facebook_status_text }}</span>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>
                🎥 Video Processing
                <span class="status-badge status-{{ video_status_class }}" id="video-status">
                    {{ video_status }}
                </span>
            </h2>
            <button class="btn" id="video-btn" onclick="runVideoProcessing()" {{ video_disabled }}>
                Process Videos from Google Sheets
            </button>
            <div class="info" id="video-info">
                <div class="info-item">
                    <span class="info-label">Last Run:</span> 
                    <span id="video-last-run">{{ video_last_run }}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Status:</span> 
                    <span id="video-status-text">{{ video_status_text }}</span>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>📊 System Status</h2>
            <div class="info">
                <div class="info-item">
                    <span class="info-label">Server Time:</span> 
                    <span id="server-time">{{ server_time }}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Python Version:</span> {{ python_version }}
                </div>
                <div class="info-item">
                    <span class="info-label">Environment:</span> {{ environment }}
                </div>
            </div>
        </div>

        <div class="footer">
            <p>Gallardo Content Pipeline Web Interface</p>
        </div>
    </div>

    <script>
        function updateStatus() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    // Update Facebook Leads status
                    const fbStatus = data.facebook_leads;
                    document.getElementById('fb-status').textContent = fbStatus.status;
                    document.getElementById('fb-status').className = 'status-badge status-' + fbStatus.status;
                    document.getElementById('fb-last-run').textContent = fbStatus.last_run || 'Never';
                    document.getElementById('fb-status-text').textContent = fbStatus.status_text || 'Ready';
                    document.getElementById('fb-btn').disabled = fbStatus.running;
                    
                    // Update Video Processing status
                    const videoStatus = data.video_processing;
                    document.getElementById('video-status').textContent = videoStatus.status;
                    document.getElementById('video-status').className = 'status-badge status-' + videoStatus.status;
                    document.getElementById('video-last-run').textContent = videoStatus.last_run || 'Never';
                    document.getElementById('video-status-text').textContent = videoStatus.status_text || 'Ready';
                    document.getElementById('video-btn').disabled = videoStatus.running;
                    
                    // Update server time
                    document.getElementById('server-time').textContent = new Date().toLocaleString();
                })
                .catch(error => console.error('Error updating status:', error));
        }

        function runFacebookLeads() {
            document.getElementById('fb-btn').disabled = true;
            document.getElementById('fb-status-text').textContent = 'Starting...';
            
            fetch('/api/run/facebook-leads', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('fb-status-text').textContent = 'Process started in background';
                    } else {
                        document.getElementById('fb-status-text').textContent = 'Error: ' + data.error;
                        document.getElementById('fb-btn').disabled = false;
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    document.getElementById('fb-status-text').textContent = 'Error: ' + error.message;
                    document.getElementById('fb-btn').disabled = false;
                });
        }

        function runVideoProcessing() {
            document.getElementById('video-btn').disabled = true;
            document.getElementById('video-status-text').textContent = 'Starting...';
            
            fetch('/api/run/video-processing', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('video-status-text').textContent = 'Process started in background';
                    } else {
                        document.getElementById('video-status-text').textContent = 'Error: ' + data.error;
                        document.getElementById('video-btn').disabled = false;
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    document.getElementById('video-status-text').textContent = 'Error: ' + error.message;
                    document.getElementById('video-btn').disabled = false;
                });
        }

        // Update status every 2 seconds
        setInterval(updateStatus, 2000);
        updateStatus();
    </script>
</body>
</html>
"""


def run_facebook_leads_background():
    """Run Facebook leads processing in background thread."""
    try:
        process_status["facebook_leads"]["running"] = True
        process_status["facebook_leads"]["status"] = "running"
        process_status["facebook_leads"]["status_text"] = "Processing leads..."
        
        from process_facebook_leads import main as process_leads_main
        process_leads_main()
        
        process_status["facebook_leads"]["status"] = "success"
        process_status["facebook_leads"]["status_text"] = "Completed successfully"
    except Exception as e:
        process_status["facebook_leads"]["status"] = "error"
        process_status["facebook_leads"]["status_text"] = f"Error: {str(e)}"
    finally:
        process_status["facebook_leads"]["running"] = False
        process_status["facebook_leads"]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_video_processing_background():
    """Run video processing in background thread."""
    try:
        process_status["video_processing"]["running"] = True
        process_status["video_processing"]["status"] = "running"
        process_status["video_processing"]["status_text"] = "Processing videos..."
        
        from sheet import main as sheet_main
        sheet_main()
        
        process_status["video_processing"]["status"] = "success"
        process_status["video_processing"]["status_text"] = "Completed successfully"
    except Exception as e:
        process_status["video_processing"]["status"] = "error"
        process_status["video_processing"]["status_text"] = f"Error: {str(e)}"
    finally:
        process_status["video_processing"]["running"] = False
        process_status["video_processing"]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@app.route('/')
def index():
    """Main web interface."""
    fb_status = process_status["facebook_leads"]["status"]
    video_status = process_status["video_processing"]["status"]
    
    return render_template_string(HTML_TEMPLATE,
        facebook_status=fb_status,
        facebook_status_class=fb_status,
        facebook_last_run=process_status["facebook_leads"]["last_run"] or "Never",
        facebook_status_text=process_status["facebook_leads"]["status_text"] or "Ready",
        fb_disabled="disabled" if process_status["facebook_leads"]["running"] else "",
        video_status=video_status,
        video_status_class=video_status,
        video_last_run=process_status["video_processing"]["last_run"] or "Never",
        video_status_text=process_status["video_processing"]["status_text"] or "Ready",
        video_disabled="disabled" if process_status["video_processing"]["running"] else "",
        server_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        python_version=sys.version.split()[0],
        environment=os.getenv("ENVIRONMENT", "development")
    )


@app.route('/api/status')
def api_status():
    """API endpoint to get current status."""
    return jsonify({
        "facebook_leads": {
            "running": process_status["facebook_leads"]["running"],
            "status": process_status["facebook_leads"]["status"],
            "last_run": process_status["facebook_leads"]["last_run"],
            "status_text": process_status["facebook_leads"]["status_text"]
        },
        "video_processing": {
            "running": process_status["video_processing"]["running"],
            "status": process_status["video_processing"]["status"],
            "last_run": process_status["video_processing"]["last_run"],
            "status_text": process_status["video_processing"]["status_text"]
        }
    })


@app.route('/api/run/facebook-leads', methods=['POST'])
def api_run_facebook_leads():
    """API endpoint to trigger Facebook leads processing."""
    if process_status["facebook_leads"]["running"]:
        return jsonify({"success": False, "error": "Process already running"}), 400
    
    thread = threading.Thread(target=run_facebook_leads_background, daemon=True)
    thread.start()
    
    return jsonify({"success": True, "message": "Facebook leads processing started"})


@app.route('/api/run/video-processing', methods=['POST'])
def api_run_video_processing():
    """API endpoint to trigger video processing."""
    if process_status["video_processing"]["running"]:
        return jsonify({"success": False, "error": "Process already running"}), 400
    
    thread = threading.Thread(target=run_video_processing_background, daemon=True)
    thread.start()
    
    return jsonify({"success": True, "message": "Video processing started"})


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


if __name__ == '__main__':
    print("=" * 80)
    print("Gallardo Content Pipeline - Web Server")
    print("=" * 80)
    print(f"Starting server on http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("=" * 80)
    
    app.run(host='0.0.0.0', port=5000, debug=True)

