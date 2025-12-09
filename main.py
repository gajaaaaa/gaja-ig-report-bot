"""
Instagram Report Bot - Telegram Bot
Python 3.14 compatible version
"""

import os
import sys
import random
import logging
import re
import time
import json
from collections import defaultdict
from threading import Thread
from typing import Optional
import telebot
import instaloader
from flask import Flask
from dotenv import load_dotenv

# Selenium imports for auto-reporting
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logging.warning("Selenium not available. Auto-reporting will be disabled.")

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(filename='bot.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Flask app to keep the bot alive
app = Flask(__name__)

@app.route('/')
def home():
    return "I'm alive"

def run_flask_app():
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask_app)
    t.start()

# Start the Flask app in a thread 
keep_alive()

# Initialize the Telegram bot
API_TOKEN = os.getenv("API_TOKEN")
FORCE_JOIN_CHANNEL = os.getenv("FORCE_JOIN_CHANNEL")
ADMIN_ID = os.getenv("ADMIN_ID")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")
# Optional: Instagram cookies (JSON array from browser export)
INSTAGRAM_COOKIES_JSON = os.getenv("INSTAGRAM_COOKIES_JSON", "")
# Optional: Chrome profile path (persistent session)
CHROME_PROFILE_PATH = os.getenv("CHROME_PROFILE_PATH", None)

bot = telebot.TeleBot(API_TOKEN)

# In-memory list to store user IDs
user_ids = set()

def add_user(user_id: int) -> None:
    """Add user to the tracking list."""
    user_ids.add(user_id)

def remove_user(user_id: int) -> None:
    """Remove user from the tracking list."""
    user_ids.discard(user_id)

def get_all_users() -> list[int]:
    """Get all tracked user IDs."""
    return list(user_ids)

# List of keywords for different report categories
report_keywords = {
    "HATE": ["devil", "666", "savage", "love", "hate", "followers", "selling", "sold", "seller", "dick", "ban", "banned", "free", "method", "paid"],
    "SELF": ["suicide", "blood", "death", "dead", "kill myself"],
    "BULLY": ["@"],
    "VIOLENT": ["hitler", "osama bin laden", "guns", "soldiers", "masks", "flags"],
    "ILLEGAL": ["drugs", "cocaine", "plants", "trees", "medicines"],
    "PRETENDING": ["verified", "tick"],
    "NUDITY": ["nude", "sex", "send nudes"],
    "SPAM": ["phone number", "email", "contact"]
}

def check_keywords(text: str, keywords: list[str]) -> bool:
    """Check if any keyword is present in the text."""
    return any(keyword in text.lower() for keyword in keywords)

def analyze_profile(profile_info: dict) -> dict[str, str]:
    """Analyze profile and generate report suggestions."""
    reports = defaultdict(int)
    profile_texts = [
        profile_info.get("username", ""),
        profile_info.get("biography", ""),
    ]

    for text in profile_texts:
        for category, keywords in report_keywords.items():
            if check_keywords(text, keywords):
                reports[category] += 1

    if reports:
        unique_counts = random.sample(range(1, 6), min(len(reports), 4))
        formatted_reports = {
            category: f"{count}x - {category}" for category, count in zip(reports.keys(), unique_counts)
        }
    else:
        all_categories = list(report_keywords.keys())
        num_categories = random.randint(2, 5)
        selected_categories = random.sample(all_categories, num_categories)
        unique_counts = random.sample(range(1, 6), num_categories)
        formatted_reports = {
            category: f"{count}x - {category}" for category, count in zip(selected_categories, unique_counts)
        }

    return formatted_reports

def get_public_instagram_info(username: str) -> Optional[dict]:
    """Fetch public Instagram profile information."""
    L = instaloader.Instaloader()
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        info = {
            "username": profile.username,
            "full_name": profile.full_name,
            "biography": profile.biography,
            "follower_count": profile.followers,
            "following_count": profile.followees,
            "is_private": profile.is_private,
            "post_count": profile.mediacount,
            "external_url": profile.external_url,
        }
        return info
    except instaloader.exceptions.ProfileNotExistsException:
        return None
    except instaloader.exceptions.InstaloaderException as e:
        logging.error(f"An error occurred: {e}")
        return None

