# slack-n8n-websocket-proxy

A Python application that connects to Slack via WebSocket (Socket Mode) and forwards events to n8n webhook triggers in real-time. This proxy allows you to receive Slack events in n8n without exposing your n8n instance to the internet.

## Features

- **Real-time WebSocket connection** to Slack using Socket Mode
- **Comprehensive event handling** for messages, reactions, slash commands, and interactive events
- **Native Slack format preservation** - events are forwarded in the exact format n8n expects
- **User and channel enrichment** - automatically fetches user names, emails, and channel information
- **Robust error handling** with detailed logging
- **Async/await architecture** for high performance

## Supported Events

- **Messages** - All channel and direct messages with user/channel details
- **Reactions** - Emoji reactions added to messages
- **Member joins** - When users join channels
- **Slash commands** - Custom slash command interactions
- **Interactive events** - Button clicks, menu selections, etc.
- **Custom events** - Easily extend to support additional Slack events

## Prerequisites

- Python 3.7+
- Slack workspace with admin permissions
- n8n instance with webhook capabilities
- Slack app with Socket Mode enabled

## Installation

1. **Clone or download the script**
   ```bash
   # Save the Python script as slack_n8n_proxy.py
   ```

2. **Install required dependencies**
   ```bash
   pip install slack_sdk aiohttp asyncio
   ```

## Slack App Setup

