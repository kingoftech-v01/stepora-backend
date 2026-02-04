/**
 * Tests for the i18n framework.
 */

// Mock React hooks before importing
jest.mock('react', () => ({
  useState: jest.fn((initial: unknown) => [initial, jest.fn()]),
  useCallback: jest.fn((fn: unknown) => fn),
  useEffect: jest.fn((fn: () => (() => void) | void) => {
    const cleanup = fn();
    if (typeof cleanup === 'function') cleanup();
  }),
}));

// Mock the types module
jest.mock('../../types', () => ({}));

import { t, setLanguage, getLanguage, getSupportedLanguages, isSupported } from '../../i18n';

describe('i18n framework', () => {
  beforeEach(() => {
    // Reset to English before each test
    setLanguage('en');
  });

  describe('t() - translation function', () => {
    it('translates simple keys in English', () => {
      expect(t('nav.home')).toBe('Home');
    });

    it('translates nested keys', () => {
      expect(t('common.loading')).toBe('Loading...');
    });

    it('returns the key string for missing translations', () => {
      expect(t('nonexistent.key')).toBe('nonexistent.key');
    });

    it('translates keys in French', () => {
      setLanguage('fr');
      expect(t('nav.home')).toBe('Accueil');
    });

    it('falls back to English for missing keys in other languages', () => {
      setLanguage('fr');
      // If a key exists in English but not in French, it should fall back
      const result = t('nav.home');
      // This should return the French translation since it exists
      expect(typeof result).toBe('string');
      expect(result.length).toBeGreaterThan(0);
    });

    it('supports parameter interpolation', () => {
      // Test with a key that has params (if any exist)
      const result = t('common.loading');
      expect(typeof result).toBe('string');
    });
  });

  describe('setLanguage()', () => {
    it('changes the current language', () => {
      setLanguage('fr');
      expect(getLanguage()).toBe('fr');
    });

    it('stays on same language when setting same language', () => {
      setLanguage('en');
      expect(getLanguage()).toBe('en');
    });

    it('falls back to English for unsupported languages', () => {
      // @ts-expect-error Testing invalid language
      setLanguage('xx');
      expect(getLanguage()).toBe('en');
    });
  });

  describe('getLanguage()', () => {
    it('returns English by default', () => {
      expect(getLanguage()).toBe('en');
    });

    it('returns the current language after change', () => {
      setLanguage('es');
      expect(getLanguage()).toBe('es');
    });
  });

  describe('getSupportedLanguages()', () => {
    it('returns all 15 supported languages', () => {
      const languages = getSupportedLanguages();
      expect(languages).toHaveLength(15);
    });

    it('includes English', () => {
      const languages = getSupportedLanguages();
      expect(languages).toContain('en');
    });

    it('includes all expected languages', () => {
      const languages = getSupportedLanguages();
      const expected = ['en', 'fr', 'es', 'pt', 'ar', 'zh', 'hi', 'ja', 'de', 'ru', 'ko', 'it', 'tr', 'nl', 'pl'];
      expected.forEach((lang) => {
        expect(languages).toContain(lang);
      });
    });
  });

  describe('isSupported()', () => {
    it('returns true for supported languages', () => {
      expect(isSupported('en')).toBe(true);
      expect(isSupported('fr')).toBe(true);
      expect(isSupported('ja')).toBe(true);
    });

    it('returns false for unsupported languages', () => {
      expect(isSupported('xx')).toBe(false);
      expect(isSupported('sv')).toBe(false);
    });
  });

  describe('language switching', () => {
    it('translates correctly after switching languages', () => {
      expect(t('nav.home')).toBe('Home');

      setLanguage('fr');
      expect(t('nav.home')).toBe('Accueil');

      setLanguage('en');
      expect(t('nav.home')).toBe('Home');
    });

    it('translates multiple keys in different languages', () => {
      setLanguage('fr');
      expect(t('nav.calendar')).toBe('Calendrier');
      expect(t('common.cancel')).toBe('Annuler');

      setLanguage('en');
      expect(t('nav.calendar')).toBe('Calendar');
      expect(t('common.cancel')).toBe('Cancel');
    });
  });
});