def is_user_in_channel(user_id: int) -> bool:
    """Check if user is a member of the required channel."""
    if not FORCE_JOIN_CHANNEL or FORCE_JOIN_CHANNEL == "your_channel_username":
        return True  # Skip check if channel not configured
    
    try:
        member = bot.get_chat_member(f"@{FORCE_JOIN_CHANNEL}", user_id)
        return member.status in ['member', 'administrator', 'creator']
    except telebot.apihelper.ApiTelegramException as e:
        logging.warning(f"Could not check channel membership for user {user_id}: {e}")
        # If bot doesn't have permission to check, allow access
        return True

def escape_markdown_v2(text: str) -> str:
    """Escape special MarkdownV2 characters."""
    replacements = {
        '_': r'\_', '*': r'\*', '[': r'\[', ']': r'\]',
        '(': r'\(', ')': r'\)', '~': r'\~', '`': r'\`',
        '>': r'\>', '#': r'\#', '+': r'\+', '-': r'\-',
        '=': r'\=', '|': r'\|', '{': r'\{', '}': r'\}',
        '.': r'\.', '!': r'\!'
    }
    pattern = re.compile('|'.join(re.escape(key) for key in replacements.keys()))
    return pattern.sub(lambda x: replacements[x.group(0)], text)

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    
    # Admin can skip channel check
    is_admin = str(user_id) == str(ADMIN_ID)
    
    if not is_admin and FORCE_JOIN_CHANNEL and not is_user_in_channel(user_id):
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("Join Channel", url=f"https://t.me/{FORCE_JOIN_CHANNEL}"))
        markup.add(telebot.types.InlineKeyboardButton("Joined", callback_data='reload'))
        bot.reply_to(message, f"Please join @{FORCE_JOIN_CHANNEL} to use this bot.", reply_markup=markup)
        return

    add_user(user_id)  # Add user to the list
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("Help", callback_data='help'))
    if FORCE_JOIN_CHANNEL:
        markup.add(telebot.types.InlineKeyboardButton("Update Channel", url=f't.me/{FORCE_JOIN_CHANNEL}'))
    bot.reply_to(message, "Welcome! Use /getmeth <username> to analyze an Instagram profile.", reply_markup=markup)

@bot.message_handler(commands=['getmeth'])
def analyze(message):
    user_id = message.chat.id
    
    # Admin can skip channel check
    is_admin = str(user_id) == str(ADMIN_ID)
    
    if not is_admin and FORCE_JOIN_CHANNEL and not is_user_in_channel(user_id):
        bot.reply_to(message, f"Please join @{FORCE_JOIN_CHANNEL} to use this bot.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "📝 Usage:\n/getmeth <username> - Analyze profile\n/getmeth <username> report <number> - Analyze and send reports\n\nExample: /getmeth instagram report 25")
        return

    # Parse command: /getmeth username [report number]
    username = parts[1]
    num_reports = None
    
    # Check if "report" keyword is present
    if "report" in parts:
        try:
            report_index = parts.index("report")
            if report_index + 1 < len(parts):
                num_reports = int(parts[report_index + 1])
                if num_reports < 1 or num_reports > 50:
                    bot.reply_to(message, "⚠️ Number of reports must be between 1 and 50.")
                    return
        except (ValueError, IndexError):
            bot.reply_to(message, "❌ Invalid number. Usage: /getmeth <username> report <number>\nExample: /getmeth instagram report 25")
            return

    bot.reply_to(message, f"🔍 Scanning Your Target Profile: {username}. Please wait...")

    profile_info = get_public_instagram_info(username)
    if profile_info:
        reports_to_file = analyze_profile(profile_info)
        result_text = f"**Public Information for {username}:**\n"
        result_text += f"Username: {profile_info.get('username', 'N/A')}\n"
        result_text += f"Full Name: {profile_info.get('full_name', 'N/A')}\n"
        result_text += f"Biography: {profile_info.get('biography', 'N/A')}\n"
        result_text += f"Followers: {profile_info.get('follower_count', 'N/A')}\n"
        result_text += f"Following: {profile_info.get('following_count', 'N/A')}\n"
        result_text += f"Private Account: {'Yes' if profile_info.get('is_private') else 'No'}\n"
        result_text += f"Posts: {profile_info.get('post_count', 'N/A')}\n"
        result_text += f"External URL: {profile_info.get('external_url', 'N/A')}\n\n"
        result_text += "Suggested Reports for Your Target:\n"
        for report in reports_to_file.values():
            result_text += f"• {report}\n"
        result_text += "\n*Note: This method is based on available data and may not be fully accurate.*"

        # Escape special characters for MarkdownV2
        result_text = escape_markdown_v2(result_text)

        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("Visit Target Profile", url=f"https://instagram.com/{profile_info['username']}"))

        bot.send_message(message.chat.id, result_text, reply_markup=markup, parse_mode='MarkdownV2')
        
        # If report number is specified, start auto-reporting
        if num_reports is not None:
            # Only admin can use auto-report
            if not is_admin:
                bot.reply_to(message, "❌ Only admin can use auto-report feature.")
                return
            
            bot.send_message(user_id, f"🚀 Starting mass report for @{username}...\n📊 Reports to send: {num_reports}\n⚡ Faster mode enabled\n⚠️ This may take a few minutes.")
            
            # Start auto-reporting in background thread
            def report_thread():
                status_msg = bot.send_message(user_id, f"⏳ Processing... 0/{num_reports} reports sent")
                result = auto_report_profile(username, reports_to_file, num_reports=num_reports)
                
                if result["success"]:
                    success_count = result["reports_sent"]
                    failed_count = num_reports - success_count
                    
                    msg = f"✅ *Mass Report Completed!*\n\n"
                    msg += f"🎯 Target: @{username}\n"
                    msg += f"✅ Successfully sent: *{success_count}* reports\n"
                    msg += f"❌ Failed: *{failed_count}* reports\n"
                    msg += f"📊 Success rate: *{(success_count/num_reports*100):.1f}%*\n"
                    
                    if result.get("errors") and len(result["errors"]) > 0:
                        msg += f"\n⚠️ Errors encountered: {len(result['errors'])}"
                        if len(result["errors"]) <= 3:
                            for error in result["errors"]:
                                msg += f"\n• {error[:50]}..."
                    
                    bot.edit_message_text(msg, user_id, status_msg.message_id, parse_mode='Markdown')
                else:
                    bot.edit_message_text(
                        f"❌ *Auto-report failed*\n\nError: {result.get('error', 'Unknown error')}",
                        user_id,
                        status_msg.message_id,
                        parse_mode='Markdown'
                    )
            
            Thread(target=report_thread, daemon=True).start()
    else:
        bot.reply_to(message, f"❌ Profile {username} not found or an error occurred.")

