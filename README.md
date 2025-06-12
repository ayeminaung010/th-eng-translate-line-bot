# LINE Multi-Language Translation Bot

A LINE messaging bot that provides real-time translation between English, Thai, and Myanmar (Burmese) languages using the AI Translate API.

## Features

- **Multi-Language Support**:
  - English ↔️ Thai
  - English ↔️ Myanmar
  - Thai ↔️ Myanmar
  - Automatic language detection
  - Emoji flags to indicate languages (🇬🇧 🇹🇭 🇲🇲)

- **Group Chat Support**:
  - Works in both private and group chats
  - Stays in groups when added
  - Processes messages from all group members

- **Basic Commands**:
  - `hello` - Get a greeting message
  - `help` - View available commands and features

## Setup

### Prerequisites

- Python 3.x
- Flask
- LINE Messaging API SDK v3
- ngrok (for local development)
- RapidAPI account (for AI Translate API)

### Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_CHANNEL_SECRET=your_line_channel_secret
RAPIDAPI_KEY=your_rapidapi_key
```

### Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd translate_line_bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Start the server:
```bash
python main.py
```

4. (For local development) Start ngrok:
```bash
ngrok http 8000
```

5. Update your LINE Bot webhook URL with the ngrok HTTPS URL + `/callback`

## Usage

1. Add the bot to LINE using the QR code or Bot ID
2. Send a message in any supported language (English, Thai, or Myanmar)
3. The bot will automatically detect the language and provide translations to the other two languages
4. Each translation will be prefixed with its corresponding flag emoji

## Technical Details

- **Language Detection**: Uses Unicode character ranges to detect the source language
- **Translation API**: Utilizes RapidAPI's AI Translate endpoint
- **Webhook Handler**: Processes LINE messaging events using Flask
- **Error Handling**: Includes comprehensive error handling and logging

## Error Handling

The bot includes robust error handling for:
- Invalid messages
- API timeouts
- Rate limiting
- Network issues
- Message length limits

## Logging

Comprehensive logging is implemented with:
- Request/response details
- Translation attempts
- Error tracking
- User interactions
- API responses

## Security

- Environment variables for sensitive data
- Webhook signature validation
- Rate limiting protection
- Error message sanitization

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## License

[Your chosen license]

## Acknowledgments

- LINE Messaging API
- RapidAPI AI Translate
- Flask framework
- Python LINE Bot SDK 