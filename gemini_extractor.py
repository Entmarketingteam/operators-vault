"""
Gemini 2.x SDK Multimodal Extractor for Operators Vault.
Uses the new google-genai library.
"""
from __future__ import annotations

import os
import time
import json
import re
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from structured_logger import get_logger

_log = get_logger("gemini_extractor")

def get_client():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set in environment")
    return genai.Client(api_key=api_key)

def process_video_multimodal(video_path: str | Path, prompt_set: str = "operators") -> dict[str, Any]:
    """
    Analyzes video using Gemini 2.0 Flash via new SDK.
    """
    client = get_client()
    
    # 1. Upload
    _log.info(f"Uploading {video_path} to Gemini...")
    file = client.files.upload(file=video_path)
    _log.info(f"Uploaded file '{file.display_name}' as : {file.uri}")
    
    while file.state == "PROCESSING":
        time.sleep(5)
        file = client.files.get(name=file.name)
    
    if file.state == "FAILED":
        raise ValueError(f"File processing failed: {file.state}")
    
    # 2. Prepare Prompt
    prompt = """
    You are an expert DTC Operator and Content Analyst. 
    Analyze this video and provide a comprehensive extraction in the following JSON format:
    
    {
      "transcription": "Full clean transcription of the video",
      "visual_moments": [
        {
          "start_time_sec": integer,
          "end_time_sec": integer,
          "description": "Detailed description of what is shown (spreadsheet, dashboard, slide, specific person)",
          "transcript_excerpt": "Quote from audio during this moment"
        }
      ],
      "insights": [
        {
          "category": "Tactical Recommendation | Framework | Case Study | Metric",
          "title": "Short punchy title",
          "description": "Detailed insight explanation",
          "start_time_sec": integer,
          "end_time_sec": integer
        }
      ]
    }
    
    Focus on high-leverage DTC insights, tactical advice, and clear visual transitions.
    If the speaker shows a specific tool (Shopify, Meta Ads, Google Sheets), name it.
    Output ONLY valid JSON.
    """
    
    _log.info(f"Starting Gemini analysis for {video_path}...")
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(file_uri=file.uri, mime_type=file.mime_type),
                    types.Part.from_text(text=prompt)
                ]
            )
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )
    
    # 3. Parse Response
    try:
        if response.parsed:
            data = response.parsed
        else:
            # Fallback to manual parsing if .parsed is not populated
            raw_text = response.text
            match = re.search(r"```json\s*(.*?)\s*```", raw_text, re.DOTALL)
            if match:
                raw_text = match.group(1)
            data = json.loads(raw_text)
        
        # Cleanup file after processing
        client.files.delete(name=file.name)
        
        return data
    except Exception as e:
        _log.error(f"Failed to parse Gemini response: {e}")
        if hasattr(response, 'text'):
             _log.debug(f"Raw response: {response.text}")
        return {}

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    if len(sys.argv) > 1:
        load_dotenv()
        res = process_video_multimodal(sys.argv[1])
        print(json.dumps(res, indent=2))
