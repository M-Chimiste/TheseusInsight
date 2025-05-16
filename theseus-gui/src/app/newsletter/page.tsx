"use client";
import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { format } from "date-fns";
import { CalendarIcon, Play, Music, Settings2, CheckCircle2, XCircle, Clock, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
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
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";
import { Progress } from "@/components/ui/progress";

interface NewsletterConfig {
  startDate: string;
  endDate: string;
  researchInterests: string[];
  emailRecipients: string[];
  createPodcast: boolean;
  podcastConfig?: {
    scriptModel: string;
    ttsModel: string;
    introMusic?: File;
  };
}

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

export default function NewsletterPage() {
  const [dateRange, setDateRange] = useState<{
    from: Date | undefined;
    to: Date | undefined;
  }>({
    from: undefined,
    to: undefined,
  });
  const [lastNDays, setLastNDays] = useState<string>("7");
  const [useDateRange, setUseDateRange] = useState(true);
  const [researchInterests, setResearchInterests] = useState<string>("");
  const [emailRecipients, setEmailRecipients] = useState<string>("");
  const [createPodcast, setCreatePodcast] = useState(false);
  const [introMusic, setIntroMusic] = useState<File | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [runStatus, setRunStatus] = useState<RunStatus | null>(null);
  const [ws, setWs] = useState<WebSocket | null>(null);

  useEffect(() => {
    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, [ws]);

  // Fetch available models
  const { data: models } = useQuery<Model[]>({
    queryKey: ['models'],
    queryFn: async () => {
      const response = await fetch('/api/models');
      if (!response.ok) throw new Error('Failed to fetch models');
      return response.json();
    },
  });

  const connectWebSocket = (taskId: string) => {
    const wsUrl = `ws://localhost:8000/ws/newsletter/${taskId}`;
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

  const handleGenerate = async () => {
    if (!dateRange.from || !dateRange.to) {
      toast.error("Please select a date range");
      return;
    }

    if (!researchInterests.trim()) {
      toast.error("Please enter research interests");
      return;
    }

    if (!emailRecipients.trim()) {
      toast.error("Please enter email recipients");
      return;
    }

    setIsGenerating(true);
    setRunStatus(null);

    try {
      const config: NewsletterConfig = {
        startDate: dateRange.from.toISOString(),
        endDate: dateRange.to.toISOString(),
        researchInterests: researchInterests.split('\n').filter(Boolean),
        emailRecipients: emailRecipients.split('\n').filter(Boolean),
        createPodcast,
      };

      if (createPodcast) {
        config.podcastConfig = {
          scriptModel: "gpt-4",
          ttsModel: "elevenlabs",
        };

        if (introMusic) {
          const formData = new FormData();
          formData.append('config', JSON.stringify(config));
          formData.append('intro_music_file', introMusic);

          const response = await fetch('/api/newsletter/run', {
            method: 'POST',
            body: formData,
          });

          if (!response.ok) throw new Error('Failed to generate newsletter');
          const { taskId } = await response.json();
          connectWebSocket(taskId);
        }
      } else {
        const response = await fetch('/api/newsletter/run', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(config),
        });

        if (!response.ok) throw new Error('Failed to generate newsletter');
        const { taskId } = await response.json();
        connectWebSocket(taskId);
      }

      toast.success("Newsletter generation started");
    } catch (error) {
      toast.error("Failed to start newsletter generation");
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
      <h1 className="text-3xl font-bold mb-6">Newsletter Builder</h1>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Date Range</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-4 mb-4">
              <Switch
                checked={useDateRange}
                onCheckedChange={setUseDateRange}
              />
              <Label>{useDateRange ? "Use Date Range" : "Last N Days"}</Label>
            </div>

            {useDateRange ? (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>From Date</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button
                        variant="outline"
                        className={cn(
                          "w-full justify-start text-left font-normal",
                          !dateRange.from && "text-muted-foreground"
                        )}
                      >
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {dateRange.from ? (
                          format(dateRange.from, "PPP")
                        ) : (
                          <span>Pick a date</span>
                        )}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0">
                      <Calendar
                        mode="single"
                        selected={dateRange.from}
                        onSelect={(date: Date | undefined) =>
                          setDateRange((prev) => ({ ...prev, from: date }))
                        }
                        initialFocus
                      />
                    </PopoverContent>
                  </Popover>
                </div>

                <div className="space-y-2">
                  <Label>To Date</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button
                        variant="outline"
                        className={cn(
                          "w-full justify-start text-left font-normal",
                          !dateRange.to && "text-muted-foreground"
                        )}
                      >
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {dateRange.to ? (
                          format(dateRange.to, "PPP")
                        ) : (
                          <span>Pick a date</span>
                        )}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0">
                      <Calendar
                        mode="single"
                        selected={dateRange.to}
                        onSelect={(date: Date | undefined) =>
                          setDateRange((prev) => ({ ...prev, to: date }))
                        }
                        initialFocus
                      />
                    </PopoverContent>
                  </Popover>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <Label>Last N Days</Label>
                <Input
                  type="number"
                  value={lastNDays}
                  onChange={(e) => setLastNDays(e.target.value)}
                  min="1"
                  max="365"
                />
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Research Interests</CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              placeholder="Enter research interests (one per line)"
              value={researchInterests}
              onChange={(e) => setResearchInterests(e.target.value)}
              className="min-h-[100px]"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Email Recipients</CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              placeholder="Enter email addresses (one per line)"
              value={emailRecipients}
              onChange={(e) => setEmailRecipients(e.target.value)}
              className="min-h-[100px]"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Podcast Options</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-4 mb-4">
              <Switch
                checked={createPodcast}
                onCheckedChange={setCreatePodcast}
              />
              <Label>Create Podcast</Label>
            </div>

            {createPodcast && (
              <Accordion type="single" collapsible className="w-full">
                <AccordionItem value="models">
                  <AccordionTrigger>
                    <div className="flex items-center">
                      <Settings2 className="mr-2 h-4 w-4" />
                      Model Settings
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="grid gap-4">
                      <div className="space-y-2">
                        <Label>Script Generation Model</Label>
                        <Select defaultValue="gpt-4">
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
                        <Select defaultValue="elevenlabs">
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
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="intro-music">
                  <AccordionTrigger>
                    <div className="flex items-center">
                      <Music className="mr-2 h-4 w-4" />
                      Intro Music
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-2">
                      <Label>Upload Intro Music (MP3/WAV)</Label>
                      <Input
                        type="file"
                        accept=".mp3,.wav"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) setIntroMusic(file);
                        }}
                      />
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
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
                          {format(new Date(node.timestamp), 'HH:mm:ss')}
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

        <div className="flex justify-end">
          <Button
            onClick={handleGenerate}
            disabled={isGenerating}
            className="w-full sm:w-auto"
          >
            <Play className="mr-2 h-4 w-4" />
            {isGenerating ? "Generating..." : "Generate Newsletter"}
          </Button>
        </div>
      </div>
    </div>
  );
} 