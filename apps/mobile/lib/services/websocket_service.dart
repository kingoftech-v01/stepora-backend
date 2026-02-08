import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../config/env.dart';

class WebSocketService {
  WebSocketChannel? _channel;
  final _messageController = StreamController<Map<String, dynamic>>.broadcast();
  String? _token;
  bool _isConnected = false;

  Stream<Map<String, dynamic>> get messageStream => _messageController.stream;
  bool get isConnected => _isConnected;

  void connect(String conversationId, String token) {
    _token = token;
    final url = '${Env.wsBaseUrl}/chat/$conversationId/?token=$token';

    _channel = WebSocketChannel.connect(Uri.parse(url));
    _isConnected = true;

    _channel!.stream.listen(
      (data) {
        final decoded = jsonDecode(data as String) as Map<String, dynamic>;
        _messageController.add(decoded);
      },
      onError: (error) {
        _isConnected = false;
        _reconnect(conversationId);
      },
      onDone: () {
        _isConnected = false;
      },
    );
  }

  void sendMessage(String content) {
    if (_channel != null && _isConnected) {
      _channel!.sink.add(jsonEncode({
        'type': 'chat_message',
        'content': content,
      }));
    }
  }

  void _reconnect(String conversationId) {
    Future.delayed(const Duration(seconds: 3), () {
      if (!_isConnected && _token != null) {
        connect(conversationId, _token!);
      }
    });
  }

  void disconnect() {
    _isConnected = false;
    _channel?.sink.close();
    _channel = null;
  }

  void dispose() {
    disconnect();
    _messageController.close();
  }
}
