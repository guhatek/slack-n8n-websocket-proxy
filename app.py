import asyncio
import json
import logging
import os
import aiohttp
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SlackN8nProxy:
    def __init__(self, slack_bot_token: str, slack_app_token: str, n8n_webhook_url: str):
        """
        Initialize the Slack to n8n proxy.
        
        Args:
            slack_bot_token: Slack Bot User OAuth Token (starts with xoxb-)
            slack_app_token: Slack App-Level Token (starts with xapp-)
            n8n_webhook_url: The n8n webhook URL to send messages to
        """
        self.slack_web_client = AsyncWebClient(token=slack_bot_token)
        self.socket_mode_client = SocketModeClient(
            app_token=slack_app_token,
            web_client=self.slack_web_client
        )
        self.n8n_webhook_url = n8n_webhook_url
        self.session = None
        
        # Register event handlers
        self.socket_mode_client.socket_mode_request_listeners.append(self.handle_socket_mode_request)
    
    async def start(self):
        """Start the proxy service."""
        try:
            # Create aiohttp session for webhook requests
            self.session = aiohttp.ClientSession()
            
            logger.info("Starting Slack WebSocket connection...")
            await self.socket_mode_client.connect()
            
            logger.info("Slack proxy is running. Press Ctrl+C to stop.")
            # Keep the connection alive
            await asyncio.Event().wait()
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal. Shutting down...")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources."""
        if self.session:
            await self.session.close()
        await self.socket_mode_client.close()
        logger.info("Cleanup completed.")
    
    async def handle_socket_mode_request(self, client: SocketModeClient, req: SocketModeRequest):
        """Handle incoming Slack socket mode requests."""
        try:
            # Acknowledge the request immediately
            response = SocketModeResponse(envelope_id=req.envelope_id)
            await client.send_socket_mode_response(response)
            
            # Process different event types
            if req.type == "events_api":
                await self.handle_events_api(req.payload)
            elif req.type == "slash_commands":
                await self.handle_slash_command(req.payload)
            elif req.type == "interactive":
                await self.handle_interactive_event(req.payload)
            else:
                logger.debug(f"Unhandled request type: {req.type}")
                
        except Exception as e:
            logger.error(f"Error handling socket mode request: {e}")
    
    async def handle_events_api(self, payload: Dict[str, Any]):
        """Handle Events API payloads."""
        event = payload.get("event", {})
        event_type = event.get("type")
        
        logger.info(f"Received event: {event_type}")
        
        # Filter out bot messages to avoid loops
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return
        
        # Process different event types
        if event_type == "message":
            await self.process_message_event(event, payload)
        elif event_type == "reaction_added":
            await self.process_reaction_event(event, payload)
        elif event_type == "member_joined_channel":
            await self.process_member_joined_event(event, payload)
        else:
            # Send all other events to n8n
            await self.send_to_n8n({"type": event_type, "event": event}, payload)
    
    async def process_message_event(self, event: Dict[str, Any], full_payload: Dict[str, Any]):
        """Process message events."""
        channel = event.get("channel")
        user = event.get("user")
        text = event.get("text", "")
        timestamp = event.get("ts")
        
        # Get channel info
        try:
            channel_info = await self.slack_web_client.conversations_info(channel=channel)
            channel_name = channel_info["channel"]["name"]
        except Exception as e:
            logger.warning(f"Could not get channel info: {e}")
            channel_name = channel
        
        # Get user info
        try:
            user_info = await self.slack_web_client.users_info(user=user)
            username = user_info["user"]["real_name"] or user_info["user"]["name"]
            user_email = user_info["user"]["profile"].get("email")
        except Exception as e:
            logger.warning(f"Could not get user info: {e}")
            username = user
            user_email = None
        
        # Prepare message data for n8n
        message_data = {
            "type": "message",
            "event_type": "message",
            "channel": channel,
            "channel_name": channel_name,
            "user": user,
            "username": username,
            "user_email": user_email,
            "text": text,
            "timestamp": timestamp,
            "raw_event": event,
            "team_id": full_payload.get("team_id")
        }
        
        await self.send_to_n8n(message_data, full_payload)
        logger.info(f"Processed message from {username} in #{channel_name}: {text[:50]}...")
    
    async def process_reaction_event(self, event: Dict[str, Any], full_payload: Dict[str, Any]):
        """Process reaction added events."""
        reaction_data = {
            "type": "reaction_added",
            "event_type": "reaction_added",
            "reaction": event.get("reaction"),
            "user": event.get("user"),
            "item": event.get("item"),
            "raw_event": event,
            "team_id": full_payload.get("team_id")
        }
        
        await self.send_to_n8n(reaction_data, full_payload)
        logger.info(f"Processed reaction: {event.get('reaction')} by {event.get('user')}")
    
    async def process_member_joined_event(self, event: Dict[str, Any], full_payload: Dict[str, Any]):
        """Process member joined channel events."""
        join_data = {
            "type": "member_joined_channel",
            "event_type": "member_joined_channel",
            "user": event.get("user"),
            "channel": event.get("channel"),
            "raw_event": event,
            "team_id": full_payload.get("team_id")
        }
        
        await self.send_to_n8n(join_data, full_payload)
        logger.info(f"Processed member join: {event.get('user')} joined {event.get('channel')}")
    
    async def handle_slash_command(self, payload: Dict[str, Any]):
        """Handle slash commands."""
        # Send slash command in Slack's native format
        await self.send_to_n8n(None, payload)
        logger.info(f"Processed slash command: {payload.get('command')} by {payload.get('user_name')}")
    
    async def handle_interactive_event(self, payload: Dict[str, Any]):
        """Handle interactive events (buttons, menus, etc.)."""
        # Send interactive event in Slack's native format
        await self.send_to_n8n(None, payload)
        logger.info(f"Processed interactive event: {payload.get('type')}")
    
    async def send_to_n8n(self, data: Dict[str, Any], full_payload: Dict[str, Any] = None):
        """Send data to n8n webhook in Slack's native format."""
        try:
            # Send the original Slack payload format that n8n expects
            if full_payload:
                # For Events API, send the complete Slack payload
                payload = full_payload
            else:
                # For other events, wrap in Slack-like structure
                payload = {
                    "token": "proxy-token",  # Placeholder token
                    "team_id": data.get("team_id"),
                    "api_app_id": "proxy-app",
                    "event": data,
                    "type": "event_callback",
                    "event_id": f"proxy-{asyncio.get_event_loop().time()}",
                    "event_time": int(asyncio.get_event_loop().time())
                }
            
            async with self.session.post(
                self.n8n_webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                # Read the response to complete the HTTP transaction
                response_text = await response.text()
                
                if response.status == 200:
                    logger.debug(f"Successfully sent data to n8n: {response.status}")
                    if response_text:
                        logger.debug(f"n8n response: {response_text[:100]}...")
                else:
                    logger.warning(f"n8n webhook returned status {response.status}: {response_text}")
                    
        except asyncio.TimeoutError:
            logger.error("Timeout sending data to n8n webhook")
        except Exception as e:
            logger.error(f"Error sending data to n8n: {e}")


async def main():
    """Main function to run the proxy."""
    # Configuration - use environment variables or replace with your values
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")  # xoxb-...
    SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")  # xapp-...
    N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")  # Your n8n webhook URL
    
    # Validate configuration
    if not all([SLACK_BOT_TOKEN, SLACK_APP_TOKEN, N8N_WEBHOOK_URL]):
        logger.error("Missing required environment variables:")
        logger.error("- SLACK_BOT_TOKEN: Your Slack Bot User OAuth Token")
        logger.error("- SLACK_APP_TOKEN: Your Slack App-Level Token") 
        logger.error("- N8N_WEBHOOK_URL: Your n8n webhook URL")
        return
    
    # Create and start the proxy
    proxy = SlackN8nProxy(
        slack_bot_token=SLACK_BOT_TOKEN,
        slack_app_token=SLACK_APP_TOKEN,
        n8n_webhook_url=N8N_WEBHOOK_URL
    )
    
    await proxy.start()


if __name__ == "__main__":
    asyncio.run(main())