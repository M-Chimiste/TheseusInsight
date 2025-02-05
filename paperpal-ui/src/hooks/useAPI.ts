import axios from 'axios';

export const API_BASE_URL = 'http://localhost:8000/api';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for handling errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.detail || error.message;
    return Promise.reject(new Error(message));
  }
);

// Helper function to handle file uploads
export const uploadFile = async <T>(
  endpoint: string,
  file: File,
  config?: Record<string, any>
): Promise<T> => {
  const formData = new FormData();
  formData.append('file', file);
  
  if (config) {
    formData.append('config', JSON.stringify(config));
  }

  const response = await api.post<T>(endpoint, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
};

// Helper function to handle multiple file uploads
export const uploadFiles = async <T>(
  endpoint: string,
  files: File[],
  config?: Record<string, any>
): Promise<T> => {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });

  if (config) {
    formData.append('config', JSON.stringify(config));
  }

  const response = await api.post<T>(endpoint, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
}; 