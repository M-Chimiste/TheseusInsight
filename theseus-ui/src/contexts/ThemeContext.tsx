import React, { createContext, useContext, useMemo } from 'react';
import { ThemeProvider as MuiThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { buildTheme } from '../styles/theme';
import { useDesign } from './DesignContext';

// Observatory is dark-first. The previous dark/light toggle has been retired;
// `isDarkMode`/`toggleTheme` are kept on the context only so existing callers
// (Settings switch, charts that branch on dark vs light) keep compiling. They
// always read as dark and the toggle is a no-op.
type ThemeContextType = {
  isDarkMode: boolean;
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextType>({
  isDarkMode: true,
  toggleTheme: () => {},
});

export const useTheme = () => useContext(ThemeContext);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { accent } = useDesign();

  const theme = useMemo(() => buildTheme({ accent }), [accent]);

  const value = useMemo<ThemeContextType>(
    () => ({ isDarkMode: true, toggleTheme: () => {} }),
    []
  );

  return (
    <ThemeContext.Provider value={value}>
      <MuiThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ThemeContext.Provider>
  );
};
