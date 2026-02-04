import * as admin from 'firebase-admin';

let firebaseApp: admin.app.App | null = null;

export const initializeFirebase = (): admin.app.App => {
  if (firebaseApp) {
    return firebaseApp;
  }

  // Check if running in test mode
  if (process.env.NODE_ENV === 'test') {
    // Use mock for tests
    firebaseApp = {
      auth: () => ({
        verifyIdToken: async (token: string) => ({
          uid: 'test-uid',
          email: 'test@example.com',
        }),
      }),
    } as unknown as admin.app.App;
    return firebaseApp;
  }

  const serviceAccount = {
    projectId: process.env.FIREBASE_PROJECT_ID,
    privateKey: process.env.FIREBASE_PRIVATE_KEY?.replace(/\\n/g, '\n'),
    clientEmail: process.env.FIREBASE_CLIENT_EMAIL,
  };

  firebaseApp = admin.initializeApp({
    credential: admin.credential.cert(serviceAccount as admin.ServiceAccount),
  });

  return firebaseApp;
};

export const getFirebaseAdmin = (): admin.app.App => {
  if (!firebaseApp) {
    throw new Error('Firebase not initialized. Call initializeFirebase() first.');
  }
  return firebaseApp;
};

export const verifyFirebaseToken = async (idToken: string): Promise<admin.auth.DecodedIdToken> => {
  const app = getFirebaseAdmin();
  return app.auth().verifyIdToken(idToken);
};

export default { initializeFirebase, getFirebaseAdmin, verifyFirebaseToken };