def check_logged_in(driver) -> bool:
    """Check if user is logged in to Instagram."""
    try:
        # Check for login indicators
        current_url = driver.current_url
        if "accounts/login" in current_url:
            return False
        
        # Check for various logged-in indicators
        try:
            # Look for navigation bar elements that only appear when logged in
            driver.find_element(By.XPATH, "//a[contains(@href, '/direct/inbox/') or contains(@href, '/explore/') or contains(@href, '/reels/')]")
            return True
        except:
            pass
        
        # Check if we can see profile elements (only visible when logged in)
        try:
            # Look for profile header or follow button
            driver.find_element(By.XPATH, "//button[contains(text(), 'Follow') or contains(text(), 'Following') or contains(text(), 'Message')]")
            return True
        except:
            pass
        
        # Check URL - if we're on a profile page and not redirected to login, we're probably logged in
        if "/" in current_url and "instagram.com" in current_url and "accounts" not in current_url and "login" not in current_url:
            # Additional check - try to find any interactive element
            try:
                driver.find_element(By.TAG_NAME, "nav")  # Navigation bar
                return True
            except:
                return False
        
        return False
    except Exception as e:
        logging.warning(f"Error checking login status: {e}")
        return False

def login_instagram(driver) -> bool:
    """Login to Instagram."""
    try:
        driver.get("https://www.instagram.com/accounts/login/")
        time.sleep(3)
        
        # Wait for login form
        username_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        password_input = driver.find_element(By.NAME, "password")
        
        # Clear and fill username
        username_input.clear()
        time.sleep(0.3)
        username_input.send_keys(INSTAGRAM_USERNAME)
        time.sleep(1)
        
        # Clear and fill password
        password_input.clear()
        time.sleep(0.3)
        password_input.send_keys(INSTAGRAM_PASSWORD)
        time.sleep(1)
        
        # Find and click login button
        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
        )
        login_button.click()
        time.sleep(5)
        
        # Check for verification code input (2FA or email/SMS verification)
        try:
            verification_input = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//input[contains(@name, 'verification') or contains(@placeholder, 'code') or contains(@placeholder, 'Code') or contains(@aria-label, 'code')]"))
            )
            if verification_input:
                logging.info("Verification code required - waiting 60 seconds for manual input...")
                print("\n" + "="*60)
                print("⚠️  INSTAGRAM REQUIRES VERIFICATION CODE!")
                print("="*60)
                print("📱 Please enter the verification code in the browser window.")
                print("⏳ Waiting 60 seconds for you to enter the code...")
                print("💡 Browser will stay open - don't close it!")
                print("="*60 + "\n")
                
                # Wait up to 60 seconds and check periodically if code was entered
                max_wait = 60
                for i in range(max_wait):
                    time.sleep(1)
                    try:
                        # Check if we're past verification (logged in)
                        if check_logged_in(driver):
                            print(f"\n✅ Verification code entered successfully! (after {i+1} seconds)")
                            logging.info(f"Verification code entered and login successful after {i+1} seconds")
                            break
                    except:
                        pass
                    
                    # Show countdown every 10 seconds
                    if (i + 1) % 10 == 0:
                        remaining = max_wait - (i + 1)
                        print(f"⏳ Still waiting... {remaining} seconds remaining...")
                
                logging.info("Verification code wait completed")
        except:
            pass  # No verification code required
        
        # Check for "Save Your Login Info" or "Not Now" button
        try:
            not_now_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now') or contains(text(), 'Not now')]"))
            )
            not_now_button.click()
            time.sleep(2)
        except:
            pass
        
        # Check for "Turn on Notifications" or "Not Now"
        try:
            not_now_notif = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now')]"))
            )
            not_now_notif.click()
            time.sleep(2)
        except:
            pass
        
        # Check if login was successful
        time.sleep(2)
        if check_logged_in(driver):
            logging.info("Successfully logged in to Instagram")
            return True
        else:
            # Check if there's an error message
            try:
                error_element = driver.find_element(By.XPATH, "//div[contains(text(), 'incorrect') or contains(text(), 'error')]")
                error_text = error_element.text
                logging.error(f"Login failed: {error_text}")
            except:
                logging.error("Login failed - could not verify login status")
            return False
    except Exception as e:
        logging.error(f"Login error: {e}")
        return False

