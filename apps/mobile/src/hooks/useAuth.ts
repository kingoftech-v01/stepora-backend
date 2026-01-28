import { useMutation, useQuery } from '@tanstack/react-query';
import auth from '@react-native-firebase/auth';
import { api } from '../services/api';
import { useAuthStore } from '../stores/authStore';

export function useFirebaseAuth() {
  const setUser = useAuthStore((state) => state.setUser);
  const setAccessToken = useAuthStore((state) => state.setAccessToken);
  const logout = useAuthStore((state) => state.logout);

  const signIn = async (email: string, password: string) => {
    const userCredential = await auth().signInWithEmailAndPassword(email, password);
    const token = await userCredential.user.getIdToken();
    setAccessToken(token);

    // Register/sync with backend
    const response: any = await api.auth.register({});
    setUser(response.data.user);

    return response.data;
  };

  const signUp = async (email: string, password: string, displayName?: string) => {
    const userCredential = await auth().createUserWithEmailAndPassword(email, password);

    if (displayName) {
      await userCredential.user.updateProfile({ displayName });
    }

    const token = await userCredential.user.getIdToken();
    setAccessToken(token);

    // Register with backend
    const response: any = await api.auth.register({ displayName });
    setUser(response.data.user);

    return response.data;
  };

  const signOut = async () => {
    await auth().signOut();
    logout();
  };

  return { signIn, signUp, signOut };
}

export function useCurrentUser() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  return useQuery({
    queryKey: ['currentUser'],
    queryFn: () => api.users.getMe(),
    enabled: isAuthenticated,
  });
}

export function useUpdateProfile() {
  return useMutation({
    mutationFn: api.users.updateMe,
  });
}
