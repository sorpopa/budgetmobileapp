import anthropic
import os
from typing import Optional
import random
from dotenv import load_dotenv
import requests
import time
import httpx

# Load environment variables from .env file
load_dotenv()


class FinancialAdviceGenerator:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the AI advice generator with Anthropic Claude

        Args:
            api_key: Anthropic API key. If None, will try to get from environment variable
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')

        # Validate API key exists
        if not self.api_key:
            print("Warning: No ANTHROPIC_API_KEY found in environment variables")

        # Initialize client with timeout and retry settings
        http_client = httpx.Client(verify=False)
        self.client = anthropic.Anthropic(
            api_key=self.api_key,
            http_client=http_client
        )

        # Fallback motivational messages if API fails
        self.fallback_messages = [
            "Great job tracking your expenses! Every dollar you monitor is a step toward financial freedom.",
            "Small consistent savings today lead to big financial wins tomorrow. Keep up the excellent work!",
            "You're building healthy money habits that will serve you for life. Stay focused on your goals!",
            "Remember: budgeting isn't about restricting yourself, it's about giving yourself permission to "
            "spend on what truly matters.",
            "Your financial journey is a marathon, not a sprint. Every budget decision is progress forward.",
            "Celebrating small wins keeps you motivated! Each day you stick to your budget is a victory "
            "worth acknowledging.",
            "You have the power to shape your financial future. Every conscious spending choice brings "
            "you closer to your dreams.",
            "Building wealth isn't about making more money—it's about making smart decisions with what you have."
        ]


    def generate_advice_with_fallback(self) -> str:
        """
        Generate advice with multiple fallback strategies

        Returns:
            String containing financial advice
        """
        # Check if API key is available
        if not self.api_key:
            print("No API key available, using fallback message")
            return random.choice(self.fallback_messages)

        # Try the API call with retries
        for attempt in range(3):
            try:
                print(f"Attempting API call (attempt {attempt + 1}/3)...")

                prompt = """Please provide 2-5 sentences of encouraging, motivational financial advice for someone who is actively managing their budget. The advice should be:

- Positive and uplifting in tone
- Practical and actionable
- Focused on building good financial habits
- Suitable for anyone working on their personal finances
- Motivational without being preachy

Keep the language friendly, supportive, and accessible. Avoid complex financial jargon."""

                response = self.client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=200,
                    temperature=0.7,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )

                advice = response.content[0].text.strip()

                # Validate response length
                if len(advice) < 50 or len(advice) > 500:
                    print("Response length invalid, using fallback")
                    return random.choice(self.fallback_messages)

                print("✓ Successfully generated AI advice")
                return advice

            except anthropic.APIConnectionError as e:
                print(f"Connection error (attempt {attempt + 1}): {e}")
                if attempt < 2:  # Don't sleep on last attempt
                    time.sleep(2 ** attempt)  # Exponential backoff
                continue
            except anthropic.AuthenticationError as e:
                print(f"Authentication error: {e}")
                break  # Don't retry auth errors
            except anthropic.RateLimitError as e:
                print(f"Rate limit error: {e}")
                if attempt < 2:
                    time.sleep(5)  # Wait longer for rate limits
                continue
            except Exception as e:
                print(f"Unexpected error (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    time.sleep(1)
                continue

        print("All API attempts failed, using fallback message")
        return random.choice(self.fallback_messages)

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
            prompt = f"""Please provide 2-5 sentences of encouraging, motivational financial advice for someone who is actively managing their budget. 

{theme_context}.

The advice should be:
- Positive and uplifting in tone
- Practical and actionable
- Focused on building good financial habits
- Motivational without being preachy

Keep the language friendly, supportive, and accessible."""

            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=200,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            advice = response.content[0].text.strip()

            if len(advice) < 50 or len(advice) > 500:
                return random.choice(self.fallback_messages)
            print("returned message with claude")

            return advice

        except Exception as e:
            print(f"Error generating themed advice: {e}")
            return random.choice(self.fallback_messages)


# Debug function to help troubleshoot
def debug_connection():
    """
    Debug function to help identify connection issues
    """
    print("=== Debugging Anthropic Connection ===")

    # Check if .env file exists
    if os.path.exists('.env'):
        print("✓ .env file found")
    else:
        print("✗ .env file not found")

    # Check if API key is loaded
    load_dotenv()
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if api_key:
        print(f"✓ API key loaded (starts with: {api_key[:10]}...)")
    else:
        print("✗ No API key found in environment variables")
        return

    # Test different endpoints
    endpoints_to_test = [
        'https://api.anthropic.com',
        'https://api.anthropic.com/v1/messages',
        'https://www.anthropic.com'
    ]

    for endpoint in endpoints_to_test:
        try:
            response = requests.get(endpoint, timeout=10)
            print(f"✓ Can reach {endpoint} (status: {response.status_code})")
        except requests.exceptions.ConnectionError:
            print(f"✗ Cannot reach {endpoint} - connection error")
        except requests.exceptions.Timeout:
            print(f"✗ Timeout connecting to {endpoint}")
        except Exception as e:
            print(f"✗ Error connecting to {endpoint}: {e}")


# Main functions for your Flet app
def get_daily_financial_advice() -> str:
    """
    Main function to call from your Flet app for general advice
    Uses robust fallback system for network issues

    Returns:
        Generated financial advice text
    """
    advisor = FinancialAdviceGenerator()
    return advisor.generate_advice_with_fallback()


def get_daily_financial_advice_simple() -> str:
    """
    Simplified version that just returns fallback messages
    Use this if you continue having connection issues

    Returns:
        Motivational financial advice from fallback messages
    """
    advisor = FinancialAdviceGenerator()
    return random.choice(advisor.fallback_messages)


def get_themed_financial_advice(theme: str = "general") -> str:
    """
    Function to get themed financial advice

    Args:
        theme: 'saving', 'budgeting', 'investing', 'debt', or 'general'

    Returns:
        Generated themed financial advice text
    """
    advisor = FinancialAdviceGenerator()
    return advisor.generate_themed_advice(theme)

