# Chat Screens - TODO

## Current Status
- chat_screen.dart: Fully functional (WebSocket streaming, message display, suggestion chips)

## Missing Screens
- [ ] **Conversation list/history screen**: List all conversations from `GET /api/conversations/`; show type, last message preview, message count, timestamp; tap to open in ChatScreen

## Missing Functionality
- [ ] Add conversation deletion: Swipe or long-press; call `DELETE /api/conversations/{id}/`
- [ ] Add conversation type label in chat header

## Small Improvements
- [ ] Add message retry on send failure
- [ ] Add "Copy message" long-press action on chat bubbles
- [ ] Show connection status indicator (connected/reconnecting)
