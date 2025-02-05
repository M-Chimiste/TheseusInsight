import { useMutation, useQuery } from '@tanstack/react-query';
import { api, uploadFile } from './useAPI';
import { VisualizerConfig, VisualizerResponse, TaskStatus } from '../types/api';

interface GenerateVisualizerParams {
  file: File;
  config: VisualizerConfig;
}

export const useGenerateVisualizer = () => {
  return useMutation<VisualizerResponse, Error, GenerateVisualizerParams>({
    mutationFn: async ({ file, config }) => {
      const response = await uploadFile<VisualizerResponse>('/visualizer/generate', file, config);
      return response;
    },
  });
};

export const useVisualizerStatus = (taskId: string) => {
  return useQuery<TaskStatus, Error>({
    queryKey: ['visualizer-status', taskId],
    queryFn: async () => {
      const response = await api.get<TaskStatus>(`/visualizer/status/${taskId}`);
      return response.data;
    },
    enabled: !!taskId,
    refetchInterval: (data) =>
      data?.status === 'completed' || data?.status === 'failed' ? false : 1000,
  });
}; 