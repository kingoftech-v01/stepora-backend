"""
Firebase Cloud Messaging service for push notification delivery.
"""

import logging
from typing import List, Optional, Dict

from django.conf import settings

logger = logging.getLogger(__name__)

# Module-level singleton: initialized once per process
_firebase_app = None


def get_firebase_app():
    """
    Lazily initialize and return the Firebase Admin app singleton.
    Uses FIREBASE_CREDENTIALS_PATH from settings.
    """
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    import firebase_admin
    from firebase_admin import credentials

    cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', '')
    if not cred_path:
        raise RuntimeError(
            "FIREBASE_CREDENTIALS_PATH is not configured in Django settings."
        )

    cred = credentials.Certificate(cred_path)
    _firebase_app = firebase_admin.initialize_app(cred)
    logger.info("Firebase Admin SDK initialized successfully")
    return _firebase_app


class InvalidTokenError(Exception):
    """Raised when an FCM token is invalid or expired."""

    def __init__(self, token: str):
        self.token = token
        super().__init__(f"FCM token is invalid or unregistered: {token[:20]}...")


class MulticastResult:
    """Aggregated result from one or more multicast sends."""

    def __init__(self):
        self.success_count: int = 0
        self.failure_count: int = 0
        self.invalid_tokens: List[str] = []

    @property
    def total(self) -> int:
        return self.success_count + self.failure_count

    @property
    def any_success(self) -> bool:
        return self.success_count > 0


class FCMService:
    """
    Service class for Firebase Cloud Messaging operations.

    Handles single sends, multicast (batch) sends, topic management,
    and stale token detection.
    """

    MAX_MULTICAST_SIZE = 500

    def __init__(self):
        self.app = get_firebase_app()

    def build_message(
        self,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: str = '',
    ):
        """
        Build a base FCM Message (without token/topic).
        All values in `data` must be strings (FCM requirement).
        """
        from firebase_admin import messaging

        str_data = {}
        if data:
            str_data = {k: str(v) for k, v in data.items()}

        notification = messaging.Notification(
            title=title,
            body=body,
            image=image_url or None,
        )

        android_config = messaging.AndroidConfig(
            priority='high',
            notification=messaging.AndroidNotification(
                channel_id='dreamplanner_default',
                icon='ic_notification',
                color='#6C63FF',
            ),
        )

        apns_config = messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    alert=messaging.ApsAlert(title=title, body=body),
                    sound='default',
                    mutable_content=True,
                    content_available=True,
                ),
            ),
        )

        webpush_config = messaging.WebpushConfig(
            notification=messaging.WebpushNotification(
                title=title,
                body=body,
                icon='/static/icon-192.png',
            ),
        )

        return messaging.Message(
            notification=notification,
            data=str_data,
            android=android_config,
            apns=apns_config,
            webpush=webpush_config,
        )

    def send_to_token(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: str = '',
    ) -> Optional[str]:
        """
        Send a push notification to a single FCM registration token.
        Returns the FCM message_id on success, or None on failure.
        Raises InvalidTokenError if the token is invalid/expired.
        """
        from firebase_admin import messaging

        msg = self.build_message(title, body, data, image_url)
        msg.token = token

        try:
            message_id = messaging.send(msg, app=self.app)
            logger.debug(f"FCM sent to token {token[:20]}...: {message_id}")
            return message_id
        except messaging.UnregisteredError:
            raise InvalidTokenError(token)
        except messaging.SenderIdMismatchError:
            raise InvalidTokenError(token)
        except Exception as e:
            logger.error(f"FCM send failed for token {token[:20]}...: {e}", exc_info=True)
            raise

    def send_multicast(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: str = '',
    ) -> MulticastResult:
        """
        Send a push notification to multiple tokens via FCM multicast.
        Auto-chunks lists larger than 500 tokens.
        """
        result = MulticastResult()

        for i in range(0, len(tokens), self.MAX_MULTICAST_SIZE):
            chunk = tokens[i:i + self.MAX_MULTICAST_SIZE]
            self._send_multicast_chunk(chunk, title, body, data, image_url, result)

        return result

    def _send_multicast_chunk(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]],
        image_url: str,
        result: MulticastResult,
    ) -> None:
        """Send a single multicast chunk (up to 500 tokens)."""
        from firebase_admin import messaging

        base_msg = self.build_message(title, body, data, image_url)
        multicast = messaging.MulticastMessage(
            tokens=tokens,
            notification=base_msg.notification,
            data=base_msg.data,
            android=base_msg.android,
            apns=base_msg.apns,
            webpush=base_msg.webpush,
        )

        try:
            response = messaging.send_each_for_multicast(multicast, app=self.app)
            result.success_count += response.success_count
            result.failure_count += response.failure_count

            for idx, send_response in enumerate(response.responses):
                if send_response.exception is not None:
                    exc = send_response.exception
                    if isinstance(exc, (
                        messaging.UnregisteredError,
                        messaging.SenderIdMismatchError,
                    )):
                        result.invalid_tokens.append(tokens[idx])
                    else:
                        logger.warning(
                            f"FCM multicast error for token {tokens[idx][:20]}...: {exc}"
                        )
        except Exception as e:
            logger.error(f"FCM multicast batch failed: {e}")
            result.failure_count += len(tokens)

    def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Send a notification to all devices subscribed to an FCM topic."""
        from firebase_admin import messaging

        msg = self.build_message(title, body, data)
        msg.topic = topic

        try:
            message_id = messaging.send(msg, app=self.app)
            logger.debug(f"FCM topic send to '{topic}': {message_id}")
            return message_id
        except Exception as e:
            logger.warning(f"FCM topic send failed for '{topic}': {e}")
            return None

    def subscribe_to_topic(self, tokens: List[str], topic: str) -> None:
        """Subscribe device tokens to an FCM topic."""
        from firebase_admin import messaging

        try:
            response = messaging.subscribe_to_topic(tokens, topic, app=self.app)
            if response.failure_count > 0:
                logger.warning(
                    f"FCM topic subscribe partial failure: "
                    f"{response.failure_count}/{len(tokens)} failed for topic '{topic}'"
                )
        except Exception as e:
            logger.error(f"FCM topic subscribe error for '{topic}': {e}")

    def unsubscribe_from_topic(self, tokens: List[str], topic: str) -> None:
        """Unsubscribe device tokens from an FCM topic."""
        from firebase_admin import messaging

        try:
            response = messaging.unsubscribe_from_topic(tokens, topic, app=self.app)
            if response.failure_count > 0:
                logger.warning(
                    f"FCM topic unsubscribe partial failure: "
                    f"{response.failure_count}/{len(tokens)} for topic '{topic}'"
                )
        except Exception as e:
            logger.error(f"FCM topic unsubscribe error for '{topic}': {e}")
