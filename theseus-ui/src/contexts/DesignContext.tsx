import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import type { CardStyle, Density } from '../styles/observatoryTokens';
import { OBS } from '../styles/observatoryTokens';

const STORAGE_KEY = 'theseus.design';

type DesignState = {
  accent: string;
  density: Density;
  cardStyle: CardStyle;
};

type DesignContextValue = DesignState & {
  setAccent: (v: string) => void;
  setDensity: (v: Density) => void;
  setCardStyle: (v: CardStyle) => void;
  reset: () => void;
};

const DEFAULTS: DesignState = {
  accent: OBS.cyan,
  density: 'balanced',
  cardStyle: 'bordered',
};

function loadInitial(): DesignState {
  if (typeof window === 'undefined') return DEFAULTS;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<DesignState>;
    return {
      accent: typeof parsed.accent === 'string' ? parsed.accent : DEFAULTS.accent,
      density: (parsed.density as Density) || DEFAULTS.density,
      cardStyle: (parsed.cardStyle as CardStyle) || DEFAULTS.cardStyle,
    };
  } catch {
    return DEFAULTS;
  }
}

const DesignContext = createContext<DesignContextValue | undefined>(undefined);

export const useDesign = (): DesignContextValue => {
  const ctx = useContext(DesignContext);
  if (!ctx) throw new Error('useDesign must be used within DesignProvider');
  return ctx;
};

export const DesignProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, setState] = useState<DesignState>(() => loadInitial());

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // localStorage unavailable; ignore
    }
  }, [state]);

  const setAccent = useCallback((accent: string) => setState((s) => ({ ...s, accent })), []);
  const setDensity = useCallback((density: Density) => setState((s) => ({ ...s, density })), []);
  const setCardStyle = useCallback((cardStyle: CardStyle) => setState((s) => ({ ...s, cardStyle })), []);
  const reset = useCallback(() => setState(DEFAULTS), []);

  const value = useMemo<DesignContextValue>(
    () => ({ ...state, setAccent, setDensity, setCardStyle, reset }),
    [state, setAccent, setDensity, setCardStyle, reset]
  );

  return <DesignContext.Provider value={value}>{children}</DesignContext.Provider>;
};
