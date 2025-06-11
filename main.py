import os
import requests
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
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

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

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

@handler.add(MessageEvent, message=TextMessage)
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
        url = "https://microsoft-translator-text-api3.p.rapidapi.com/largetranslate"
        
        payload = {
            "sep": "|",
            "text": user_message
        }
        
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": "microsoft-translator-text-api3.p.rapidapi.com",
            "Content-Type": "application/json"
        }

        params = {
            "to": "en",
            "from": "th"
        }

        try:
            logger.debug(f"Sending translation request to {url}")
            logger.debug(f"Headers: {headers}")
            logger.debug(f"Params: {params}")
            logger.debug(f"Payload: {payload}")
            
            rapidapi_response = requests.post(url, json=payload, headers=headers, params=params, timeout=10)
            
            logger.debug(f"Response Status Code: {rapidapi_response.status_code}")
            logger.debug(f"Response Headers: {dict(rapidapi_response.headers)}")
            
            try:
                response_json = rapidapi_response.json()
                logger.debug(f"Response JSON: {json.dumps(response_json, indent=2, ensure_ascii=False)}")
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON. Raw response: {rapidapi_response.text}")
                raise
            
            if 'translation' in response_json:
                translated_text = response_json['translation']
                reply_text = f"🔤 Original: {user_message}\n📝 Translation: {translated_text}"
                logger.info(f"Translated for {user_id}: '{user_message}' -> '{translated_text}'")
            else:
                logger.error(f"No translations in response: {response_json}")
                reply_text = "Sorry, I couldn't find the translation in the response."

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

    try:
        logger.info(f"Sending response to user {user_id}: '{reply_text}'")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
        logger.info(f"Successfully sent response to user {user_id}")
    except Exception as reply_error:
        logger.error(f"Failed to send response to user {user_id}: {str(reply_error)}", exc_info=True)

# --- 7. Run the Flask Application (for local development) ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)