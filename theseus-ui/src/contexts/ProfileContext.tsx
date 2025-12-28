import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { profileApi } from '../services/api';
import type { ProfileApiResponse } from '../services/api';

interface ProfileContextType {
  profiles: ProfileApiResponse[];
  selectedProfileIds: number[];
  setSelectedProfileIds: (ids: number[]) => void;
  defaultProfile: ProfileApiResponse | null;
  isLoading: boolean;
  error: string | null;
  refreshProfiles: () => Promise<void>;
  getSelectedProfiles: () => ProfileApiResponse[];
  hasProfileSelected: (id: number) => boolean;
  selectProfile: (id: number) => void;
  deselectProfile: (id: number) => void;
  selectAllProfiles: () => void;
  clearAllProfiles: () => void;
}

const ProfileContext = createContext<ProfileContextType | undefined>(undefined);

export const useProfile = () => {
  const context = useContext(ProfileContext);
  if (context === undefined) {
    throw new Error('useProfile must be used within a ProfileProvider');
  }
  return context;
};

interface ProfileProviderProps {
  children: ReactNode;
}

export const ProfileProvider: React.FC<ProfileProviderProps> = ({ children }) => {
  const [profiles, setProfiles] = useState<ProfileApiResponse[]>([]);
  const [selectedProfileIds, setSelectedProfileIds] = useState<number[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshProfiles = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await profileApi.getProfiles();
      setProfiles(response.data);
      
      // Auto-select default profile if no profiles are selected
      if (selectedProfileIds.length === 0) {
        const defaultProfile = response.data.find(p => p.is_default);
        if (defaultProfile) {
          setSelectedProfileIds([defaultProfile.id]);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load profiles');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshProfiles();
  }, []);

  const defaultProfile = profiles.find(p => p.is_default) || null;

  const getSelectedProfiles = () => {
    return profiles.filter(p => selectedProfileIds.includes(p.id));
  };

  const hasProfileSelected = (id: number) => {
    return selectedProfileIds.includes(id);
  };

  const selectProfile = (id: number) => {
    if (!selectedProfileIds.includes(id)) {
      setSelectedProfileIds([...selectedProfileIds, id]);
    }
  };

  const deselectProfile = (id: number) => {
    setSelectedProfileIds(selectedProfileIds.filter(pid => pid !== id));
  };

  const selectAllProfiles = () => {
    setSelectedProfileIds(profiles.map(p => p.id));
  };

  const clearAllProfiles = () => {
    setSelectedProfileIds([]);
  };

  const value: ProfileContextType = {
    profiles,
    selectedProfileIds,
    setSelectedProfileIds,
    defaultProfile,
    isLoading,
    error,
    refreshProfiles,
    getSelectedProfiles,
    hasProfileSelected,
    selectProfile,
    deselectProfile,
    selectAllProfiles,
    clearAllProfiles,
  };

  return (
    <ProfileContext.Provider value={value}>
      {children}
    </ProfileContext.Provider>
  );
};

export default ProfileProvider; 