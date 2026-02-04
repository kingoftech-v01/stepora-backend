# Conversations App

Application Django pour le chat IA en temps reel avec WebSocket.

## Overview

L'app Conversations gere les interactions entre l'utilisateur et le coach IA:
- **Conversation** - Session de chat avec contexte
- **Message** - Message individuel (user/assistant/system)
- **ConversationSummary** - Resume pour le contexte long terme

## Models

### Conversation

| Champ | Type | Description |
|-------|------|-------------|
| id | UUID | Identifiant unique |
| user | FK(User) | Proprietaire |
| dream | FK(Dream) | Reve associe (optionnel) |
| conversation_type | CharField | Type de conversation |
| total_messages | Integer | Nombre total de messages |
| total_tokens_used | Integer | Tokens OpenAI utilises |
| is_active | Boolean | Conversation active |

**Types de conversation:**
- `dream_creation` - Creation de reve guide
- `planning` - Planification d'objectifs
- `check_in` - Point de suivi
- `adjustment` - Ajustement de plan
- `general` - Discussion generale
- `motivation` - Boost de motivation
- `rescue` - Mode sauvetage (utilisateur en difficulte)

### Message

| Champ | Type | Description |
|-------|------|-------------|
| id | UUID | Identifiant unique |
| conversation | FK(Conversation) | Conversation parente |
| role | CharField | user, assistant, system |
| content | TextField | Contenu du message |
| metadata | JSONField | Tokens utilises, modele, etc. |

### ConversationSummary

| Champ | Type | Description |
|-------|------|-------------|
| id | UUID | Identifiant unique |
| conversation | FK(Conversation) | Conversation |
| summary | TextField | Resume textuel |
| key_points | JSONField | Points cles extraits |
| start_message | FK(Message) | Premier message couvert |
| end_message | FK(Message) | Dernier message couvert |

## API Endpoints

### REST API
- `GET /api/conversations/` - Liste des conversations
- `POST /api/conversations/` - Creer une conversation
- `GET /api/conversations/{id}/` - Detail avec messages
- `DELETE /api/conversations/{id}/` - Supprimer
- `GET /api/conversations/{id}/messages/` - Liste des messages
- `POST /api/conversations/{id}/messages/` - Envoyer un message (non-streaming)

### WebSocket
- `ws://host/ws/conversations/{id}/` - Chat temps reel

**Actions WebSocket:**
```json
// Envoyer un message
{"type": "message", "content": "Bonjour!"}

// Recevoir une reponse (streaming)
{"type": "assistant_start"}
{"type": "assistant_chunk", "content": "Bon"}
{"type": "assistant_chunk", "content": "jour"}
{"type": "assistant_end", "message_id": "uuid"}

// Typing indicator
{"type": "typing", "is_typing": true}
```

## Serializers

- `ConversationSerializer` - Avec messages recents
- `ConversationListSerializer` - Version legere
- `MessageSerializer` - Message complet

## WebSocket Consumer

Le `ChatConsumer` gere:
1. Authentification via Firebase JWT
2. Reception des messages utilisateur
3. Streaming des reponses GPT-4
4. Indicateurs de frappe
5. Gestion des erreurs

## Integration OpenAI

**Modele utilise:** GPT-4 Turbo (configurable)

**System prompt dynamique selon le type:**
- `dream_creation`: Guide la creation de reve
- `planning`: Aide a planifier les etapes
- `motivation`: Encourage et motive
- `rescue`: Mode empathique pour utilisateurs en difficulte

## Rate Limiting

Les conversations sont soumises au rate limiting:
- **Free**: 10 messages/heure
- **Premium**: 100 messages/heure
- **Pro**: 1000 messages/heure

## Testing

```bash
# Tests unitaires
python manage.py test apps.conversations

# Tests WebSocket
pytest apps/conversations/tests.py -v -k websocket
```

## Configuration

Variables d'environnement:
- `OPENAI_API_KEY` - Cle API OpenAI
- `OPENAI_MODEL` - Modele (default: gpt-4-turbo-preview)
- `OPENAI_TIMEOUT` - Timeout en secondes (default: 30)

## Routing WebSocket

```python
# routing.py
websocket_urlpatterns = [
    re_path(r'ws/conversations/(?P<conversation_id>[^/]+)/$', ChatConsumer.as_asgi()),
]
```

## Dependencies

- `channels` - WebSocket support
- `channels-redis` - Redis channel layer
- `openai` - API OpenAI
