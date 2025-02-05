import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from './useAPI';
import { Script, ScriptListItem } from '../types/api';

export const useLoadScript = (filename: string) => {
  return useQuery<Script, Error>({
    queryKey: ['script', filename],
    queryFn: async () => {
      const response = await api.get<Script>(`/script/load/${filename}`);
      return response.data;
    },
    enabled: !!filename,
  });
};

export const useListScripts = () => {
  return useQuery<ScriptListItem[], Error>({
    queryKey: ['scripts'],
    queryFn: async () => {
      const response = await api.get<ScriptListItem[]>('/script/list');
      return response.data;
    },
  });
};

export const useSaveScript = () => {
  return useMutation<{ message: string }, Error, { script: Script; filename: string }>({
    mutationFn: async ({ script, filename }) => {
      const response = await api.post<{ message: string }>(
        '/script/save',
        script,
        { params: { filename } }
      );
      return response.data;
    },
  });
};

export const useDeleteScript = () => {
  return useMutation<{ message: string }, Error, string>({
    mutationFn: async (filename: string) => {
      const response = await api.delete<{ message: string }>(`/script/${filename}`);
      return response.data;
    },
  });
}; 