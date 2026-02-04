// Django backend uses port 8000 by default
export const ENV = {
  API_URL: __DEV__ ? 'http://localhost:8000' : 'https://api.dreamplanner.app',
  WS_URL: __DEV__ ? 'ws://localhost:8000/ws' : 'wss://api.dreamplanner.app/ws',
};