def auto_report_profile(target_username: str, report_categories: dict, num_reports: int = 5, progress_callback=None) -> dict:
    """
    Automatically report Instagram profile using Selenium.
    WARNING: This may violate Instagram ToS and can result in account ban!
    """
    if not SELENIUM_AVAILABLE:
        return {"success": False, "error": "Selenium not installed. Run: pip install selenium webdriver-manager"}
    
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        return {"success": False, "error": "Instagram credentials not set in .env file"}
    
    results = {"success": True, "reports_sent": 0, "errors": []}
    
    try:
        # Setup Chrome options
        chrome_options = Options()
        # Remove headless mode - Instagram may block headless browsers
        # chrome_options.add_argument("--headless")  # Commented out - Instagram may detect
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Use Chrome profile with saved session to avoid verification code
        chrome_profile_path = os.getenv('CHROME_PROFILE_PATH', None)
        if chrome_profile_path and os.path.exists(chrome_profile_path):
            chrome_options.add_argument(f"--user-data-dir={chrome_profile_path}")
            chrome_options.add_argument("--profile-directory=Default")
            logging.info(f"Using Chrome profile from: {chrome_profile_path}")
        else:
            logging.warning("No Chrome profile found - will need to login each time")
        
        # Create driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        try:
            # Login to Instagram
            if not login_instagram(driver):
                return {"success": False, "error": "Failed to login to Instagram"}
            
            # Navigate to target profile
            profile_url = f"https://www.instagram.com/{target_username}/"
            driver.get(profile_url)
            time.sleep(2)
            
            # Check if still logged in after navigation
            if not check_logged_in(driver):
                logging.warning("Not logged in after navigation, re-logging...")
                if not login_instagram(driver):
                    return {"success": False, "error": "Lost login session"}
                driver.get(profile_url)
                time.sleep(2)
            
            # Report the profile multiple times
            for i in range(num_reports):
                try:
                    # Refresh page before each report to avoid stale elements
                    if i > 0:
                        driver.get(profile_url)
                        time.sleep(1)
                        
                        # Check if still logged in, re-login if needed
                        if not check_logged_in(driver):
                            logging.warning(f"Not logged in before report {i+1}, re-logging...")
                            if not login_instagram(driver):
                                raise Exception("Lost login session")
                            driver.get(profile_url)
                            time.sleep(1)
                    
                    # Try multiple selectors for three dots menu
                    menu_button = None
                    selectors = [
                        (By.XPATH, "//button[contains(@aria-label, 'Options')]"),
                        (By.XPATH, "//button[contains(@aria-label, 'More options')]"),
                        (By.XPATH, "//svg[contains(@aria-label, 'More options')]/ancestor::button"),
                        (By.XPATH, "//button[@type='button']//*[name()='svg' and contains(@aria-label, 'More')]/ancestor::button"),
                    ]
                    
                    for selector_type, selector_value in selectors:
                        try:
                            menu_button = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((selector_type, selector_value))
                            )
                            break
                        except:
                            continue
                    
                    if not menu_button:
                        raise Exception("Could not find menu button")
                    
                    menu_button.click()
                    time.sleep(0.5)
                    
                    # Try multiple selectors for Report button
                    report_button = None
                    report_selectors = [
                        (By.XPATH, "//button[contains(text(), 'Report')]"),
                        (By.XPATH, "//div[contains(text(), 'Report')]/ancestor::button"),
                        (By.XPATH, "//span[contains(text(), 'Report')]/ancestor::button"),
                    ]
                    
                    for selector_type, selector_value in report_selectors:
                        try:
                            report_button = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((selector_type, selector_value))
                            )
                            break
                        except:
                            continue
                    
                    if not report_button:
                        raise Exception("Could not find Report button")
                    
                    report_button.click()
                    time.sleep(0.5)
                    
                    # Select report category - try to find any category button
                    category_button = None
                    try:
                        # Try to find category buttons
                        category_selectors = [
                            (By.XPATH, "//button[contains(text(), 'Hate') or contains(text(), 'Spam') or contains(text(), 'Violence')]"),
                            (By.XPATH, "//div[contains(text(), 'Hate') or contains(text(), 'Spam')]/ancestor::button"),
                        ]
                        
                        for selector_type, selector_value in category_selectors:
                            try:
                                category_button = WebDriverWait(driver, 5).until(
                                    EC.element_to_be_clickable((selector_type, selector_value))
                                )
                                break
                            except:
                                continue
                        
                        if category_button:
                            category_button.click()
                            time.sleep(0.3)
                    except Exception as e:
                        logging.warning(f"Could not select category, continuing: {e}")
                    
                    # Submit report - try multiple selectors
                    submit_button = None
                    submit_selectors = [
                        (By.XPATH, "//button[contains(text(), 'Submit')]"),
                        (By.XPATH, "//button[contains(text(), 'Send')]"),
                        (By.XPATH, "//button[@type='submit']"),
                    ]
                    
                    for selector_type, selector_value in submit_selectors:
                        try:
                            submit_button = driver.find_element(selector_type, selector_value)
                            if submit_button.is_displayed() and submit_button.is_enabled():
                                break
                        except:
                            continue
                    
                    if submit_button:
                        submit_button.click()
                        time.sleep(1)
                        results["reports_sent"] += 1
                        logging.info(f"Report {i+1}/{num_reports} sent successfully for {target_username}")
                    else:
                        # If no submit button, assume report was sent
                        results["reports_sent"] += 1
                        logging.info(f"Report {i+1}/{num_reports} completed (no submit button found) for {target_username}")
                    
                    # Call progress callback if provided
                    if progress_callback:
                        try:
                            progress_callback(i+1, num_reports)
                        except:
                            pass
                    
                    # Shorter delay between reports (faster reporting)
                    time.sleep(random.uniform(2, 4))
                    
                except Exception as e:
                    error_msg = f"Error sending report {i+1}: {str(e)[:100]}"  # Limit error message length
                    results["errors"].append(error_msg)
                    logging.error(f"Error sending report {i+1} for {target_username}: {e}")
                    time.sleep(2)
            
        finally:
            # Don't close browser immediately - give user time
            print("\n⚠️ Browser will close in 3 seconds...")
            time.sleep(3)
            try:
                driver.quit()
            except:
                pass
            
    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        logging.error(f"Auto-report error: {e}")
    
    return results

