
import os
import base64
import json
import logging
import requests
import re
from pathlib import Path

logger = logging.getLogger(__name__)

class AISolver:
    def __init__(self, api_key=None, api_base=None, model=None):
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        self.api_base = api_base or os.environ.get('OPENAI_API_BASE', 'https://api.openai.com/v1')
        self.model = model or os.environ.get('AI_MODEL', 'gpt-4o')
        
    def _encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def identify_gap(self, image_path, prompt_text=None):
        """
        Identify the X coordinate of a sliding captcha gap.
        Returns: int (x coordinate) or None
        """
        if not self.api_key:
            logger.error("OPENAI_API_KEY not set")
            return None

        if not prompt_text:
            prompt_text = "这是一张带有缺口的滑动验证码背景图。请帮我找出缺口中心在图片中的 X 轴像素坐标。请只返回一个数字，例如：156"

        try:
            base64_image = self._encode_image(image_path)
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 50
            }

            url = f"{self.api_base.rstrip('/')}/chat/completions"
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"AI API Error: {response.text}")
                return None

            result = response.json()['choices'][0]['message']['content']
            logger.info(f"AI Response: {result}")

            # Extract number
            match = re.search(r'\d+', result)
            if match:
                return int(match.group())
            return None

        except Exception as e:
            logger.error(f"AISolver Error: {e}")
            return None

    def solve_text_captcha(self, image_path, prompt_text="Please identify the text or characters in this image."):
        """
        Generic text captcha solver.
        """
        pass # To be implemented if needed
