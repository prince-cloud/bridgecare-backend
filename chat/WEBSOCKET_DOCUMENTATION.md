# WebSocket Chat API Documentation

This document provides instructions on how to connect to the WebSocket chat API for real-time messaging between patients and healthcare providers.

## Overview

The chat WebSocket API enables real-time bidirectional communication between patients and healthcare providers. Messages are sent and received instantly through WebSocket connections.

## WebSocket URL

```
ws://your-domain.com/ws/chat/{chat_id}/
```

or for secure connections:

```
wss://your-domain.com/ws/chat/{chat_id}/
```

### URL Parameters

- **`chat_id`** (required): The UUID of the chat room you want to connect to. Format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

### Example

```
ws://localhost:8000/ws/chat/550e8400-e29b-41d4-a716-446655440000/
```

## Authentication

The WebSocket connection requires JWT authentication. You can provide the JWT token in one of two ways:

### Method 1: Query Parameter (Recommended)

Add the JWT token as a query parameter:

```
ws://your-domain.com/ws/chat/{chat_id}/?token=YOUR_JWT_TOKEN
```

**Example:**
```
ws://localhost:8000/ws/chat/550e8400-e29b-41d4-a716-446655440000/?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

### Method 2: Authorization Header

Some WebSocket clients support headers. You can use the `Authorization` header:

```
Authorization: Bearer YOUR_JWT_TOKEN
```

## Getting a Chat ID

Before connecting to the WebSocket, you need to obtain a chat ID. Use the REST API to create or retrieve a chat:

```bash
# Create or get existing chat
POST /chat/chats/
Content-Type: application/json
Authorization: Bearer YOUR_JWT_TOKEN

{
  "professional": "professional-uuid"  # If you're a patient
  // OR
  "patient": "patient-uuid"  # If you're a professional
}
```

The response will include the chat `id` that you can use for the WebSocket connection.

## Message Format

### Sending Messages

Send messages as JSON objects:

```json
{
  "content": "Hello, how can I help you?",
  "role": "patient"
}
```

**Fields:**
- `content` (string, required): The message text content. Cannot be empty.
- `role` (string, optional): Specify which profile to use when sending. Must be `"patient"` or `"professional"` (or `"provider"`). Only required if the user has both patient and professional profiles and the role cannot be determined from chat context.

### Receiving Messages

Messages are received as JSON objects:

```json
{
  "message": {
    "id": "message-uuid",
    "content": "Hello, how can I help you?",
    "sender_type": "patient",  // or "professional"
    "created_at": "2025-12-07T10:30:00.123456Z"
  }
}
```

**Response Fields:**
- `message.id` (string): Unique message identifier (UUID)
- `message.content` (string): The message content
- `message.sender_type` (string): Either `"patient"` or `"professional"`
- `message.created_at` (string): ISO 8601 formatted timestamp

### Error Responses

Errors are returned as JSON:

```json
{
  "error": "Error message here"
}
```

**Common Errors:**
- `"Message content cannot be empty"` - Sent when message content is empty or whitespace only
- `"Chat not found"` - Chat ID doesn't exist
- `"Invalid JSON"` - Request format is invalid
- Connection closed - User doesn't have access to the chat or authentication failed

## Connection Flow

1. **Authenticate**: Obtain a JWT token from your authentication endpoint
2. **Get Chat ID**: Create or retrieve a chat using the REST API
3. **Connect**: Establish WebSocket connection with JWT token
4. **Send/Receive**: Exchange messages in real-time
5. **Disconnect**: Close the connection when done

## JavaScript Example

### Using Native WebSocket API

```javascript
// Configuration
const CHAT_ID = '550e8400-e29b-41d4-a716-446655440000';
const JWT_TOKEN = 'your-jwt-token-here';
const WS_URL = `ws://localhost:8000/ws/chat/${CHAT_ID}/?token=${JWT_TOKEN}`;

// Create WebSocket connection
const ws = new WebSocket(WS_URL);

// Connection opened
ws.onopen = (event) => {
    console.log('WebSocket connection opened');

    // Send a message
    ws.send(JSON.stringify({
        content: 'Hello, doctor!'
    }));
};

// Listen for messages
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.message) {
        // Handle incoming message
        console.log('Received message:', data.message.content);
        console.log('From:', data.message.sender_type);
        console.log('Time:', data.message.created_at);
    } else if (data.error) {
        // Handle error
        console.error('Error:', data.error);
    }
};

// Connection closed
ws.onclose = (event) => {
    console.log('WebSocket connection closed');
};

// Connection error
ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

// Send a message function
function sendMessage(content) {
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ content }));
    } else {
        console.error('WebSocket is not open');
    }
}
```

### Using React Hook

```javascript
import { useEffect, useRef, useState } from 'react';

