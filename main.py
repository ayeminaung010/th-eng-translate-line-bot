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
        reply_text = "Here's what I can do:\n1. Say 'hello' to greet me\n2. Ask for 'help' to see this menu\n3. Type any Thai text for English translation!"
        logger.debug(f"Sending help menu to user {user_id}")
    else:
        # --- Translation Logic ---
        url = "https://ai-translate.p.rapidapi.com/translate"
        
        payload = {
            "texts": [user_message],
            "tl": "en",
            "sl": "th"
        }
        
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": "ai-translate.p.rapidapi.com",
            "Content-Type": "application/json"
        }

        try:
            logger.debug(f"Sending translation request to {url}")
            logger.debug(f"Headers: {headers}")
            logger.debug(f"Payload: {payload}")
            
            rapidapi_response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            logger.debug(f"Response Status Code: {rapidapi_response.status_code}")
            logger.debug(f"Response Headers: {dict(rapidapi_response.headers)}")
            
            try:
                response_json = rapidapi_response.json()
                logger.debug("=== Translation API Response ===")
                logger.debug(f"Full Response Data: {json.dumps(response_json, indent=2, ensure_ascii=False)}")
                logger.debug("=== Response Structure ===")
                logger.debug(f"Response Keys: {list(response_json.keys())}")
                if isinstance(response_json, dict):
                    for key, value in response_json.items():
                        logger.debug(f"Key: {key}, Type: {type(value)}, Value: {value}")
                logger.debug("=== End Response Data ===")
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON. Raw response: {rapidapi_response.text}")
                logger.error("=== Raw Response Content ===")
                logger.error(rapidapi_response.text)
                logger.error("=== End Raw Response ===")
                reply_text = "Sorry, there was an error processing the translation. Please try again with a shorter text."
                raise

            if 'texts' in response_json and response_json['texts']:
                translated_text = response_json['texts'][0]
                if len(translated_text) > 2000:  # Set a reasonable limit
                    reply_text = "⚠️ Sorry, the translated text is too long. Please try with a shorter message (less than 2000 characters)."
                    logger.warning(f"Translation exceeded length limit for user {user_id}")
                else:
                    reply_text = f"{translated_text}"
                logger.info(f"Translated for {user_id}: '{user_message}' -> '{translated_text}'")
            else:
                logger.error(f"No translations in response: {response_json}")
                reply_text = "Sorry, I couldn't translate your message. Please try again."

        except requests.exceptions.Timeout:
            reply_text = "Sorry, the translation service is taking too long to respond. Please try again."
            logger.error("Translation API timeout")
        except requests.exceptions.HTTPError as http_err:
            error_msg = ""
            try:
                error_details = http_err.response.json()
                error_msg = error_details.get('error', {}).get('message', 'Unknown error')
            except:
                error_msg = str(http_err)
            reply_text = f"Translation error: {error_msg}"
            logger.error(f"HTTP error from translation API: {error_msg}")
        except Exception as e:
            reply_text = "Sorry, an error occurred during translation. Please try again."
            logger.error(f"Translation error: {str(e)}", exc_info=True)

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
    app.run(host="0.0.0.0", port=8000, debug=True)