# Chat Screens - TODO

## Current Status
- chat_screen.dart: Fully functional (WebSocket streaming, message display, suggestion chips)
- conversation_list_screen.dart: Fully functional (list conversations, delete, type labels)

## Missing Screens
- [x] **Conversation list/history screen**: List all conversations from `GET /api/conversations/`; show type, last message preview, message count, timestamp; tap to open in ChatScreen

## Missing Functionality
- [x] Add conversation deletion: Swipe or long-press; call `DELETE /api/conversations/{id}/`
- [x] Add conversation type label in chat header

## Small Improvements
- [x] Add message retry on send failure
- [x] Add "Copy message" long-press action on chat bubbles
- [x] Show connection status indicator (connected/reconnecting)