function useChatWebSocket(chatId, token) {
    const [messages, setMessages] = useState([]);
    const [isConnected, setIsConnected] = useState(false);
    const wsRef = useRef(null);

    useEffect(() => {
        if (!chatId || !token) return;

        const wsUrl = `ws://localhost:8000/ws/chat/${chatId}/?token=${token}`;
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('Connected to chat');
            setIsConnected(true);
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.message) {
                setMessages((prev) => [...prev, data.message]);
            }
        };

        ws.onclose = () => {
            console.log('Disconnected from chat');
            setIsConnected(false);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        wsRef.current = ws;

        return () => {
            ws.close();
        };
    }, [chatId, token]);

    const sendMessage = (content) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ content }));
        }
    };

    return { messages, isConnected, sendMessage };
}

// Usage in component
function ChatComponent({ chatId, token }) {
    const { messages, isConnected, sendMessage } = useChatWebSocket(chatId, token);

    return (
        <div>
            <div>
                {messages.map((msg) => (
                    <div key={msg.id}>
                        <strong>{msg.sender_type}:</strong> {msg.content}
                    </div>
                ))}
            </div>
            <input
                type="text"
                onKeyPress={(e) => {
                    if (e.key === 'Enter' && e.target.value.trim()) {
                        sendMessage(e.target.value.trim());
                        e.target.value = '';
                    }
                }}
            />
        </div>
    );
}
```

## Python Example

```python
import asyncio
import json
import websockets
from typing import Optional

class ChatWebSocketClient:
    def __init__(self, chat_id: str, token: str, url: str = "ws://localhost:8000"):
        self.chat_id = chat_id
        self.token = token
        self.url = f"{url}/ws/chat/{chat_id}/?token={token}"
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None

    async def connect(self):
        """Establish WebSocket connection"""
        self.websocket = await websockets.connect(self.url)
        print("Connected to chat")

    async def send_message(self, content: str):
        """Send a message"""
        if self.websocket:
            message = json.dumps({"content": content})
            await self.websocket.send(message)

    async def receive_messages(self):
        """Listen for incoming messages"""
        async for message in self.websocket:
            data = json.loads(message)
            if "message" in data:
                print(f"Received: {data['message']['content']}")
            elif "error" in data:
                print(f"Error: {data['error']}")

    async def disconnect(self):
        """Close WebSocket connection"""
        if self.websocket:
            await self.websocket.close()

# Usage
async def main():
    client = ChatWebSocketClient(
        chat_id="550e8400-e29b-41d4-a716-446655440000",
        token="your-jwt-token-here"
    )

    await client.connect()

    # Send a message
    await client.send_message("Hello!")

    # Listen for messages
    await client.receive_messages()

# Run
asyncio.run(main())
```

## Access Control

- Users can only connect to chats where they are either:
  - The **patient** in the chat, OR
  - The **professional/provider** in the chat
- Attempts to connect to unauthorized chats will result in immediate disconnection
- The system automatically determines user type based on their JWT token

## Multi-Profile Users

If a user has both a patient profile and a professional profile:

- **Automatic Role Detection**: The system automatically determines which role to use based on the chat context:
  - If you're the patient in the chat, messages are sent as patient
  - If you're the professional in the chat, messages are sent as professional

- **Explicit Role Specification**: You can explicitly specify which profile to use by including a `role` field in your message:
  ```json
  {
    "content": "Hello!",
    "role": "patient"  // or "professional" / "provider"
  }
  ```

- **Validation**: The system validates that you can only send messages using the profile that matches your role in that specific chat (you cannot send as a professional in a chat where you're the patient, and vice versa)

## Best Practices

1. **Reconnection Logic**: Implement automatic reconnection with exponential backoff
2. **Error Handling**: Always check for error responses and handle them gracefully
3. **Token Refresh**: Refresh JWT tokens before they expire
4. **Connection Status**: Monitor connection state and provide UI feedback
5. **Message Queuing**: Queue messages when disconnected and send when reconnected

## Rate Limiting

Currently, there are no specific rate limits on WebSocket messages. However, it's recommended to:
- Avoid sending messages more frequently than once per second
- Implement client-side throttling for rapid user input

## Testing with WebSocket Clients

### Using `wscat` (Node.js)

```bash
# Install wscat
npm install -g wscat

# Connect to chat
wscat -c "ws://localhost:8000/ws/chat/YOUR_CHAT_ID/?token=YOUR_JWT_TOKEN"

# Send message
{"content": "Hello!"}
```

### Using Browser DevTools

Open browser console and run:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat/YOUR_CHAT_ID/?token=YOUR_JWT_TOKEN');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
ws.send(JSON.stringify({content: 'Test message'}));
```

## Troubleshooting

### Connection Refused

- Check if the server is running with WebSocket support (Daphne or similar ASGI server)
- Verify the URL format is correct
- Ensure JWT token is valid and not expired

### Authentication Failed

- Verify JWT token is included in the connection URL
- Check token expiration time
- Ensure token format is correct (should not include "Bearer" prefix in query string)

### Messages Not Received

- Verify you're connected to the correct chat ID
- Check that the other participant is also connected
- Ensure you have access to the chat (you're either patient or provider)

### Connection Closes Immediately

- User doesn't have access to the chat
- Chat ID doesn't exist
- JWT token is invalid or expired

## Support

For issues or questions, please contact the development team or refer to the main API documentation.
