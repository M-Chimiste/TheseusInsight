import { useMutation } from '@tanstack/react-query';
import { uploadFile, uploadFiles } from './useAPI';
import { PDFUploadResult } from '../types/api';

export const useUploadPDF = () => {
  return useMutation<PDFUploadResult, Error, File>({
    mutationFn: (file: File) => uploadFile<PDFUploadResult>('/pdf/upload', file),
  });
};

export const useUploadMultiplePDFs = () => {
  return useMutation<PDFUploadResult[], Error, File[]>({
    mutationFn: (files: File[]) => uploadFiles<PDFUploadResult[]>('/pdf/batch-upload', files),
  });
}; 