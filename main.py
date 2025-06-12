import os
import requests
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    JoinEvent,
    LeaveEvent
)
import logging
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- 1. Load Environment Variables ---
load_dotenv()

# --- 2. Configuration ---
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')

# --- 3. Initialize LINE Bot API and Webhook Handler ---
if not all([LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, RAPIDAPI_KEY]):
    raise ValueError(
        "Missing required environment variables. "
        "Please check your .env file or deployment settings."
    )

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
line_bot_api = MessagingApi(ApiClient(configuration))

# --- 4. Initialize Flask Application ---
app = Flask(__name__)

# --- 5. Webhook Endpoint for LINE ---
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    logger.debug("Request Headers:")
    for header, value in request.headers.items():
        logger.debug(f"{header}: {value}")
    
    if signature is None:
        logger.error("Missing X-Line-Signature in headers")
        abort(400, "X-Line-Signature header missing.")

    body = request.get_data(as_text=True)
    try:
        body_json = json.loads(body)
        logger.info("Webhook Payload:")
        logger.info(json.dumps(body_json, indent=2, ensure_ascii=False))
    except json.JSONDecodeError:
        logger.warning(f"Could not parse webhook body as JSON: {body[:200]}...")

    try:
        handler.handle(body, signature)
        logger.info("Successfully processed webhook")
    except InvalidSignatureError:
        logger.error(f"Invalid signature. Received signature: {signature}")
        abort(400, "Invalid signature")
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        abort(500, f"Internal server error: {e}")

    return 'OK'

def detect_language(text):
    # Count characters in different scripts
    english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    thai_chars = sum(1 for c in text if '\u0E00' <= c <= '\u0E7F')  # Thai Unicode range
    myanmar_chars = sum(1 for c in text if '\u1000' <= c <= '\u109F')  # Myanmar Unicode range
    
    total_chars = sum(1 for c in text if c.isalpha() or '\u0E00' <= c <= '\u0E7F' or '\u1000' <= c <= '\u109F')
    
    if total_chars == 0:
        return 'en'  # Default to English if no clear script is detected
    
    # Calculate ratios
    eng_ratio = english_chars / total_chars if total_chars > 0 else 0
    thai_ratio = thai_chars / total_chars if total_chars > 0 else 0
    myanmar_ratio = myanmar_chars / total_chars if total_chars > 0 else 0
    
    # Determine dominant script
    if eng_ratio > 0.7:
        return 'en'
    elif thai_ratio > 0.7:
        return 'th'
    elif myanmar_ratio > 0.7:
        return 'my'
    else:
        return 'en'  # Default to English if no clear dominant script

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_message = event.message.text
    user_id = event.source.user_id
    timestamp = datetime.fromtimestamp(event.timestamp / 1000)
    
    logger.info("Received Message Details:")
    logger.info(f"Timestamp: {timestamp}")
    logger.info(f"User ID: {user_id}")
    logger.info(f"Message: '{user_message}'")
    logger.info(f"Reply Token: {event.reply_token}")
    
    reply_text = ""

    # --- Basic Command Handling ---
    if user_message.lower().startswith('hello'):
        reply_text = "👋 Hello! How can I help you today?"
        logger.debug(f"Sending greeting response to user {user_id}")
    elif user_message.lower().startswith('help'):
        reply_text = (
            "Here's what I can do:\n"
            "1. Say 'hello' to greet me\n"
            "2. Ask for 'help' to see this menu\n"
            "3. Type English text for Thai/Myanmar translation\n"
            "4. Type Thai text for English/Myanmar translation\n"
            "5. Type Myanmar text for English/Thai translation!"
        )
        logger.debug(f"Sending help menu to user {user_id}")
    else:
        # --- Translation Logic ---
        url = "https://ai-translate.p.rapidapi.com/translate"
        
        # Detect source language
        source_lang = detect_language(user_message)
        
        # Determine target languages based on source
        if source_lang == 'en':
            translations_needed = ['th', 'my']
        elif source_lang == 'th':
            translations_needed = ['en', 'my']
        else:  # Myanmar
            translations_needed = ['en', 'th']
        
        translated_texts = []
        
        for target_lang in translations_needed:
            try:
                payload = {
                    "texts": [user_message],
                    "tl": target_lang,
                    "sl": source_lang
                }
                
                headers = {
                    "x-rapidapi-key": RAPIDAPI_KEY,
                    "x-rapidapi-host": "ai-translate.p.rapidapi.com",
                    "Content-Type": "application/json"
                }

                logger.debug(f"Sending translation request to {url} for {target_lang}")
                logger.debug(f"Headers: {headers}")
                logger.debug(f"Payload: {payload}")
                
                rapidapi_response = requests.post(url, json=payload, headers=headers, timeout=10)
                
                if rapidapi_response.status_code == 200:
                    response_json = rapidapi_response.json()
                    if 'texts' in response_json and response_json['texts']:
                        translated_text = response_json['texts'][0]
                        lang_emoji = "🇬🇧" if target_lang == 'en' else "🇹🇭" if target_lang == 'th' else "🇲🇲"
                        translated_texts.append(f"{lang_emoji} {translated_text}")
                        
            except Exception as e:
                logger.error(f"Translation error for {target_lang}: {str(e)}")
                translated_texts.append(f"Error translating to {target_lang}")
        
        if translated_texts:
            reply_text = "\n\n".join(translated_texts)
        else:
            reply_text = "Sorry, translation failed. Please try again."

    if reply_text:  # Only send if we have a reply
        try:
            # Validate reply text is not empty
            if not reply_text.strip():
                logger.error(f"Empty reply text for user {user_id}")
                return

            # Clean up any potential null characters or invalid whitespace
            reply_text = reply_text.strip()

            logger.info(f"Sending response to user {user_id}: '{reply_text}'")
            
            # Create message object directly
            message = TextMessage(text=reply_text)
            
            request = ReplyMessageRequest(
                replyToken=event.reply_token,
                messages=[message]
            )
            
            line_bot_api.reply_message(request)
            logger.info(f"Successfully sent response to user {user_id}")
        except Exception as reply_error:
            logger.error(f"Failed to send response to user {user_id}: {str(reply_error)}", exc_info=True)