### 1. Create a Slack App
1. Go to [Slack API](https://api.slack.com/apps)
2. Click "Create New App" → "From scratch"
3. Name your app and select your workspace

### 2. Enable Socket Mode
1. Go to **Socket Mode** in your app settings
2. Enable Socket Mode
3. Generate an **App-Level Token** with `connections:write` scope
4. Save the token (starts with `xapp-`)

### 3. Configure Bot Token
1. Go to **OAuth & Permissions**
2. Add the following Bot Token Scopes:
   - `channels:history`
   - `channels:read`
   - `chat:write`
   - `groups:history`
   - `groups:read`
   - `im:history`
   - `mpim:history`
   - `reactions:read`
   - `users:read`
   - `users:read.email`
3. Install the app to your workspace
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 4. Subscribe to Events
1. Go to **Event Subscriptions**
2. Enable Events
3. Subscribe to these bot events:
   - `message.channels`
   - `message.groups`
   - `message.im`
   - `message.mpim`
   - `reaction_added`
   - `member_joined_channel`
4. Add any additional events you need

### 5. Enable Interactive Components (Optional)
1. Go to **Interactivity & Shortcuts**
2. Enable Interactivity if you want to handle button clicks, menus, etc.

## n8n Setup

1. **Create a new workflow** in n8n
2. **Add a Slack Trigger node** (not a generic Webhook node)
3. **Configure the trigger**:
   - Set the webhook URL (you'll use this in the Python app)
   - Configure any event filtering as needed
4. **Copy the webhook URL** from the trigger node

## Configuration

Set the following environment variables:

```bash
# Required environment variables
export SLACK_BOT_TOKEN="xoxb-your-bot-user-oauth-token"
export SLACK_APP_TOKEN="xapp-your-app-level-token"  
export N8N_WEBHOOK_URL="https://your-n8n-instance.com/webhook/slack-trigger-url"
```

### Alternative: Hardcode in Script
You can also modify the script to hardcode these values:
```python
SLACK_BOT_TOKEN = "xoxb-your-token-here"
SLACK_APP_TOKEN = "xapp-your-token-here"  
N8N_WEBHOOK_URL = "https://your-n8n-webhook-url"
```

## Usage

### Running the Proxy

```bash
python slack_n8n_proxy.py
```

### Expected Output
```
2024-01-20 10:30:00,123 - __main__ - INFO - Starting Slack WebSocket connection...
2024-01-20 10:30:01,456 - __main__ - INFO - Slack proxy is running. Press Ctrl+C to stop.
2024-01-20 10:30:15,789 - __main__ - INFO - Received event: message
2024-01-20 10:30:15,790 - __main__ - INFO - Processed message from John Doe in #general: Hello world!...
```

### Stopping the Proxy
Press `Ctrl+C` to gracefully shutdown the proxy.

## Event Data Structure

The proxy forwards events to n8n in Slack's native webhook format:

### Message Event Example
```json
{
  "token": "proxy-token",
  "team_id": "T1234567890",
  "api_app_id": "proxy-app",
  "event": {
    "type": "message",
    "channel": "C1234567890",
    "user": "U1234567890", 
    "text": "Hello world!",
    "ts": "1234567890.123456"
  },
  "type": "event_callback",
  "event_id": "proxy-1234567890",
  "event_time": 1234567890
}
```

### Reaction Event Example
```json
{
  "token": "proxy-token",
  "team_id": "T1234567890",
  "api_app_id": "proxy-app",
  "event": {
    "type": "reaction_added",
    "user": "U1234567890",
    "reaction": "thumbsup",
    "item": {
      "type": "message",
      "channel": "C1234567890",
      "ts": "1234567890.123456"
    }
  },
  "type": "event_callback",
  "event_id": "proxy-1234567891",
  "event_time": 1234567891
}
```

## Customization

### Adding New Event Types
To handle additional Slack events:

1. **Subscribe to the event** in your Slack app's Event Subscriptions
2. **Add a handler** in the `handle_events_api` method:
   ```python
   elif event_type == "your_new_event":
       await self.process_your_new_event(event, payload)
   ```
3. **Create the processor method**:
   ```python
   async def process_your_new_event(self, event: Dict[str, Any], full_payload: Dict[str, Any]):
       # Process your event
       await self.send_to_n8n(event_data, full_payload)
   ```

### Filtering Events
To filter specific events before sending to n8n:
```python
# In process_message_event method
if "ignore" in text.lower():
    logger.info("Ignoring message with 'ignore' keyword")
    return

# Continue with normal processing...
```

### Custom Data Enrichment
Add custom data to events before forwarding:
```python
# In process_message_event method
message_data.update({
    "custom_field": "custom_value",
    "processed_at": datetime.utcnow().isoformat(),
    "environment": "production"
})
```

## Troubleshooting

### Common Issues

**"Missing required environment variables" Error**
- Ensure all three environment variables are set correctly
- Check that tokens don't have extra spaces or quotes

**"Cannot read properties of undefined (reading 'type')" in n8n**
- Make sure you're using a **Slack Trigger** node, not a generic Webhook node
- Verify the webhook URL is correct

**Connection timeouts or failures**
- Check your internet connection
- Verify Slack app tokens are valid and have correct permissions
- Ensure Socket Mode is enabled in your Slack app

**Events not appearing in n8n**
- Check the Python script logs for errors
- Verify the n8n webhook URL is accessible
- Test the webhook manually with curl

**Bot not receiving messages**
- Ensure the bot is added to channels you want to monitor
- Check that required OAuth scopes are granted
- Verify Event Subscriptions are properly configured

### Debug Mode
Enable debug logging by changing the logging level:
```python
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Testing the Webhook
Test your n8n webhook directly:
```bash
curl -X POST "YOUR_N8N_WEBHOOK_URL" \
     -H "Content-Type: application/json" \
     -d '{
       "token": "test-token",
       "team_id": "T12345",
       "type": "event_callback",
       "event": {
         "type": "message",
         "text": "Test message",
         "user": "U12345",
         "channel": "C12345"
       }
     }'
```

## Security Considerations

- Keep your Slack tokens secure and never commit them to version control
- Use environment variables or secure secret management
- Consider running the proxy in a secure environment
- Regularly rotate your Slack app tokens
- Monitor the logs for any suspicious activity

## Performance

- The proxy uses async/await for high performance
- WebSocket connection is maintained automatically
- Failed webhook deliveries are logged but don't stop processing
- Memory usage is minimal as events are forwarded immediately

## License

This project is provided as-is for educational and practical purposes. Modify and distribute as needed.

## Contributing

Feel free to extend this proxy for additional Slack events or n8n integrations. Common enhancements include:

- Database logging of events
- Webhook retry logic with exponential backoff
- Multiple n8n endpoint support
- Event transformation and filtering rules
- Metrics and monitoring integration
- Docker containerization

## Support

For issues related to:
- **Slack API**: Check [Slack API Documentation](https://api.slack.com/)
- **n8n**: Check [n8n Documentation](https://docs.n8n.io/)
- **This proxy**: Review the troubleshooting section above
