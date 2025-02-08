import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from './useAPI';
import {
  PodcastGenerationResponse,
  PodcastGenerationConfig,
  Script,
  TaskStatus,
} from '../types/api';

export const useGeneratePodcast = () => {
  return useMutation<PodcastGenerationResponse, Error, FormData>({
    mutationFn: async (formData: FormData) => {
      const response = await api.post<PodcastGenerationResponse>(
        '/podcast/generate',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );
      return response.data;
    },
  });
};

export const useRegeneratePodcast = () => {
  return useMutation<
    PodcastGenerationResponse,
    Error,
    { script: Script; config: PodcastGenerationConfig }
  >({
    mutationFn: async ({ script, config }) => {
      const response = await api.post<PodcastGenerationResponse>(
        '/podcast/regenerate',
        { script, config }
      );
      return response.data;
    },
  });
};

export const usePodcastStatus = (taskId: string) => {
  return useQuery<TaskStatus, Error>({
    queryKey: ['podcast-status', taskId],
    queryFn: async () => {
      const response = await api.get<TaskStatus>(`/podcast/status/${taskId}`);
      return response.data;
    },
    enabled: !!taskId,
    refetchInterval: (data) => {
      if (!data) return 2000; // Default to 2 seconds if no data
      return data.status === 'processing' ? 2000 : false;
    },
  });
}; 