# --- NEW: Handler for when the bot joins a group/room ---
@handler.add(JoinEvent)
def handle_join(event):
    """
    This function is called when the bot is added to a group chat or multi-person chat.
    """
    try:
        # event.source will tell you if it's a group or room
        if event.source.type == 'group':
            group_id = event.source.group_id
            reply_text = "Hello everyone! 👋 Thanks for adding me to this group. I'm a Thai-English translation bot.\n\nTry sending me:\n1. 'hello' - for a greeting\n2. 'help' - to see this menu again\n3. Any Thai text - I'll translate it to English!"
            logger.info(f"Bot joined group: {group_id}")
        elif event.source.type == 'room':
            room_id = event.source.room_id
            reply_text = "Hello everyone! 👋 Thanks for adding me to this room. I'm a Thai-English translation bot.\n\nTry sending me:\n1. 'hello' - for a greeting\n2. 'help' - to see this menu again\n3. Any Thai text - I'll translate it to English!"
            logger.info(f"Bot joined room: {room_id}")
        else:
            reply_text = "Hello! 👋 Thanks for adding me. I'm a translation bot."
            logger.info("Bot joined unknown chat type.")

        request = ReplyMessageRequest(
            replyToken=event.reply_token,
            messages=[{
                "type": "text",
                "text": reply_text
            }]
        )
        
        line_bot_api.reply_message(request)
        logger.info(f"Successfully sent join message for event type: {event.source.type}")
    except Exception as e:
        logger.error(f"Failed to send join message: {str(e)}", exc_info=True)

# --- 7. Run the Flask Application (for local development) ---
if __name__ == "__main__":
    # Check if running in production (Render) or development
    is_production = os.environ.get('RENDER', False)
    
    if is_production:
        # Production settings
        app.run(host="0.0.0.0", port=10000)
    else:
        # Development settings
        app.run(host="0.0.0.0", port=8000, debug=True)