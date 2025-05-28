import React, { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';

const drawerWidth = 240;
const collapsedDrawerWidth = 64;

interface LayoutContextType {
  isDrawerOpen: boolean;
  drawerWidth: number;
  collapsedDrawerWidth: number;
  currentDrawerWidth: number;
  toggleDrawer: () => void;
}

const LayoutContext = createContext<LayoutContextType | undefined>(undefined);

export const useLayout = () => {
  const context = useContext(LayoutContext);
  if (context === undefined) {
    throw new Error('useLayout must be used within a LayoutProvider');
  }
  return context;
};

interface LayoutProviderProps {
  children: ReactNode;
}

export const LayoutProvider: React.FC<LayoutProviderProps> = ({ children }) => {
  const [isDrawerOpen, setIsDrawerOpen] = useState(true);

  const toggleDrawer = () => {
    setIsDrawerOpen(!isDrawerOpen);
  };

  const currentDrawerWidth = isDrawerOpen ? drawerWidth : collapsedDrawerWidth;

  const value = {
    isDrawerOpen,
    drawerWidth,
    collapsedDrawerWidth,
    currentDrawerWidth,
    toggleDrawer,
  };

  return (
    <LayoutContext.Provider value={value}>
      {children}
    </LayoutContext.Provider>
  );
};

export { drawerWidth, collapsedDrawerWidth }; 