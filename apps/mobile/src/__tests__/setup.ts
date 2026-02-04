// Mock react-native modules
jest.mock('react-native-mmkv', () => ({
  MMKV: jest.fn().mockImplementation(() => ({
    getString: jest.fn(),
    set: jest.fn(),
    delete: jest.fn(),
  })),
}));

jest.mock('@react-native-async-storage/async-storage', () => {
  const storage: Record<string, string> = {};
  return {
    __esModule: true,
    default: {
      setItem: jest.fn((key: string, value: string) => {
        storage[key] = value;
        return Promise.resolve();
      }),
      getItem: jest.fn((key: string) => {
        return Promise.resolve(storage[key] || null);
      }),
      removeItem: jest.fn((key: string) => {
        delete storage[key];
        return Promise.resolve();
      }),
      clear: jest.fn(() => {
        Object.keys(storage).forEach((key) => delete storage[key]);
        return Promise.resolve();
      }),
    },
  };
});

jest.mock('react-native-vector-icons/MaterialCommunityIcons', () => 'Icon');
jest.mock('react-native-linear-gradient', () => 'LinearGradient');
jest.mock('react-native-calendars', () => ({
  Calendar: 'Calendar',
  LocaleConfig: {
    locales: {},
    defaultLocale: '',
  },
}));

jest.mock('react-native-safe-area-context', () => ({
  SafeAreaView: 'SafeAreaView',
  SafeAreaProvider: 'SafeAreaProvider',
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

jest.mock('react-native-reanimated', () => ({
  default: {
    call: jest.fn(),
    event: jest.fn(),
    Value: jest.fn(),
    Node: jest.fn(),
  },
  useSharedValue: jest.fn(),
  useAnimatedStyle: jest.fn(() => ({})),
  withTiming: jest.fn(),
  withSpring: jest.fn(),
  FadeIn: { duration: jest.fn().mockReturnThis() },
  FadeInDown: { duration: jest.fn().mockReturnThis(), delay: jest.fn().mockReturnThis() },
  SlideInRight: { duration: jest.fn().mockReturnThis() },
}));

jest.mock('@notifee/react-native', () => ({
  default: {
    displayNotification: jest.fn(),
    createChannel: jest.fn(),
    requestPermission: jest.fn(),
  },
}));

jest.mock('@react-native-firebase/app', () => ({
  default: jest.fn(),
}));

jest.mock('@react-native-firebase/auth', () => ({
  default: jest.fn().mockReturnValue({
    signInWithEmailAndPassword: jest.fn(),
    createUserWithEmailAndPassword: jest.fn(),
    signOut: jest.fn(),
    currentUser: null,
    onAuthStateChanged: jest.fn(),
  }),
}));

jest.mock('@react-native-firebase/messaging', () => ({
  default: jest.fn().mockReturnValue({
    getToken: jest.fn(),
    requestPermission: jest.fn(),
    onMessage: jest.fn(),
  }),
}));

jest.mock('axios', () => {
  const mockAxios = {
    create: jest.fn(() => mockAxios),
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
    defaults: {
      headers: {
        common: {},
      },
    },
    interceptors: {
      response: {
        use: jest.fn(),
      },
      request: {
        use: jest.fn(),
      },
    },
  };
  return {
    default: mockAxios,
    ...mockAxios,
  };
});
