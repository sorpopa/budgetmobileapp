import requests
import os
from typing import Optional
from dotenv import load_dotenv
import random
import json
import re
from datetime import datetime


load_dotenv()

class ClaudeUtilityFunctions:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the AI advice generator with Anthropic Claude

        Args:
            api_key: Anthropic API key. If None, will try to get from environment variable
        """


        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self.api_url = 'https://api.anthropic.com/v1/messages'

        # Validate API key exists
        if not self.api_key:
            print("Warning: No ANTHROPIC_API_KEY found in environment variables")

        self.prompt = "Give a short financial advice"

        self.headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key,
            'anthropic-version': '2023-06-01'
        }

        self.data = {
            'model': 'claude-3-7-sonnet-latest',
            'max_tokens': 1024,
            'messages': [
                {'role': 'user', 'content': self.prompt}
            ]
        }

    def process_image_with_anthropic(self, image_base64):
        """Send image to Anthropic API for expense extraction"""
        try:
            prompt = """
            Analyze this receipt/expense image and extract the following information in JSON format:

            {
                "amount": "amount as float (just the number, no currency symbol)",
                "category": "expense category (food, transport, shopping, utilities, entertainment, etc.)",
                "description": "brief description of the expense/merchant name",
                "date": "date from receipt in YYYY-MM-DD format (use today's date if not visible)"
            }

            Rules:
            - If amount is not clearly visible, set to 0.0
            - Choose the most appropriate category from common expense categories
            - Keep description concise but informative
            - If date is not visible on receipt, use today's date
            - Only return the JSON object, no additional text
            """
            data = {
            'model': 'claude-3-7-sonnet-latest',
            'max_tokens': 1024,
            'messages': [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            }

            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=data,
                verify=False  # Note: Using verify=False is not recommended for production
            )
            if response.status_code != 200:
                print(f"Error: {response.status_code}")
                print(f"Response: {response.text}")
                return None

            result = response.json()
            response_text = result['content'][0]['text']
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            else:
                # Fallback if JSON extraction fails
                return {
                    "amount": 0.0,
                    "category": "miscellaneous",
                    "description": "Could not extract details from image",
                    "date": datetime.now().strftime('%Y-%m-%d')
                }

        except Exception as e:
            print(f"Error processing image with Anthropic: {e}")
            return {
                "amount": 0.0,
                "category": "miscellaneous",
                "description": "Error processing image",
                "date": datetime.now().strftime('%Y-%m-%d')
            }


    def generate__advice_with_fallback(self):
        print("generating advice with claude")

        """
                Generate advice with multiple fallback strategies

                Returns:
                    String containing financial advice
                """
        # Check if API key is available
        if not self.api_key:
            print("No API key available, using fallback message")
            return random.choice(self.fallback_messages)

        self.prompt = """Please provide 2-5 sentences of encouraging, motivational financial advice for someone who is actively managing their budget. The advice should be:

        - Positive and uplifting in tone
        - Practical and actionable
        - Focused on building good financial habits
        - Suitable for anyone working on their personal finances
        - Motivational without being preachy

        Keep the language friendly, supportive, and accessible. Avoid complex financial jargon."""

        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=self.data,
                verify=False  # Note: Using verify=False is not recommended for production
            )
            if response.status_code != 200:
                print(f"Error: {response.status_code}")
                print(f"Response: {response.text}")
                return None

            result = response.json()
            advice = result['content'][0]['text']
            # Validate response length
            if len(advice) < 50 or len(advice) > 500:
                print("Response length invalid, using fallback")
                return random.choice(self.fallback_messages)

            print("✓ Successfully generated AI advice")
            return advice
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return None

    def generate_themed_advice(self, theme: str = "general") -> str:
        """
                Generate themed financial advice

                Args:
                    theme: Theme for advice ('saving', 'budgeting', 'investing', 'debt', 'general')

                Returns:
                    String containing themed financial advice
                """
        theme_prompts = {
            "saving": "Focus on encouraging saving habits and building emergency funds",
            "budgeting": "Focus on budgeting strategies and expense tracking",
            "investing": "Focus on beginner-friendly investment encouragement",
            "debt": "Focus on debt reduction strategies and staying motivated",
            "general": "Provide general financial wellness advice"
        }

        theme_context = theme_prompts.get(theme, theme_prompts["general"])
        try:
            self.prompt = f"""Please provide 2-5 sentences of encouraging, motivational financial advice for someone who is actively managing their budget. 

        {theme_context}.

        The advice should be:
        - Positive and uplifting in tone
        - Practical and actionable
        - Focused on building good financial habits
        - Motivational without being preachy

        Keep the language friendly, supportive, and accessible."""

            try:
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=self.data,
                    verify=False  # Note: Using verify=False is not recommended for production
                )
                if response.status_code != 200:
                    print(f"Error: {response.status_code}")
                    print(f"Response: {response.text}")
                    return None

                result = response.json()
                advice = result['content'][0]['text']
                # Validate response length
                if len(advice) < 50 or len(advice) > 500:
                    print("Response length invalid, using fallback")
                    return random.choice(self.fallback_messages)

                print("✓ Successfully generated AI advice")
                return advice
            except requests.exceptions.RequestException as e:
                print(f"An error occurred: {e}")
                return None


        except Exception as e:
            print(f"Error generating themed advice: {e}")
            return random.choice(self.fallback_messages)

