"use client";
import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";
import { Play, Download, Settings2, CheckCircle2, XCircle, Clock, Loader2 } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

interface Model {
  id: string;
  name: string;
  provider: string;
}

interface NodeStatus {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  message: string;
  progress: number;
  timestamp: string;
}

interface RunStatus {
  taskId: string;
  nodes: NodeStatus[];
  overallStatus: 'pending' | 'processing' | 'completed' | 'failed';
  error?: string;
}

interface VisualizerConfig {
  fps: number;
  colorScheme: string;
  introLength: number;
  outroLength: number;
}

export default function PodcastPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [urls, setUrls] = useState<string>("");
  const [scriptModel, setScriptModel] = useState<string>("gpt-4");
  const [ttsModel, setTtsModel] = useState<string>("elevenlabs");
  const [addVisualization, setAddVisualization] = useState(false);
  const [visualizerConfig, setVisualizerConfig] = useState<VisualizerConfig>({
    fps: 30,
    colorScheme: "default",
    introLength: 5,
    outroLength: 5,
  });
  const [isGenerating, setIsGenerating] = useState(false);
  const [runStatus, setRunStatus] = useState<RunStatus | null>(null);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);

  // Fetch available models
  const { data: models } = useQuery<Model[]>({
    queryKey: ['models'],
    queryFn: async () => {
      const response = await fetch('/api/models');
      if (!response.ok) throw new Error('Failed to fetch models');
      return response.json();
    },
  });

  useEffect(() => {
    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, [ws]);

  const connectWebSocket = (taskId: string) => {
    const wsUrl = `ws://localhost:8000/ws/podcast/${taskId}`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('WebSocket connected');
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setRunStatus((prev) => {
        if (!prev) {
          return {
            taskId,
            nodes: [data],
            overallStatus: data.status,
          };
        }
        return {
          ...prev,
          nodes: [...prev.nodes, data],
          overallStatus: data.status,
        };
      });

      // Check if generation is complete and get download URL
      if (data.status === 'completed') {
        setDownloadUrl(`/api/podcast/download/${taskId}`);
      }
    };

    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
      toast.error('Lost connection to progress updates');
    };

    socket.onclose = () => {
      console.log('WebSocket disconnected');
    };

    setWs(socket);
  };

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files);
    setFiles((prev) => [...prev, ...droppedFiles]);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files);
      setFiles((prev) => [...prev, ...selectedFiles]);
    }
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleGenerate = async () => {
    if (files.length === 0 && !urls.trim()) {
      toast.error("Please provide at least one PDF file or arXiv URL");
      return;
    }

    setIsGenerating(true);
    setRunStatus(null);
    setDownloadUrl(null);

    try {
      const formData = new FormData();
      files.forEach((file) => {
        formData.append('files', file);
      });

      const config = {
        scriptModel,
        ttsModel,
        addVisualization,
        visualizerConfig: addVisualization ? visualizerConfig : undefined,
        urls: urls.split('\n').filter(Boolean),
      };

      formData.append('config', JSON.stringify(config));

      const response = await fetch('/api/podcast/generate', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Failed to generate podcast');
      
      const { taskId } = await response.json();
      connectWebSocket(taskId);
      toast.success("Podcast generation started");
    } catch (error) {
      toast.error("Failed to start podcast generation");
      setIsGenerating(false);
    }
  };

  const getStatusIcon = (status: NodeStatus['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />;
      case 'processing':
        return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
      default:
        return <Clock className="h-5 w-5 text-gray-500" />;
    }
  };

  return (
    <div className="container mx-auto py-6">
      <h1 className="text-3xl font-bold mb-6">Podcast Builder</h1>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Input Sources</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              <div>
                <Label>PDF Files</Label>
                <div
                  className="mt-2 border-2 border-dashed rounded-lg p-6 text-center cursor-pointer hover:border-primary"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleFileDrop}
                  onClick={() => document.getElementById('file-input')?.click()}
                >
                  <input
                    id="file-input"
                    type="file"
                    multiple
                    accept=".pdf"
                    className="hidden"
                    onChange={handleFileInput}
                  />
                  <p className="text-sm text-muted-foreground">
                    Drag and drop PDF files here or click to browse
                  </p>
                </div>
                {files.length > 0 && (
                  <div className="mt-4 space-y-2">
                    {files.map((file, index) => (
                      <div
                        key={index}
                        className="flex items-center justify-between p-2 bg-muted rounded"
                      >
                        <span className="text-sm truncate">{file.name}</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeFile(index)}
                        >
                          Remove
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <Label>arXiv URLs</Label>
                <Textarea
                  placeholder="Enter arXiv URLs (one per line)"
                  value={urls}
                  onChange={(e) => setUrls(e.target.value)}
                  className="mt-2 min-h-[100px]"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Model Settings</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4">
              <div className="space-y-2">
                <Label>Script Generation Model</Label>
                <Select value={scriptModel} onValueChange={setScriptModel}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select model" />
                  </SelectTrigger>
                  <SelectContent>
                    {models?.map((model) => (
                      <SelectItem key={model.id} value={model.id}>
                        {model.name} ({model.provider})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Text-to-Speech Model</Label>
                <Select value={ttsModel} onValueChange={setTtsModel}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select model" />
                  </SelectTrigger>
                  <SelectContent>
                    {models?.map((model) => (
                      <SelectItem key={model.id} value={model.id}>
                        {model.name} ({model.provider})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Visualizer Options</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-4 mb-4">
              <Switch
                checked={addVisualization}
                onCheckedChange={setAddVisualization}
              />
              <Label>Add Visualization</Label>
            </div>

            {addVisualization && (
              <div className="grid gap-4">
                <div className="space-y-2">
                  <Label>FPS</Label>
                  <Input
                    type="number"
                    value={visualizerConfig.fps}
                    onChange={(e) =>
                      setVisualizerConfig((prev) => ({
                        ...prev,
                        fps: parseInt(e.target.value),
                      }))
                    }
                    min="1"
                    max="60"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Color Scheme</Label>
                  <Select
                    value={visualizerConfig.colorScheme}
                    onValueChange={(value) =>
                      setVisualizerConfig((prev) => ({
                        ...prev,
                        colorScheme: value,
                      }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select color scheme" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="default">Default</SelectItem>
                      <SelectItem value="dark">Dark</SelectItem>
                      <SelectItem value="light">Light</SelectItem>
                      <SelectItem value="neon">Neon</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Intro Length (seconds)</Label>
                    <Input
                      type="number"
                      value={visualizerConfig.introLength}
                      onChange={(e) =>
                        setVisualizerConfig((prev) => ({
                          ...prev,
                          introLength: parseInt(e.target.value),
                        }))
                      }
                      min="0"
                      max="30"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Outro Length (seconds)</Label>
                    <Input
                      type="number"
                      value={visualizerConfig.outroLength}
                      onChange={(e) =>
                        setVisualizerConfig((prev) => ({
                          ...prev,
                          outroLength: parseInt(e.target.value),
                        }))
                      }
                      min="0"
                      max="30"
                    />
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {runStatus && (
          <Card>
            <CardHeader>
              <CardTitle>Generation Progress</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {runStatus.nodes.map((node, index) => (
                  <div key={node.id} className="flex items-start space-x-4">
                    <div className="flex flex-col items-center">
                      {getStatusIcon(node.status)}
                      {index < runStatus.nodes.length - 1 && (
                        <div className="w-0.5 h-8 bg-gray-200 my-1" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <p className="font-medium">{node.message}</p>
                        <span className="text-sm text-gray-500">
                          {new Date(node.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      {node.status === 'processing' && (
                        <Progress value={node.progress} className="mt-2" />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        <div className="flex justify-end space-x-4">
          {downloadUrl && (
            <Button
              variant="outline"
              onClick={() => window.open(downloadUrl, '_blank')}
            >
              <Download className="mr-2 h-4 w-4" />
              Download Podcast
            </Button>
          )}
          <Button
            onClick={handleGenerate}
            disabled={isGenerating}
            className="w-full sm:w-auto"
          >
            <Play className="mr-2 h-4 w-4" />
            {isGenerating ? "Generating..." : "Generate Podcast"}
          </Button>
        </div>
      </div>
    </div>
  );
} 