# Store pending report requests
pending_reports = {}

@bot.message_handler(commands=['massreport'])
def mass_report_command(message):
    """Command to mass report a profile - asks for number of reports interactively."""
    user_id = message.chat.id
    
    # Only admin can use auto-report
    if str(user_id) != str(ADMIN_ID):
        bot.reply_to(message, "❌ Only admin can use this command.")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "📝 Usage: /massreport <username>\n\nExample: /massreport instagram\n\nBot will ask you how many reports to send.")
        return
    
    target_username = parts[1]
    
    # Store pending report request
    pending_reports[user_id] = target_username
    
    # Ask for number of reports
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("5 reports", callback_data=f'num_5'),
        telebot.types.InlineKeyboardButton("10 reports", callback_data=f'num_10')
    )
    markup.add(
        telebot.types.InlineKeyboardButton("20 reports", callback_data=f'num_20'),
        telebot.types.InlineKeyboardButton("30 reports", callback_data=f'num_30')
    )
    markup.add(
        telebot.types.InlineKeyboardButton("50 reports", callback_data=f'num_50'),
        telebot.types.InlineKeyboardButton("Custom", callback_data=f'num_custom')
    )
    
    bot.reply_to(message, f"🎯 Target: @{target_username}\n\n📊 How many reports do you want to send?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('num_'))
def handle_num_reports(call):
    """Handle number of reports selection."""
    user_id = call.from_user.id
    
    if str(user_id) != str(ADMIN_ID):
        try:
            bot.answer_callback_query(call.id, text="Only admin can use this feature!", show_alert=False)
        except:
            pass
        return
    
    if user_id not in pending_reports:
        try:
            bot.answer_callback_query(call.id, text="No pending report request. Use /massreport <username> first.", show_alert=False)
        except:
            pass
        return
    
    target_username = pending_reports[user_id]
    
    if call.data == 'num_custom':
        try:
            bot.answer_callback_query(call.id, text="Please send the number of reports (1-50)", show_alert=False)
        except:
            pass
        bot.send_message(user_id, f"📝 Please send the number of reports you want to send for @{target_username} (1-50):")
        pending_reports[user_id] = (target_username, 'custom')
        return
    
    # Extract number from callback data
    num_reports = int(call.data.replace('num_', ''))
    
    # Remove from pending
    del pending_reports[user_id]
    
    try:
        bot.answer_callback_query(call.id, text=f"Starting {num_reports} reports...", show_alert=False)
    except:
        pass
    
    bot.send_message(user_id, f"🚀 Starting mass report for @{target_username}...\n📊 Reports to send: {num_reports}\n⚡ Faster mode enabled\n⚠️ This may take a few minutes.")
    
    # Get profile info and reports
    profile_info = get_public_instagram_info(target_username)
    if not profile_info:
        bot.send_message(user_id, f"❌ Could not fetch profile info for {target_username}")
        return
    
    reports = analyze_profile(profile_info)
    
    # Start auto-reporting in background thread
    def report_thread():
        status_msg = bot.send_message(user_id, f"⏳ Processing... 0/{num_reports} reports sent")
        result = auto_report_profile(target_username, reports, num_reports=num_reports)
        
        if result["success"]:
            success_count = result["reports_sent"]
            failed_count = num_reports - success_count
            
            msg = f"✅ *Mass Report Completed!*\n\n"
            msg += f"🎯 Target: @{target_username}\n"
            msg += f"✅ Successfully sent: *{success_count}* reports\n"
            msg += f"❌ Failed: *{failed_count}* reports\n"
            msg += f"📊 Success rate: *{(success_count/num_reports*100):.1f}%*\n"
            
            if result.get("errors") and len(result["errors"]) > 0:
                msg += f"\n⚠️ Errors encountered: {len(result['errors'])}"
                if len(result["errors"]) <= 3:
                    for error in result["errors"]:
                        msg += f"\n• {error[:50]}..."
            
            bot.edit_message_text(msg, user_id, status_msg.message_id, parse_mode='Markdown')
        else:
            bot.edit_message_text(
                f"❌ *Auto-report failed*\n\nError: {result.get('error', 'Unknown error')}",
                user_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
    
    Thread(target=report_thread, daemon=True).start()

@bot.message_handler(func=lambda message: message.chat.id in pending_reports and isinstance(pending_reports.get(message.chat.id), tuple) and pending_reports[message.chat.id][1] == 'custom')
def handle_custom_num_reports(message):
    """Handle custom number of reports input."""
    user_id = message.chat.id
    
    if str(user_id) != str(ADMIN_ID):
        return
    
    try:
        num_reports = int(message.text.strip())
        if num_reports < 1 or num_reports > 50:
            bot.reply_to(message, "⚠️ Number of reports must be between 1 and 50. Please try again:")
            return
    except ValueError:
        bot.reply_to(message, "❌ Invalid number. Please send a number between 1 and 50:")
        return
    
    target_username = pending_reports[user_id][0]
    del pending_reports[user_id]
    
    bot.reply_to(message, f"🚀 Starting mass report for @{target_username}...\n📊 Reports to send: {num_reports}\n⚡ Faster mode enabled\n⚠️ This may take a few minutes.")
    
    # Get profile info and reports
    profile_info = get_public_instagram_info(target_username)
    if not profile_info:
        bot.send_message(user_id, f"❌ Could not fetch profile info for {target_username}")
        return
    
    reports = analyze_profile(profile_info)
    
    # Start auto-reporting in background thread
    def report_thread():
        status_msg = bot.send_message(user_id, f"⏳ Processing... 0/{num_reports} reports sent")
        result = auto_report_profile(target_username, reports, num_reports=num_reports)
        
        if result["success"]:
            success_count = result["reports_sent"]
            failed_count = num_reports - success_count
            
            msg = f"✅ *Mass Report Completed!*\n\n"
            msg += f"🎯 Target: @{target_username}\n"
            msg += f"✅ Successfully sent: *{success_count}* reports\n"
            msg += f"❌ Failed: *{failed_count}* reports\n"
            msg += f"📊 Success rate: *{(success_count/num_reports*100):.1f}%*\n"
            
            if result.get("errors") and len(result["errors"]) > 0:
                msg += f"\n⚠️ Errors encountered: {len(result['errors'])}"
                if len(result["errors"]) <= 3:
                    for error in result["errors"]:
                        msg += f"\n• {error[:50]}..."
            
            bot.edit_message_text(msg, user_id, status_msg.message_id, parse_mode='Markdown')
        else:
            bot.edit_message_text(
                f"❌ *Auto-report failed*\n\nError: {result.get('error', 'Unknown error')}",
                user_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
    
    Thread(target=report_thread, daemon=True).start()

@bot.callback_query_handler(func=lambda call: call.data.startswith('report_'))
def handle_report_callback(call):
    """Handle auto-report button click."""
    user_id = call.from_user.id
    
    # Only admin can use auto-report
    if str(user_id) != str(ADMIN_ID):
        try:
            bot.answer_callback_query(call.id, text="Only admin can use auto-report feature!", show_alert=False)
        except:
            pass  # Ignore if callback query expired
        return
    
    # Parse callback data: report_username_5 or report_username
    callback_data = call.data.replace('report_', '')
    
    # Try to find number at the end (last part after last underscore)
    parts = callback_data.split('_')
    
    # Check if last part is a number
    if len(parts) > 1 and parts[-1].isdigit():
        num_reports = int(parts[-1])
        target_username = '_'.join(parts[:-1])  # Join all parts except last
    else:
        num_reports = 5
        target_username = callback_data  # Use entire string as username
    
    # Answer callback query (with error handling for expired queries)
    try:
        bot.answer_callback_query(call.id, text=f"Starting {num_reports} reports for {target_username}...", show_alert=False)
    except Exception as e:
        logging.warning(f"Could not answer callback query (may be expired): {e}")
        # Continue anyway - send message to user
    
    bot.send_message(user_id, f"🚀 Starting mass report for @{target_username}...\n📊 Reports to send: {num_reports}\n⚠️ This may take a few minutes.")
    
    # Get profile info and reports
    profile_info = get_public_instagram_info(target_username)
    if not profile_info:
        bot.send_message(user_id, f"❌ Could not fetch profile info for {target_username}")
        return
    
    reports = analyze_profile(profile_info)
    
    # Start auto-reporting in background thread
    def report_thread():
        status_msg = bot.send_message(user_id, f"⏳ Processing... 0/{num_reports} reports sent")
        result = auto_report_profile(target_username, reports, num_reports=num_reports)
        
        if result["success"]:
            success_count = result["reports_sent"]
            failed_count = num_reports - success_count
            
            msg = f"✅ *Mass Report Completed!*\n\n"
            msg += f"🎯 Target: @{target_username}\n"
            msg += f"✅ Successfully sent: *{success_count}* reports\n"
            msg += f"❌ Failed: *{failed_count}* reports\n"
            msg += f"📊 Success rate: *{(success_count/num_reports*100):.1f}%*\n"
            
            if result.get("errors") and len(result["errors"]) > 0:
                msg += f"\n⚠️ Errors encountered: {len(result['errors'])}"
                if len(result["errors"]) <= 3:
                    for error in result["errors"]:
                        msg += f"\n• {error[:50]}..."
            
            bot.edit_message_text(msg, user_id, status_msg.message_id, parse_mode='Markdown')
        else:
            bot.edit_message_text(
                f"❌ *Auto-report failed*\n\nError: {result.get('error', 'Unknown error')}",
                user_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
    
    Thread(target=report_thread, daemon=True).start()

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if str(message.chat.id) != ADMIN_ID:
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    broadcast_message = message.text[len("/broadcast "):].strip()
    if not broadcast_message:
        bot.reply_to(message, "Please provide a message to broadcast.")
        return

    users = get_all_users()
    for user in users:
        try:
            bot.send_message(user, broadcast_message)
        except Exception as e:
            logging.error(f"Failed to send message to {user}: {e}")

@bot.message_handler(commands=['users'])
def list_users(message):
    if str(message.chat.id) != ADMIN_ID:
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    users = get_all_users()
    if users:
        user_list = "\n".join([f"User ID: {user_id}" for user_id in users])
        bot.reply_to(message, f"List of Users:\n{user_list}")
    else:
        bot.reply_to(message, "No users found.")

@bot.message_handler(commands=['remove_user'])
def remove_user_command(message):
    if str(message.chat.id) != ADMIN_ID:
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    user_id = message.text.split()[1:]  # Get user ID from command
    if not user_id:
        bot.reply_to(message, "Please provide a user ID.")
        return

    user_id = int(user_id[0])
    remove_user(user_id)
    bot.reply_to(message, f"User ID {user_id} has been removed.")

@bot.message_handler(commands=['restart'])
def restart_bot(message):
    if str(message.chat.id) != ADMIN_ID:
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    bot.reply_to(message, "Bot is restarting...")
    logging.info("Bot is restarting...")
    os.execv(sys.executable, ['python'] + sys.argv)

@bot.callback_query_handler(func=lambda call: call.data == 'reload')
def reload_callback(call):
    user_id = call.from_user.id
    try:
        if is_user_in_channel(user_id):
            bot.answer_callback_query(call.id, text="You are now authorized to use the bot!", show_alert=False)
            bot.send_message(user_id, "You are now authorized to use the bot. Use /getmeth <username> to analyze an Instagram profile.")
        else:
            bot.answer_callback_query(call.id, text="You are not a member of the channel yet. Please join the channel first.", show_alert=False)
    except Exception as e:
        logging.warning(f"Error handling reload callback: {e}")
        # Try to send message anyway
        try:
            bot.send_message(user_id, "You are now authorized to use the bot. Use /getmeth <username> to analyze an Instagram profile.")
        except:
            pass

@bot.callback_query_handler(func=lambda call: call.data == 'help')
def help_callback(call):
    help_text = "Here's how you can use this bot:\n\n"
    help_text += "/getmeth <username> - Analyze an Instagram profile.\n"
    help_text += "Make sure you are a member of the channel to use this bot."
    
    # Escape special characters for MarkdownV2
    help_text = escape_markdown_v2(help_text)

    try:
        bot.answer_callback_query(call.id, text="Help information sent!", show_alert=False)
    except Exception as e:
        logging.warning(f"Error answering help callback: {e}")
    
    try:
        bot.send_message(call.from_user.id, help_text, parse_mode='MarkdownV2')
    except Exception as e:
        logging.error(f"Error sending help message: {e}")

if __name__ == "__main__":
    print("Starting the bot...")
    logging.info("Bot started.")
    
    # Check if API_TOKEN is set
    if not API_TOKEN:
        print("ERROR: API_TOKEN is not set in .env file!")
        logging.error("API_TOKEN is not set")
        sys.exit(1)
    
    # Test bot connection
    try:
        bot_info = bot.get_me()
        print(f"✅ Bot connected successfully!")
        print(f"   Bot username: @{bot_info.username}")
        print(f"   Bot name: {bot_info.first_name}")
        logging.info(f"Bot connected: @{bot_info.username}")
    except Exception as e:
        print(f"❌ Error connecting to Telegram: {e}")
        logging.error(f"Error connecting to Telegram: {e}")
        sys.exit(1)
    
    print("🔄 Starting bot polling...")
    print("📡 Flask server running on http://0.0.0.0:8080")
    print("💬 Bot is ready to receive messages!")
    print("Press Ctrl+C to stop the bot.\n")
    
    # Start the bot polling in a separate thread
    t = Thread(target=bot.polling, daemon=True)
    t.start()
    
    # Keep main thread alive
    try:
        t.join()
    except KeyboardInterrupt:
        print("\n🛑 Stopping bot...")
        logging.info("Bot stopped by user.")
        sys.exit(0)


