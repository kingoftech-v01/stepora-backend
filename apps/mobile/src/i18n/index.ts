/**
 * Internationalization (i18n) framework for DreamPlanner.
 *
 * Provides a lightweight, custom i18n solution for React Native with:
 * - Type-safe translation keys via dot-notation path access
 * - Parameter interpolation using {{param}} syntax
 * - React hook for reactive language switching
 * - Support for 15 languages with English as the default fallback
 */
import { useState, useCallback, useEffect } from 'react';
import type { SupportedLanguage } from '../types';
import type { TranslationKeys } from './locales/en';

import en from './locales/en';
import fr from './locales/fr';
import es from './locales/es';
import pt from './locales/pt';
import ar from './locales/ar';
import zh from './locales/zh';
import hi from './locales/hi';
import ja from './locales/ja';
import de from './locales/de';
import ru from './locales/ru';
import ko from './locales/ko';
import it from './locales/it';
import tr from './locales/tr';
import nl from './locales/nl';
import pl from './locales/pl';

// ---------------------------------------------------------------------------
// Translation resource map
// ---------------------------------------------------------------------------

const resources: Record<SupportedLanguage, TranslationKeys> = {
  en,
  fr,
  es,
  pt,
  ar,
  zh,
  hi,
  ja,
  de,
  ru,
  ko,
  it,
  tr,
  nl,
  pl,
};

// ---------------------------------------------------------------------------
// Internal state
// ---------------------------------------------------------------------------

const DEFAULT_LANGUAGE: SupportedLanguage = 'en';

let currentLanguage: SupportedLanguage = DEFAULT_LANGUAGE;

/**
 * Listeners that are notified whenever the language changes so that
 * React components using the `useTranslation` hook can re-render.
 */
type LanguageChangeListener = (lang: SupportedLanguage) => void;
const listeners = new Set<LanguageChangeListener>();

function subscribe(listener: LanguageChangeListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function notifyListeners(): void {
  listeners.forEach((listener) => listener(currentLanguage));
}

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

/**
 * Resolves a dot-notation key (e.g. "nav.home") against a translation object.
 * Returns `undefined` when any segment along the path does not exist.
 */
function resolveKey(obj: Record<string, unknown>, key: string): string | undefined {
  const segments = key.split('.');
  let current: unknown = obj;

  for (const segment of segments) {
    if (current === null || current === undefined || typeof current !== 'object') {
      return undefined;
    }
    current = (current as Record<string, unknown>)[segment];
  }

  return typeof current === 'string' ? current : undefined;
}

/**
 * Replaces `{{paramName}}` placeholders in a string with the corresponding
 * values from the `params` map.
 */
function interpolate(text: string, params?: Record<string, string>): string {
  if (!params) return text;
  return text.replace(/\{\{(\w+)\}\}/g, (_, paramKey: string) => {
    return params[paramKey] !== undefined ? params[paramKey] : `{{${paramKey}}}`;
  });
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Translate a key into the current language.
 *
 * Supports dot-notation for nested keys and `{{param}}` interpolation.
 *
 * @example
 * ```ts
 * t('nav.home')                       // "Home"
 * t('dreams.todayTasks', { count: '3' }) // "3 tasks today"
 * ```
 *
 * Falls back to the English value when a key is missing in the active
 * language. Returns the raw key string as a last resort so missing
 * translations are immediately visible during development.
 */
export function t(key: string, params?: Record<string, string>): string {
  // Try the current language first
  const translated = resolveKey(
    resources[currentLanguage] as unknown as Record<string, unknown>,
    key,
  );

  if (translated !== undefined) {
    return interpolate(translated, params);
  }

  // Fallback to English
  if (currentLanguage !== DEFAULT_LANGUAGE) {
    const fallback = resolveKey(
      resources[DEFAULT_LANGUAGE] as unknown as Record<string, unknown>,
      key,
    );
    if (fallback !== undefined) {
      return interpolate(fallback, params);
    }
  }

  // Last resort: return the key itself so missing translations are obvious
  return key;
}

/**
 * Change the active language. All components using `useTranslation` will
 * re-render automatically.
 */
export function setLanguage(lang: SupportedLanguage): void {
  if (lang === currentLanguage) return;
  if (!resources[lang]) {
    console.warn(`[i18n] Language "${lang}" is not supported. Falling back to "${DEFAULT_LANGUAGE}".`);
    lang = DEFAULT_LANGUAGE;
  }
  currentLanguage = lang;
  notifyListeners();
}

/**
 * Get the currently active language code.
 */
export function getLanguage(): SupportedLanguage {
  return currentLanguage;
}

/**
 * Get the list of all supported language codes.
 */
export function getSupportedLanguages(): SupportedLanguage[] {
  return Object.keys(resources) as SupportedLanguage[];
}

/**
 * Check whether a given language code is supported.
 */
export function isSupported(lang: string): lang is SupportedLanguage {
  return lang in resources;
}

// ---------------------------------------------------------------------------
// React hook
// ---------------------------------------------------------------------------

/**
 * React hook that provides the `t` function and reactive language state.
 *
 * When `setLanguage` is called (from anywhere), every component that uses
 * this hook will re-render with the new translations.
 *
 * @example
 * ```tsx
 * function MyScreen() {
 *   const { t, language, setLanguage } = useTranslation();
 *   return <Text>{t('nav.home')}</Text>;
 * }
 * ```
 */
export function useTranslation() {
  const [language, setLang] = useState<SupportedLanguage>(currentLanguage);

  useEffect(() => {
    const unsubscribe = subscribe((newLang) => {
      setLang(newLang);
    });
    return unsubscribe;
  }, []);

  const changeLanguage = useCallback((lang: SupportedLanguage) => {
    setLanguage(lang);
  }, []);

  return {
    t,
    language,
    setLanguage: changeLanguage,
  } as const;
}

// Re-export types for convenience
export type { TranslationKeys } from './locales/en';
export type { SupportedLanguage } from '../types';
